# LLM Gateway

TODO: description of the repo

## Repository Structure

```text
llm-gateway/
├── dashboard/    # Frontend UI
├── docs/         # Architecture and technical documentation
├── gateway/      # FastAPI backend service
└── infra/        # Terraform / infrastructure code
```

## Technology Stack

- Python 3.12
- FastAPI
- uv
- Ruff
- Mypy
- pre-commit

## Development Setup

Install backend dependencies:

```sh
cd gateway
uv sync
```

Install git hooks from the repository root:

```sh
uv run pre-commit install
```

Run all checks manually:

```sh
uv run pre-commit run --all-files
```

Please follow the `ticket-number/contributer-initials/title` convention to name branches.

This repository follows the trunk branching methodology.

## Running the Gateway

```sh
cd gateway
uv run uvicorn gateway.main:app --reload --app-dir src
```

## Documentation

Additional documentation can be found in:

- `gateway/README.md`
- `docs/`