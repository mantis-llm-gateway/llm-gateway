import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis


class AliasConfig(BaseModel):
    provider: str
    model: str
    rate_limits: dict[str, int]


class RuleMatchConfig(BaseModel):
    name: str
    value: str


class TargetConfig(BaseModel):
    alias: str
    weight: int


class RoutingRuleConfig(BaseModel):
    id: str
    name: str
    match: RuleMatchConfig
    targets: list[TargetConfig]


class Config(BaseModel):
    aliases: dict[str, AliasConfig]
    routing_rules: list[RoutingRuleConfig]
    target_retries: int
    initial_response_timeout: int
    default_model: str
    fallbacks: list[str]


with open(Path(__file__).parent / "config.json") as f:
    config = Config(**json.load(f))


app = FastAPI()

ALIASES = config.aliases
ROUTING_RULES = config.routing_rules
TARGET_RETRIES = config.target_retries
INITIAL_RESPONSE_TIMEOUT = config.initial_response_timeout
DEFAULT_MODEL = config.default_model
FALLBACKS = config.fallbacks
COOLDOWN_TTL = 60


def check_for_duplicates_in_config() -> None:
    for rule in ROUTING_RULES:
        a_target_list = [target.alias for target in rule.targets]
        a_target_list_with_fallbacks = a_target_list + FALLBACKS
        if len(a_target_list_with_fallbacks) != len(set(a_target_list_with_fallbacks)):
            raise ValueError(f"Duplicate targets found in config for rule '{rule.name}'")


check_for_duplicates_in_config()

redis_client = Redis(host="localhost", port=6379, decode_responses=True)


def is_matching_rule(header_name: str, header_value: str, rule: RoutingRuleConfig) -> bool:
    return header_name == rule.match.name and header_value == rule.match.value


async def try_target(target: dict[str, str], deadline: datetime):  # type: ignore[return]
    last_error = None
    attempts = 0
    max_attempts = 1 + TARGET_RETRIES
    while attempts < max_attempts:
        if datetime.now(UTC) > deadline:
            return (TimeoutError, "abort")

        # try:
        # -Call a function yet to be provided by Riz for sending a request to the target
        #  model using anyLLM and streaming a response back to the client.
        #  I will likely need to add code for SSE in this file.
        #    - The LLM provider should send back a 200 OK before the first token is sent.
        #    - If the stream completes without mid-stream errors, return:
        #      ('streaming completed', 'terminate trying targets')
        #    - If there is a mid-stream error, communicate it to the client but do not
        #      retry; still return:
        #      ('streaming completed', 'terminate trying targets')

        # -The code here should handle errors sent back by providers before streaming
        #  starts, i.e. 4xx errors, including 429 (see comments below)

        # if the LLM provider sends back a 4xx error before streaming (but non-429):
        #   this means there was a client-side issue, and no more targets should be tried
        #   return the caught error and 'abort' in a tuple: (error, 'abort')
        # elif there is a 429 error or a timeout:
        #   the provider is rate limiting or timed out; try the next target in the chain
        #   key = f"cooldown:{target['provider']}:{target['model']}"
        #   await redis_client.set(key, 1, ex=COOLDOWN_TTL)
        #   return the caught error and 'failover' in a tuple: (error, 'failover')
        # elif there is a 5xx error:
        #   assign the caught error to last_error
        #   increment attempts and retry the target

        # -Todo: From Hubert in TEA-36: Core routing logic PR:
        #  "These should be constants or typed into an Enum to
        #  avoid typo-driven errors later."
    return (last_error, "failover")


def select_entry_target(
    weighted_targets: list[TargetConfig], rng: random.Random | None = None
) -> str:
    if rng is None:
        rng = random.Random()
    targets = []
    weights = []
    for target in weighted_targets:
        targets.append(target.alias)
        weights.append(target.weight)

    return rng.choices(targets, weights=weights, k=1)[0]


def build_attempt_chain(
    entry_target: str, targets_for_matching_rule: list[TargetConfig]
) -> list[str]:
    attempt_chain = [entry_target]
    for target in targets_for_matching_rule:
        if target.alias == entry_target:
            continue
        else:
            attempt_chain.append(target.alias)

    return attempt_chain


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request) -> JSONResponse | None:
    # -Once you start using the cache and have Riz's streaming function, refactor all this
    #  code in the handler and extract into a routing module/service,
    #  as per Hubert's suggestion in PR TEA-36 Core routing logic
    now = datetime.now(UTC)
    deadline = now + timedelta(seconds=INITIAL_RESPONSE_TIMEOUT)

    # -I will use the cache class provided by Rey (teammate) here to check if the cache
    #  should be bypassed. If not, I will call cache.get(). If a cached response is found,
    #  it will be sent back to the client and the rest of the handler will not execute;
    #  otherwise, the rest of the handler will execute.

    metadata: dict[str, str] = json.loads(request.headers.get("metadata") or "{}")
    routing_rule_header_name: str = list(metadata.keys())[0]
    routing_rule_header_value: str = list(metadata.values())[0]

    found_matching_rule = False
    for rule in ROUTING_RULES:
        if is_matching_rule(routing_rule_header_name, routing_rule_header_value, rule):
            found_matching_rule = True
            entry_target = select_entry_target(rule.targets)
            attempt_chain = build_attempt_chain(entry_target, rule.targets)

            break

    if not found_matching_rule:
        attempt_chain = [DEFAULT_MODEL] + FALLBACKS
    else:
        attempt_chain += FALLBACKS

    resolved_attempt_chain = [
        {
            "provider": ALIASES[target].provider,
            "model": ALIASES[target].model,
        }
        for target in attempt_chain
    ]

    last_error = None
    for target in resolved_attempt_chain:
        if datetime.now(UTC) > deadline:
            return JSONResponse(status_code=504, content={"error": "request timed out"})

        if await redis_client.exists(f"cooldown:{target['provider']}:{target['model']}"):
            continue

        (result, action) = await try_target(target, deadline)

        if action == "terminate trying targets":
            # Nothing needs to be done. The last token has already been streamed back,
            # and a 200 OK was sent to the client before the first token.
            last_error = None
            break
        elif action == "failover":
            last_error = result
            continue
        elif action == "abort":
            return JSONResponse(
                status_code=result.response.status_code, content={"error": "bad request"}
            )

    if last_error:
        return JSONResponse(
            status_code=last_error.response.status_code, content={"error": "bad request"}
        )

    return None
