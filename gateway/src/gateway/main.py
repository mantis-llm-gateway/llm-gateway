import json
import logging
import sys
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import TypeAdapter, ValidationError
from pythonjsonlogger.json import JsonFormatter

from gateway.context import AppContext, build_context, shutdown_context
from gateway.models import ChatCompletionsRequest, Config
from gateway.orchestrator import orchestrate
from gateway.settings import get_settings
from gateway.validation import validate_config

request_id_var: ContextVar[str] = ContextVar("request_id", default="none")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


def _load_config() -> Config:
    with open(Path(__file__).parent / "config.json") as f:
        config = Config(**json.load(f))
    validate_config(config)
    return config


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(level=settings.log_level.upper(), handlers=[handler])

    config = _load_config()
    app.state.context = await build_context(settings, config)
    try:
        yield
    finally:
        await shutdown_context(app.state.context)


app = FastAPI(lifespan=lifespan)
_metadata_adapter = TypeAdapter(dict[str, str])


@app.middleware("http")
async def set_request_id(request: Request, call_next):
    request_id = request.headers.get("x-amzn-trace-id") or str(uuid4())
    request_id_var.set(request_id)
    return await call_next(request)


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


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionsRequest,
    metadata: dict[str, str] = Depends(parse_metadata_header),
    ctx: AppContext = Depends(get_context),
) -> JSONResponse | StreamingResponse | None:
    return await orchestrate(metadata, body.messages, body.stream, ctx)
