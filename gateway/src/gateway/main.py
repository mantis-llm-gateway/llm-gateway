import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

with open(Path(__file__).parent / "config.json") as f:
    config = json.load(f)

app = FastAPI()


def is_matching_rule(header_name, header_value, rule):
    return header_name == rule["match"]["name"] and header_value == rule["match"]["value"]


def try_target(target, deadline):
    last_error = None
    attempts = 0
    max_attempts = 1 + config["target_retries"]
    while attempts < max_attempts:
        if datetime.now(datetime.utc) > deadline:
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
        #   return the caught error and 'failover' in a tuple: (error, 'failover')
        # elif there is a 5xx error:
        #   assign the caught error to last_error
        #   increment attempts and retry the target

    return (last_error, "failover")


def select_entry_target(weighted_targets):
    targets = []
    weights = []
    for target in weighted_targets:
        targets.append(target["alias"])
        weights.append(target["weight"])

    return random.choices(targets, weights=weights, k=1)[0]


def build_attempt_chain(entry_target, targets_for_matching_rule):
    attempt_chain = [entry_target]
    for target in targets_for_matching_rule:
        if target["alias"] == entry_target:
            continue
        else:
            attempt_chain.append(target["alias"])

    return attempt_chain


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    now = datetime.now(UTC)
    deadline = now + timedelta(seconds=config["initial_response_timeout"])

    # -I will use the cache class provided by Rey (teammate) here to check if the cache
    #  should be bypassed. If not, I will call cache.get(). If a cached response is found,
    #  it will be sent back to the client and the rest of the handler will not execute;
    #  otherwise, the rest of the handler will execute.

    metadata = json.loads(request.headers.get("metadata") or "{}")
    routing_rule_header_name = list(metadata.keys())[0]
    routing_rule_header_value = list(metadata.values())[0]

    found_matching_rule = False
    for rule in config["routing_rules"]:
        if is_matching_rule(routing_rule_header_name, routing_rule_header_value, rule):
            found_matching_rule = True
            entry_target = select_entry_target(rule["targets"])
            attempt_chain = build_attempt_chain(entry_target, rule["targets"])

            break

    if not found_matching_rule:
        attempt_chain = [config["default_model"]] + config["fallbacks"]
    else:
        attempt_chain += config["fallbacks"]

    attempt_chain = [
        {
            "provider": config["aliases"][target]["provider"],
            "model": config["aliases"][target]["model"],
        }
        for target in attempt_chain
    ]

    last_error = None
    for target in attempt_chain:
        if datetime.now(UTC) > deadline:
            return JSONResponse(status_code=504, content={"error": "request timed out"})

        (result, action) = try_target(target, deadline)

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
