from collections.abc import AsyncIterator

from botocore.exceptions import ClientError
from redis.asyncio import Redis

from gateway.engine.adaptor import EndOfStream, Message, ProviderAdaptor, TokenChunk
from gateway.engine.errors import ErrorAction, classify_bedrock_error
from gateway.engine.verdict import Abort, CompleteSuccess, Failover, StreamingSuccess, Verdict
from gateway.routing import ResolvedTarget


async def _token_strings(
    chunks: AsyncIterator[TokenChunk | EndOfStream], first_chunk: TokenChunk | EndOfStream
) -> AsyncIterator[str]:
    """Convert adaptor chunks into plain strings for StreamingResponse.

    `execute_attempt` already consumed one item from the adaptor so it could catch
    pre-stream provider errors. This helper yields that first item, then keeps
    consuming the remaining stream.
    """
    if not isinstance(first_chunk, EndOfStream):
        yield first_chunk["token"]

    async for chunk in chunks:
        if isinstance(chunk, EndOfStream):
            break

        yield chunk["token"]


async def execute_attempt(
    target: ResolvedTarget,
    *,
    prompt: str,
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
    messages: list[Message] = [{"role": "user", "content": [{"text": prompt}]}]

    last_status: int | None = None
    for _ in range(1 + target_retries):
        try:
            chunks = adaptor.send_request(model_id, messages, stream)

            if stream:
                first_chunk = await anext(chunks)
                return StreamingSuccess(chunks=_token_strings(chunks, first_chunk))

            async for chunk in chunks:
                if isinstance(chunk, EndOfStream):
                    break

                return CompleteSuccess(response=chunk["token"])

            # In case we get no usable content from the provider
            return Failover(status_code=502)

        except StopAsyncIteration:
            # If stream ends before yielding tokens or EndOfStream
            return Failover(status_code=502)

        except ClientError as e:
            action, status = classify_bedrock_error(e)
            match action:
                case ErrorAction.RETRY:
                    last_status = status
                    continue
                case ErrorAction.COOLDOWN:
                    await redis.set(
                        f"cooldown:{target.provider}:{target.model}",
                        1,
                        ex=cooldown_ttl,
                    )
                    return Failover(status_code=status)
                case ErrorAction.FAILOVER:
                    return Failover(status_code=status)
                case ErrorAction.ABORT:
                    return Abort(status_code=status)

    return Failover(status_code=last_status or 500)
