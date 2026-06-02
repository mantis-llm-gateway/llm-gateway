import asyncio
import json
import logging
import mimetypes
import secrets
import sys
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from posixpath import join as join_s3_key
from uuid import uuid4

import aioboto3
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import TypeAdapter, ValidationError
from pythonjsonlogger.json import JsonFormatter
from starlette.types import ASGIApp, Receive, Scope, Send

from gateway.context import AppContext, build_context, shutdown_context
from gateway.models import ChatCompletionsRequest, Config, ConfigResponse
from gateway.orchestrator import orchestrate
from gateway.settings import Settings, get_settings
from gateway.validation import validate_config

request_id_var: ContextVar[str] = ContextVar("request_id", default="none")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


async def _load_config(settings: Settings) -> Config:
    if settings.parameter_store_config_key:
        session = aioboto3.Session()
        async with session.client("ssm", region_name=settings.aws_region) as ssm:
            response = await ssm.get_parameter(
                Name=settings.parameter_store_config_key,
                WithDecryption=True,
            )
        config = Config(**json.loads(response["Parameter"]["Value"]))
    else:
        with open(Path(__file__).parent / "config.json") as f:
            config = Config(**json.load(f))
    validate_config(config)
    return config


async def _load_persisted_config(settings: Settings) -> Config | None:
    if not settings.parameter_store_config_key:
        return None

    session = aioboto3.Session()
    async with session.client("ssm", region_name=settings.aws_region) as ssm:
        response = await ssm.get_parameter(
            Name=settings.parameter_store_config_key,
            WithDecryption=True,
        )
    config = Config(**json.loads(response["Parameter"]["Value"]))
    validate_config(config)
    return config


def _config_response(ctx: AppContext, config: Config) -> ConfigResponse:
    return ConfigResponse(
        config=config,
        reload_required=config.model_dump(mode="json") != ctx.config.model_dump(mode="json"),
    )


def _dashboard_key(path: str, settings: Settings) -> str:
    key = path.strip("/") or "index.html"
    prefix = settings.dashboard_s3_prefix.strip("/")
    return join_s3_key(prefix, key) if prefix else key


def _local_dashboard_file(path: str) -> Path | None:
    requested = path.strip("/") or "index.html"
    if ".." in Path(requested).parts:
        return None

    dashboard_dist = Path(__file__).parent / "dashboard_dist"
    candidate = (dashboard_dist / requested).resolve()
    if not candidate.is_relative_to(dashboard_dist.resolve()):
        return None
    if candidate.is_file():
        return candidate

    fallback = dashboard_dist / "index.html"
    if not Path(requested).suffix and fallback.is_file():
        return fallback
    return None


async def _s3_dashboard_response(path: str, settings: Settings) -> Response:
    if not settings.dashboard_s3_bucket:
        raise HTTPException(status_code=404, detail="Dashboard assets are not configured")

    key = _dashboard_key(path, settings)
    response_key = key
    session = aioboto3.Session()
    async with session.client("s3", region_name=settings.aws_region) as s3:
        try:
            response = await s3.get_object(Bucket=settings.dashboard_s3_bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"NoSuchKey", "404", "NotFound"} or Path(path).suffix:
                raise HTTPException(status_code=404, detail="Dashboard asset not found") from exc
            try:
                response_key = _dashboard_key("index.html", settings)
                response = await s3.get_object(
                    Bucket=settings.dashboard_s3_bucket,
                    Key=response_key,
                )
            except ClientError as index_exc:
                raise HTTPException(
                    status_code=404, detail="Dashboard asset not found"
                ) from index_exc

        body = await response["Body"].read()

    media_type = response.get("ContentType")
    if not media_type or media_type == "binary/octet-stream":
        media_type = mimetypes.guess_type(response_key)[0] or "application/octet-stream"

    headers = {}
    for source, target in (
        ("CacheControl", "Cache-Control"),
        ("ETag", "ETag"),
    ):
        if source in response:
            headers[target] = response[source]
    last_modified = response.get("LastModified")
    if last_modified is not None and last_modified.tzinfo is not None:
        headers["Last-Modified"] = format_datetime(last_modified.astimezone(UTC), usegmt=True)

    return Response(content=body, media_type=media_type, headers=headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s")
    )
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(level=settings.log_level.upper(), handlers=[handler])

    config = await _load_config(settings)
    app.state.context = await build_context(settings, config)
    try:
        yield
    finally:
        await shutdown_context(app.state.context)


