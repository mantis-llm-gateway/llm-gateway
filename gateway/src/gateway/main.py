import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import TypeAdapter, ValidationError

from gateway.context import AppContext, build_context, shutdown_context
from gateway.models import ChatCompletionsRequest, Config
from gateway.orchestrator import orchestrate
from gateway.settings import get_settings
from gateway.validation import validate_config


def _load_config() -> Config:
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
    config = _load_config()
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


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionsRequest,
    metadata: dict[str, str] = Depends(parse_metadata_header),
    ctx: AppContext = Depends(get_context),
) -> JSONResponse | StreamingResponse | None:
    prompt = body.messages[-1].content
    return await orchestrate(metadata, prompt, body.stream, ctx)
