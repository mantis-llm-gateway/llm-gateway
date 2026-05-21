from redis.asyncio import Redis

from gateway.engine.adaptor import ProviderAdaptor
from gateway.engine.errors import ErrorAction, classify_bedrock_error
from gateway.engine.verdict import Abort, CompleteSuccess, Failover, StreamingSuccess, Verdict
from gateway.routing import ResolvedTarget


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

    Contract (to be implemented when provider wiring lands):
      - Successful stream completion → CompleteSuccess(response) or StreamingSuccess(chunks)
      - 4xx non-429 before stream start → Abort(status_code=e.status_code)
      - 429 → set cooldown key, return Failover(status_code=429)
      - 5xx → retry up to max_attempts; if exhausted, Failover(status_code=last_5xx)

    """
    model_id = ".".join([target.provider, target.model])
    messages = [{"role": "user", "content": prompt}]

    last_status: int | None = None
    for _ in range(1 + target_retries):
        try:
            response = await adaptor.send_request(model_id, messages, stream)
        except Exception as e:
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
        else:
            if isinstance(response, str):
                return CompleteSuccess(response=response)
            return StreamingSuccess(chunks=response)

    return Failover(status_code=last_status or 500)
