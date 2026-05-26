import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi.responses import JSONResponse, StreamingResponse

from gateway.context import AppContext
from gateway.engine import Abort, CompleteSuccess, Failover, StreamingSuccess, execute_attempt
from gateway.models import ChatMessageRequest
from gateway.routing import resolve_attempt_chain

logger = logging.getLogger(__name__)


async def orchestrate(
    metadata: dict[str, str], messages: list[ChatMessageRequest], stream: bool, ctx: AppContext
) -> JSONResponse | StreamingResponse | None:
    """Run a chat-completion request through the gateway.

    Resolves the attempt chain, then for each target:
      - Honors the response deadline (504 if exceeded).
      - Skips targets currently in cooldown.
      - Calls the executor for one attempt and acts on its verdict:
          Success  → response was streamed inside the executor; return None.
          Abort    → client-side error; return as-is.
          Failover → record status, continue to next target.

    If no target succeeds, returns the last Failover status. If every target
    was cooled down (no attempts made), returns None.

    The prompt cache stores a canonical JSON representation of the whole
    conversation, so exact cache hits are scoped to the complete chat history.
    """
    start_time = datetime.now(UTC)
    deadline = start_time + timedelta(seconds=ctx.config.initial_response_timeout)
    resolved_chain = resolve_attempt_chain(metadata, ctx.config)
    cache_prompt = _conversation_cache_prompt(messages)
    prompt = cache_prompt
    use_semantic_cache = _should_use_semantic_cache(messages, ctx)

    last_status: int | None = None
    for target in resolved_chain:
        if datetime.now(UTC) > deadline:
            return JSONResponse(status_code=504, content={"error": "request timed out"})

        if await ctx.redis.exists(f"gateway:cooldown:{target.provider}:{target.model}"):
            continue

        if not stream:
            cached = await ctx.prompt_cache.get(
                prompt=cache_prompt,
                model=target.model,
                provider=target.provider,
                use_semantic=use_semantic_cache,
            )
            if cached is not None:
                latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
                logger.info(
                    "cache hit",
                    extra={
                        "metadata": metadata,
                        "stream": stream,
                        "provider": target.provider,
                        "model": target.model,
                        "latency_ms": latency_ms,
                    },
                )
                return JSONResponse(content={"response": cached})

        verdict = await execute_attempt(
            target,
            messages=messages,
            metadata=metadata,
            prompt=prompt,
            stream=stream,
            start_time=start_time,
            adaptor=ctx.adaptor,
            redis=ctx.redis,
            target_retries=ctx.config.target_retries,
            cooldown_ttl=ctx.config.cooldown_ttl,
        )

        match verdict:
            case CompleteSuccess(response=text):
                if not stream:
                    await ctx.prompt_cache.set(
                        prompt=cache_prompt,
                        response=text,
                        model=target.model,
                        provider=target.provider,
                        use_semantic=use_semantic_cache,
                    )

                    latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
                    logger.info(
                        "successful non-streamed LLM response",
                        extra={
                            "metadata": metadata,
                            "stream": stream,
                            "provider": target.provider,
                            "model": target.model,
                            "latency_ms": latency_ms,
                        },
                    )
                return JSONResponse(content={"response": text})
            case StreamingSuccess(chunks=g):
                return StreamingResponse(g, media_type="text/event-stream")
            case Abort(status_code=code, message=msg):
                latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
                logger.warning(
                    "abort",
                    extra={
                        "metadata": metadata,
                        "stream": stream,
                        "status_code": code,
                        "error_message": msg,
                        "latency_ms": latency_ms,
                    },
                )
                return JSONResponse(status_code=code, content={"error": msg})
            case Failover(status_code=code):
                last_status = code
                logger.info("failover", extra={"metadata": metadata, "stream": stream})
                continue

    if last_status is not None:
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        logger.warning(
            "targets exhausted",
            extra={
                "metadata": metadata,
                "status_code": last_status,
                "error_message": "service unavailable",
                "latency_ms": latency_ms,
            },
        )
        return JSONResponse(status_code=last_status, content={"error": "service unavailable"})

    return None


def _conversation_cache_prompt(messages: list[ChatMessageRequest]) -> str:
    return json.dumps(
        [message.model_dump(mode="json") for message in messages],
        sort_keys=True,
        separators=(",", ":"),
    )


def _should_use_semantic_cache(messages: list[ChatMessageRequest], ctx: AppContext) -> bool:
    semantic_config = ctx.config.prompt_cache.semantic
    return (
        semantic_config is not None and len(messages) <= semantic_config.conversation_size_threshold
    )