def get_context(request: Request) -> AppContext:
    return request.app.state.context


class OverallTimeoutMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != "/v1/chat/completions":
            await self.app(scope, receive, send)
            return

        timeout_seconds = scope["app"].state.context.config.initial_response_timeout
        headers_sent = False
        response_complete = False
        content_type = b""

        async def tracked_send(message):
            nonlocal headers_sent, response_complete, content_type
            if message["type"] == "http.response.start":
                headers_sent = True
                headers = dict(message.get("headers", []))
                content_type = headers.get(b"content-type", b"")
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                response_complete = True
            await send(message)

        scope["overall_timeout_start"] = datetime.now(UTC)
        timeout_context = asyncio.timeout(timeout_seconds)

        try:
            async with timeout_context:
                await self.app(scope, receive, tracked_send)
        except TimeoutError:
            if not timeout_context.expired():
                raise

            if response_complete:
                return

            if not headers_sent:
                response = JSONResponse(status_code=504, content={"error": "request timed out"})
                await response(scope, receive, send)
                return

            if content_type.startswith(b"text/plain"):
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"\nerror: request timed out\n",
                        "more_body": False,
                    }
                )


app = FastAPI(lifespan=lifespan)

_metadata_adapter = TypeAdapter(dict[str, str])


@app.middleware("http")
async def set_request_id(request: Request, call_next):
    request_id = request.headers.get("x-amzn-trace-id") or str(uuid4())
    request_id_var.set(request_id)
    return await call_next(request)


app.add_middleware(OverallTimeoutMiddleware)


def parse_metadata_header(metadata: str | None = Header(default=None)) -> dict[str, str]:
    try:
        return _metadata_adapter.validate_python(json.loads(metadata or "{}"))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail="metadata header must be a JSON object with string keys and values",
        ) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
async def get_config(ctx: AppContext = Depends(get_context)) -> ConfigResponse:
    config = await _load_persisted_config(ctx.settings)
    return _config_response(ctx, config or ctx.config)


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request,
    body: ChatCompletionsRequest,
    metadata: dict[str, str] = Depends(parse_metadata_header),
    ctx: AppContext = Depends(get_context),
) -> JSONResponse | StreamingResponse | None:
    start_time: datetime = request.scope["overall_timeout_start"]
    return await orchestrate(
        metadata,
        body.messages,
        body.stream,
        ctx,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        system=body.system,
        start_time=start_time,
    )


@app.post("/config")
async def update_config(
    config: Config,
    ctx: AppContext = Depends(get_context),
) -> ConfigResponse:
    for rule in config.routing_rules:
        if not rule.id:
            rule.id = secrets.token_hex(4)
    try:
        validate_config(config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not ctx.settings.parameter_store_config_key:
        raise HTTPException(
            status_code=409,
            detail="PARAMETER_STORE_CONFIG_KEY must be configured to persist routing config",
        )

    session = aioboto3.Session()
    async with session.client("ssm", region_name=ctx.settings.aws_region) as ssm:
        await ssm.put_parameter(
            Name=ctx.settings.parameter_store_config_key,
            Value=config.model_dump_json(),
            Type="String",
            Overwrite=True,
        )
    return _config_response(ctx, config)


@app.get("/{path:path}", include_in_schema=False)
async def dashboard(path: str, ctx: AppContext = Depends(get_context)) -> Response:
    if ctx.settings.dashboard_s3_bucket:
        return await _s3_dashboard_response(path, ctx.settings)

    local_file = _local_dashboard_file(path)
    if local_file:
        return FileResponse(local_file)

    raise HTTPException(status_code=404, detail="Dashboard assets are not configured")
