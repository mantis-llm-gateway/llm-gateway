# Gateway Service

Gateway component.

## Project Structure

```text
gateway/
├── src/
│   └── gateway/
│       ├── __init__.py
│       ├── main.py                  # FastAPI app, lifespan, handler (one-liner → orchestrate)
│       ├── settings.py              # infra config (env-derived: Redis endpoint, AWS region, ...)
│       ├── context.py               # AppContext + build_context + shutdown_context
│       ├── models.py                # Pydantic config shapes (Config, AliasConfig, ...)
│       ├── validation.py            # startup validators (no duplicates, weights, ranges, ...)
│       ├── config.json              # routing config (aliases, rules, fallbacks, retries, ...)
│       ├── orchestrator.py          # per-request loop: deadline + cooldown + executor + verdict → HTTP
│       ├── cache/                   # cache module
│       │   ├── prompt_cache.py
│       │   ├── policy.py
│       │   ├── embedders.py
│       │   ├── redis_exact_cache_backend.py
│       │   └── redis_semantic_cache_backend.py
│       ├── routing/                 # pure functions; no I/O
│       │   ├── rules.py             # is_matching_rule
│       │   ├── selection.py         # weighted entry-target pick
│       │   ├── chain.py             # build attempt chain
│       │   ├── aliases.py           # ResolvedTarget + resolve_aliases
│       │   └── resolver.py          # high-level resolve_attempt_chain (the public API)
│       └── engine/                  # one attempt; returns a typed verdict
│           ├── adaptor.py           # ProviderAdaptor (provider→gateway streaming, unchanged)
│           ├── verdict.py           # CompleteSuccess | StreamingSuccess | Abort | Failover tagged union
│           └── executor.py          # Owns each attempt to a provider endpoint
│
├── tests/
├── pyproject.toml
└── uv.lock
```

## Development

This project uses `uv` for dependency management.

Synchronize the environment and install dependencies with:

```sh
uv sync
```

For local development, copy `.env.example` to `.env` and use it for gateway settings only.
Keep AWS credentials out of `.env`; configure them through the standard AWS SDK credential chain instead,
for example with `aws configure --profile gw` and `export AWS_PROFILE=gw`.

Populate `API_TOKEN_HASHES`, `DASHBOARD_USERNAME`, and `DASHBOARD_PASSWORD_HASH` in `.env`.
`GET /health` is public, `POST /v1/chat/completions` requires a bearer token shaped like
`gw_<token-id>_<random-secret>`, and the dashboard and config routes require HTTP Basic Auth.

## Running the Service

Start the development server:

```sh
export AWS_PROFILE=gw
uv run uvicorn gateway.main:app --reload
```

## Running tests

Running the tests:
```sh
uv run pytest
```

## Tooling

### Linting and Formatting

The repository uses Ruff for:

- linting
- formatting
- import sorting

Run manually with:

```sh
uv run ruff check .
uv run ruff format .
```

### Type Checking

Mypy is used for static type checking.

Run manually with:

```sh
uv run mypy .
```

### Git Hooks

The repository uses pre-commit hooks to automatically run checks before commits.

Install hooks from the repository root:

```sh
uv run pre-commit install
```

Run all hooks manually:

```sh
uv run pre-commit run --all-files
```

The root hook also runs the dashboard ESLint check when dashboard JavaScript or
TypeScript files change. Install dashboard dependencies with `npm ci` in `../dashboard`
before running all hooks.

### Routing and cooldown

When an LLM model returns a 429 "Too Many Requests" error, the gateway will add a key that
includes both the provider and model to a Redis cache with a TTL of at least 60 seconds.
During the duration of the TTL, the gateway will not send any requests to that provider+model.
Hence, the duration of the TTL is a cooldown period.
