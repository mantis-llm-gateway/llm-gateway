from datetime import UTC, datetime, timedelta

from fastapi.responses import JSONResponse

from gateway.context import AppContext
from gateway.engine import Abort, Failover, Success, execute_attempt
from gateway.routing import resolve_attempt_chain


async def orchestrate(metadata: dict[str, str], ctx: AppContext) -> JSONResponse | None:
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

    TODO: Cache lookup at entry (PromptCache.get) and write-through on Success
    once the executor returns the response payload.
    """
    deadline = datetime.now(UTC) + timedelta(seconds=ctx.config.initial_response_timeout)
    resolved_chain = resolve_attempt_chain(metadata, ctx.config)

    last_status: int | None = None
    for target in resolved_chain:
        if datetime.now(UTC) > deadline:
            return JSONResponse(status_code=504, content={"error": "request timed out"})

        if await ctx.redis.exists(f"cooldown:{target.provider}:{target.model}"):
            continue

        verdict = await execute_attempt(
            target,
            adaptor=ctx.adaptor,
            redis=ctx.redis,
            target_retries=ctx.config.target_retries,
            cooldown_ttl=ctx.config.cooldown_ttl,
        )

        match verdict:
            case Success():
                return None
            case Abort(status_code=code, message=msg):
                return JSONResponse(status_code=code, content={"error": msg})
            case Failover(status_code=code):
                last_status = code
                continue

    if last_status is not None:
        return JSONResponse(status_code=last_status, content={"error": "service unavailable"})

    return None
