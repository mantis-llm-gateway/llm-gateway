import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.context import AppContext, build_context, shutdown_context
from gateway.models import Config
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
    config = _load_config()
    app.state.context = build_context(settings, config)
    try:
        yield
    finally:
        await shutdown_context(app.state.context)


app = FastAPI(lifespan=lifespan)


def get_context(request: Request) -> AppContext:
    return request.app.state.context


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request,
    ctx: AppContext = Depends(get_context),
) -> JSONResponse | StreamingResponse | None:
    metadata: dict[str, str] = json.loads(request.headers.get("metadata") or "{}")
    # Assumes well formed request body - TODO: wrape in Pydantic model to validate
    body = await request.json()
    prompt = body["messages"][-1]["content"]
    stream = body.get("stream", False)
    return await orchestrate(metadata, prompt, stream, ctx)
