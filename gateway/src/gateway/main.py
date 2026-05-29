import json
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import aioboto3
import boto3
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError

from gateway.context import AppContext, build_context, shutdown_context
from gateway.models import ChatCompletionsRequest, Config
from gateway.orchestrator import orchestrate
from gateway.settings import Settings, get_settings
from gateway.validation import validate_config


def _load_config(settings: Settings) -> Config:
    if settings.parameter_store_config_key:
        ssm = boto3.client("ssm", region_name=settings.aws_region)
        response = ssm.get_parameter(Name=settings.parameter_store_config_key, WithDecryption=True)
        config = Config(**json.loads(response["Parameter"]["Value"]))
    else:
        with open(Path(__file__).parent / "config.json") as f:
            config = Config(**json.load(f))
    validate_config(config)
    return config


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = _load_config(settings)
    app.state.context = await build_context(settings, config)
    try:
        yield
    finally:
        await shutdown_context(app.state.context)


app = FastAPI(lifespan=lifespan)
_metadata_adapter = TypeAdapter(dict[str, str])


def get_context(request: Request) -> AppContext:
    return request.app.state.context


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
async def get_config(ctx: AppContext = Depends(get_context)) -> Config:
    return ctx.config


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionsRequest,
    metadata: dict[str, str] = Depends(parse_metadata_header),
    ctx: AppContext = Depends(get_context),
) -> JSONResponse | StreamingResponse | None:
    return await orchestrate(metadata, body.messages, body.stream, ctx)


@app.post("/config")
async def update_config(
    config: Config,
    ctx: AppContext = Depends(get_context),
) -> Config:
    for rule in config.routing_rules:
        if not rule.id:
            rule.id = secrets.token_hex(4)
    try:
        validate_config(config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if ctx.settings.parameter_store_config_key:
        session = aioboto3.Session()
        async with session.client("ssm", region_name=ctx.settings.aws_region) as ssm:
            await ssm.put_parameter(
                Name=ctx.settings.parameter_store_config_key,
                Value=config.model_dump_json(),
                Type="String",
                Overwrite=True,
            )
    ctx.config = config
    return config


_dashboard_dist = Path(__file__).parent / "dashboard_dist"
if _dashboard_dist.exists():
    app.mount("/", StaticFiles(directory=_dashboard_dist, html=True), name="dashboard")
