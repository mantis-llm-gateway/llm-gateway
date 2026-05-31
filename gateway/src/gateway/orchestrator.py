import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.context import AppContext
from gateway.engine import Abort, CompleteSuccess, Failover, StreamingSuccess, execute_attempt
from gateway.engine.errors import bedrock_error_code
from gateway.models import ChatMessageRequest
from gateway.routing import resolve_attempt_chain


async def _handle_stream(chunks: AsyncIterator[str]) -> AsyncGenerator[str, None]:
    try:
        async for chunk in chunks:
            yield chunk
    except ClientError as e:
        if bedrock_error_code(e) == "ChunkTimeOutException":
            logger.warning("stream chunk timeout", exc_info=e)
            yield "\nerror: provider timeout - check logs for more information\n"
            return
        else:
            logger.warning("stream client error", exc_info=e)
            yield "\nerror: provider failure - check logs for more information\n"
            return
    except Exception as e:
        logger.warning("stream error", exc_info=e)
        yield "\nerror: check logs for more information\n"
        return


logger = logging.getLogger(__name__)


async def orchestrate(
    metadata: dict[str, str],
    messages: list[ChatMessageRequest],
    stream: bool,
    ctx: AppContext,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    system: str | None = None,
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
    cache_prompt = _conversation_cache_prompt(messages, system)
    use_semantic_cache = _should_use_semantic_cache(messages, ctx)
    skip_cache = _should_skip_cache(temperature, ctx)

    last_status: int | None = None
    for target in resolved_chain:
        if datetime.now(UTC) > deadline:
            return JSONResponse(status_code=504, content={"error": "request timed out"})

        if await ctx.redis.exists(f"gateway:cooldown:{target.provider}:{target.model}"):
            continue

        if not stream and not skip_cache:
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
            stream=stream,
            start_time=start_time,
            adaptor=ctx.adaptor,
            redis=ctx.redis,
            target_retries=ctx.config.target_retries,
            cooldown_ttl=ctx.config.cooldown_ttl,
            temperature=temperature,
            max_tokens=max_tokens,
            system=system,
            stream_idle_timeout=ctx.config.stream_idle_timeout,
        )

        match verdict:
            case CompleteSuccess(response=result):
                if not stream:
                    if not skip_cache:
                        await ctx.prompt_cache.set(
                            prompt=cache_prompt,
                            response=result["response"],
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
                            "input_tokens": result["input_tokens"],
                            "output_tokens": result["output_tokens"],
                            "latency_ms": latency_ms,
                        },
                    )
                return JSONResponse(content={"response": result["response"]})
            case StreamingSuccess(chunks=g):
                return StreamingResponse(
                    _handle_stream(g),
                    media_type="text/event-stream",
                )
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


def _conversation_cache_prompt(messages: list[ChatMessageRequest], system: str | None) -> str:
    return json.dumps(
        {
            "system": system,
            "messages": [message.model_dump(mode="json") for message in messages],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _should_use_semantic_cache(messages: list[ChatMessageRequest], ctx: AppContext) -> bool:
    semantic_config = ctx.config.prompt_cache.semantic
    return (
        semantic_config is not None and len(messages) <= semantic_config.conversation_size_threshold
    )


def _should_skip_cache(temperature: float | None, ctx: AppContext) -> bool:
    threshold = ctx.config.prompt_cache.temperature_threshold
    return temperature is not None and temperature > threshold
