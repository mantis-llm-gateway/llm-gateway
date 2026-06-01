import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from botocore.exceptions import ClientError
from redis.asyncio import Redis

from gateway.engine.adaptor import GuardrailIntervention, Message, ProviderAdaptor, StreamResult
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


def _extra(
    metadata: dict[str, str],
    stream: bool,
    target: ResolvedTarget,
    **kwargs,
) -> dict:
    return {
        "metadata": json.dumps(metadata, sort_keys=True),
        "stream": stream,
        "provider": target.provider,
        "model": target.model,
        **kwargs,
    }


def _sanitize_assessment(assessment: dict) -> dict:
    result = dict(assessment)
    if "sensitiveInformationPolicy" in result:
        sip = result["sensitiveInformationPolicy"]
        result["sensitiveInformationPolicy"] = {
            "piiEntities": [
                {k: v for k, v in e.items() if k != "match"} for e in sip.get("piiEntities", [])
            ],
            "regexes": [
                {k: v for k, v in r.items() if k != "match"} for r in sip.get("regexes", [])
            ],
        }
    if "wordPolicy" in result:
        wp = result["wordPolicy"]
        result["wordPolicy"] = {
            "customWords": [
                {k: v for k, v in w.items() if k != "match"} for w in wp.get("customWords", [])
            ],
            "managedWordLists": [
                {k: v for k, v in w.items() if k != "match"} for w in wp.get("managedWordLists", [])
            ],
        }
    return result


def _sanitize_trace(trace: dict) -> dict:
    result = {k: v for k, v in trace.items() if k != "modelOutput"}
    if "inputAssessment" in result:
        result["inputAssessment"] = {
            gid: _sanitize_assessment(a) for gid, a in result["inputAssessment"].items()
        }
    if "outputAssessments" in result:
        result["outputAssessments"] = {
            gid: [_sanitize_assessment(a) for a in assessments]
            for gid, assessments in result["outputAssessments"].items()
        }
    return result


async def _logged_token_strings(
    stream_result: StreamResult,
    *,
    metadata: dict[str, str],
    stream: bool,
    target: ResolvedTarget,
    start_time: datetime,
) -> AsyncIterator[str]:
    logger.info("stream started", extra=_extra(metadata, stream, target))
    try:
        async for token in stream_result:
            yield token
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        if stream_result.guardrail_info:
            logger.warning(
                "guardrail intervened",
                extra=_extra(
                    metadata,
                    stream,
                    target,
                    trace=_sanitize_trace(stream_result.guardrail_info["trace"]),
                ),
            )
        logger.info(
            "stream completed",
            extra=_extra(
                metadata,
                stream,
                target,
                latency_ms=latency_ms,
                input_tokens=stream_result.usage_info.get("input_tokens", 0),
                output_tokens=stream_result.usage_info.get("output_tokens", 0),
            ),
        )
    except BaseException as e:
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        logger.error(
            "mid-stream error",
            extra=_extra(metadata, stream, target, latency_ms=latency_ms, error=str(e)),
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
                stream_result = await adaptor.stream_request(model_id, provider_messages)
                return StreamingSuccess(
                    chunks=_logged_token_strings(
                        stream_result,
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
                    extra=_extra(metadata, stream, target, trace=_sanitize_trace(result.trace)),
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
                extra=_extra(
                    metadata,
                    stream,
                    target,
                    err_code=err_code,
                    http_status=bedrock_status_code(e),
                    err_msg=err_msg,
                ),
            )
            action, status = classify_bedrock_error(e)
            match action:
                case ErrorAction.RETRY:
                    logger.info("retry target", extra=_extra(metadata, stream, target))
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
