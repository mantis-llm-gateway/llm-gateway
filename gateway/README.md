# Gateway Service

Gateway component.

## Project Structure

```text
gateway/
├── src/
│   └── gateway/
│       ├── __init__.py
│       └── main.py
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

Copy `.env.example` to `.env` and fill in any local-specific values. The defaults
are fine for running against a local Redis (`docker run --rm -d -p 6379:6379 redis:7`).

This project uses `uv` for dependency management.

## Running the Service

Start the development server:

```sh
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

### Routing and cooldown

When an LLM model returns a 429 "Too Many Requests" error, the gateway will add a key that
includes both the provider and model to a Redis cache with a TTL of at least 60 seconds.
During the duration of the TTL, the gateway will not send any requests to that provider+model.
Hence, the duration of the TTL is a cooldown period.