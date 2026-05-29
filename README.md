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
- Node.js / npm
- React / Vite
- Ruff
- ESLint
- Mypy
- pre-commit

## Development Setup

Please do not forget to change your IDE's settings to allow some hidden folders
to appear in the file explorer (specifically .git and .github). In VSCode you can
search for "Files exclude" patterns in your settings and remove the relevant patterns.

Install backend dependencies:

```sh
cd gateway
uv sync
```

Install dashboard dependencies:

```sh
cd dashboard
npm ci
```

Install git hooks from the repository root:

```sh
uv run pre-commit install
```

Run all checks manually (by default the pre-commit hook will only
run on committed files):

```sh
uv run pre-commit run --all-files
```

The hook runs Python checks, Terraform formatting/validation, and
`npm --prefix dashboard run lint` for dashboard JavaScript/TypeScript changes.

Please follow the `ticket-number/contributer-initials/title` convention to name branches.

This repository follows the trunk branching methodology.

## Running the Gateway

For local gateway development:

1. Copy `gateway/.env.example` to `gateway/.env`.
2. Use `gateway/.env` for gateway settings only, such as `CACHE_*`, `AWS_REGION`, and `LOG_LEVEL`.
3. Configure AWS credentials through the standard AWS SDK credential chain, for example with the `gw` profile documented below.
4. Export `AWS_PROFILE=gw` before starting the service if you want to use that profile explicitly.

```sh
cd gateway
export AWS_PROFILE=gw
uv run uvicorn gateway.main:app --reload --app-dir src
```

## Routing Config Dashboard

The dashboard edits the routing config stored in AWS Systems Manager Parameter Store.
The running FastAPI process loads config once at startup and keeps using that active
in-memory config until the process is restarted.

`GET /config` returns:

```json
{
  "config": {},
  "reload_required": false
}
```

When the dashboard saves changes, `POST /config` validates the new config and writes it
to Parameter Store. It does not replace the already-loaded FastAPI context config. If the
persisted config differs from the active config, the endpoint returns
`"reload_required": true`.

To apply saved config changes to a running ECS service, manually force a new deployment:

```sh
aws ecs update-service --profile gw \
  --cluster gw-<your-name>-cluster \
  --service gw-<your-name>-gateway-service \
  --force-new-deployment
```

## Infrastructure (Terraform)

The AWS infrastructure lives in `infra/`. Each developer can spin up their own namespaced environment by passing their name as a Terraform variable.

### Prerequisites

- Terraform >= 1.15
- AWS CLI installed and configured with a `gw` profile

An AWS profile is a named set of credentials stored locally on your machine. To create the `gw` profile:

```sh
aws configure --profile gw
```

You will be prompted for:
- **AWS Access Key ID** — get this from the AWS IAM console
- **AWS Secret Access Key** — get this from the AWS IAM console
- **Default region** — enter `us-east-1`
- **Default output format** — leave blank or enter `json`

To verify the profile is set up correctly:

```sh
aws configure list --profile gw
```

### Before your first `terraform apply`

**1. Generate a cache auth token**

ElastiCache requires an AUTH token (password) that you create yourself. Generate one:

```sh
openssl rand -hex 32
```

Keep the output — you'll need it in the next step and again when populating Parameter Store.

**2. Provide the token to Terraform**

Either create an `infra/terraform.tfvars` file (make sure it's git-ignored):

```hcl
cache_auth_token = "your-generated-token"
```

Or export it as an environment variable:

```sh
export TF_VAR_cache_auth_token="your-generated-token"
```

**3. Apply**

```sh
cd infra
terraform init
terraform plan -var="owner=<your-name>"
terraform apply -var="owner=<your-name>"
```

### After apply: populate Parameter Store

Terraform automatically populates `cache/endpoint`, `cache/port`, and
`routing/config`. The routing config parameter is seeded from
`gateway/src/gateway/config.json`; later dashboard edits are intentionally ignored by
Terraform so a future `terraform apply` does not overwrite saved UI changes.

The following must be populated manually as they are either secrets or reference
resources outside this Terraform stack:

```sh
aws ssm put-parameter --name /gw-<your-name>/cache/auth-token \
  --value "<your-generated-token>" --type SecureString

aws ssm put-parameter --name /gw-<your-name>/bedrock/primary-chat-model \
  --value "us.anthropic.claude-3-5-haiku-20241022-v1:0" --type String
```

### Tearing down

To destroy all Terraform-managed infrastructure for your environment:

```sh
cd infra
terraform destroy -var="owner=<your-name>"
```

Note: the two manually created Parameter Store entries (`cache/auth-token` and `bedrock/primary-chat-model`) are not managed by Terraform and must be deleted manually if you want a clean slate:

```sh
aws ssm delete-parameter --name /gw-<your-name>/cache/auth-token
aws ssm delete-parameter --name /gw-<your-name>/bedrock/primary-chat-model
```

## Documentation

Additional documentation can be found in:

- `gateway/README.md`
- `docs/`

# Amazon Bedrock `model_id`
To find the Amazon Bedrock model_id value, click on the model you want to use here: https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html
