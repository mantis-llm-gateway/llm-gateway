import logging

from botocore.exceptions import ClientError
from redis.asyncio import Redis

from gateway.engine.adaptor import Message, ProviderAdaptor
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


async def execute_attempt(
    target: ResolvedTarget,
    *,
    messages: list[ChatMessageRequest],
    stream: bool,
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
                chunks = await adaptor.stream_request(model_id, provider_messages)
                return StreamingSuccess(chunks=chunks)

            text = await adaptor.send_request(model_id, provider_messages)
            return CompleteSuccess(response=text)

        except ClientError as e:
            err_code = bedrock_error_code(e)
            err_msg = bedrock_error_message(e)
            logger.warning(
                "bedrock call failed: provider=%s model=%s code=%s status=%s msg=%s",
                target.provider,
                target.model,
                err_code,
                bedrock_status_code(e),
                err_msg,
            )
            action, status = classify_bedrock_error(e)
            match action:
                case ErrorAction.RETRY:
                    last_status = status
                    continue
                case ErrorAction.COOLDOWN:
                    await redis.set(
                        f"cooldown:{target.provider}:{target.model}", 1, ex=cooldown_ttl
                    )
                    return Failover(status_code=status, message=err_msg or "service unavailable")
                case ErrorAction.FAILOVER:
                    return Failover(status_code=status, message=err_msg or "service unavailable")
                case ErrorAction.ABORT:
                    return Abort(status_code=status, message=err_msg or "bad request")

    return Failover(status_code=last_status or 500)


def _to_provider_messages(messages: list[ChatMessageRequest]) -> list[Message]:
    return [{"role": message.role, "content": [{"text": message.content}]} for message in messages]
