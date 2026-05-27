import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from botocore.exceptions import ClientError
from redis.asyncio import Redis

from gateway.engine.adaptor import GuardrailIntervention, Message, ProviderAdaptor
from gateway.engine.errors import (
    ErrorAction,
    bedrock_error_code,
    bedrock_error_message,
    bedrock_status_code,
    classify_bedrock_error,
)
from gateway.engine.verdict import Abort, CompleteSuccess, Failover, StreamingSuccess, Verdict
from gateway.models import ChatMessageRequest
from gateway.routing import ResolvedTarget

logger = logging.getLogger(__name__)


async def _logged_token_strings(
    chunks: AsyncIterator[str],
    *,
    guardrail_info: dict,
    metadata: dict[str, str],
    stream: bool,
    target: ResolvedTarget,
    start_time: datetime,
) -> AsyncIterator[str]:
    logger.info(
        "stream started",
        extra={
            "metadata": metadata,
            "stream": stream,
            "provider": target.provider,
            "model": target.model,
        },
    )
    try:
        async for token in chunks:
            yield token
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        if guardrail_info:
            logger.warning(
                "guardrail intervened",
                extra={
                    "metadata": metadata,
                    "stream": stream,
                    "provider": target.provider,
                    "model": target.model,
                    "trace": guardrail_info["trace"],
                },
            )
        logger.info(
            "stream completed",
            extra={
                "metadata": metadata,
                "stream": stream,
                "provider": target.provider,
                "model": target.model,
                "latency_ms": latency_ms,
            },
        )
    except BaseException as e:
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        logger.error(
            "mid-stream error",
            extra={
                "metadata": metadata,
                "stream": stream,
                "provider": target.provider,
                "model": target.model,
                "latency_ms": latency_ms,
                "error": str(e),
            },
        )
        raise


async def execute_attempt(
    target: ResolvedTarget,
    *,
    messages: list[ChatMessageRequest],
    metadata: dict[str, str],
    prompt: str,
    stream: bool,
    start_time: datetime,
    adaptor: ProviderAdaptor,
    redis: Redis,
    target_retries: int,
    cooldown_ttl: int,
) -> Verdict:
    """Run one target with up to `target_retries` retries.

    Returns a typed verdict that the orchestrator translates into HTTP behavior.
    """
    model_id = target.model
    provider_messages = _to_provider_messages(messages)

    last_status: int | None = None
    for _ in range(1 + target_retries):
        try:
            if stream:
                chunks, guardrail_info = await adaptor.stream_request(model_id, provider_messages)
                return StreamingSuccess(
                    chunks=_logged_token_strings(
                        chunks,
                        guardrail_info=guardrail_info,
                        metadata=metadata,
                        stream=stream,
                        target=target,
                        start_time=start_time,
                    )
                )

            result = await adaptor.send_request(model_id, provider_messages)
            if isinstance(result, GuardrailIntervention):
                logger.warning(
                    "guardrail intervened",
                    extra={
                        "metadata": metadata,
                        "stream": stream,
                        "provider": target.provider,
                        "model": target.model,
                        "trace": result.trace,
                    },
                )
                return CompleteSuccess(
                    response={"response": result.response, "input_tokens": 0, "output_tokens": 0}
                )
            return CompleteSuccess(response=result)

        except ClientError as e:
            err_code = bedrock_error_code(e)
            err_msg = bedrock_error_message(e)
            logger.warning(
                "bedrock call failed",
                extra={
                    "metadata": metadata,
                    "stream": stream,
                    "provider": target.provider,
                    "model": target.model,
                    "err_code": err_code,
                    "http_status": bedrock_status_code(e),
                    "err_msg": err_msg,
                },
            )
            action, status = classify_bedrock_error(e)
            match action:
                case ErrorAction.RETRY:
                    logger.info(
                        "retry target",
                        extra={
                            "metadata": metadata,
                            "stream": stream,
                            "provider": target.provider,
                            "model": target.model,
                        },
                    )
                    last_status = status
                    continue
                case ErrorAction.COOLDOWN:
                    logger.warning(
                        "target put into cooldown",
                        extra={"provider": target.provider, "model": target.model},
                    )
                    await redis.set(
                        f"gateway:cooldown:{target.provider}:{target.model}", 1, ex=cooldown_ttl
                    )
                    return Failover(status_code=status, message=err_msg or "service unavailable")
                case ErrorAction.FAILOVER:
                    return Failover(status_code=status, message=err_msg or "service unavailable")
                case ErrorAction.ABORT:
                    return Abort(status_code=status, message=err_msg or "bad request")

    return Failover(status_code=last_status or 500)


def _to_provider_messages(messages: list[ChatMessageRequest]) -> list[Message]:
    return [{"role": message.role, "content": [{"text": message.content}]} for message in messages]
