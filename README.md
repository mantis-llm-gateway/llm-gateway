# LLM Gateway

TODO: description of the repo

## Repository Structure

```text
llm-gateway/
├── dashboard/    # Frontend UI
├── docs/         # Architecture and technical documentation
├── gateway/      # FastAPI backend service
├── infra/        # Terraform / infrastructure code
└── scripts/      # Infrastructure bootstrap and deployment scripts
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
  --cluster gw-<namespace>-cluster \
  --service gw-<namespace>-gateway-service \
  --force-new-deployment
```

### Dashboard static files

Terraform creates a private S3 bucket for dashboard build files and injects its
name into the gateway task as `DASHBOARD_S3_BUCKET`. The gateway serves `GET /`
and dashboard asset paths by reading objects from that bucket; API routes such as
`/health`, `/config`, and `/v1/chat/completions` still resolve before the
dashboard fallback.

The deployment script builds the dashboard and uploads the generated files to the
Terraform-managed bucket:

```sh
./scripts/deploy.sh
```

## Infrastructure (Terraform)

The AWS infrastructure lives in `infra/`. Terraform files are split by concern but
still form one root module. Each deployment has an `owner` tag and a `namespace` used
in resource names and SSM paths.

### Prerequisites

- Terraform >= 1.15
- AWS CLI installed and configured with a `gw` profile
- Docker
- Node.js / npm

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

### Bootstrap remote state

Terraform state contains sensitive values, including the plaintext ElastiCache auth
token. Bootstrap a separate private, encrypted, versioned S3 bucket before applying
the application infrastructure:

```sh
./scripts/bootstrap_state_bucket.sh <namespace>
```

Set `AWS_PROFILE` or `AWS_REGION` when using values other than the script defaults
of `gw` and `us-east-1`.

The script prints the matching `terraform init` command. Run that command from the
repository root. It includes `-migrate-state`, so it also migrates an existing local
state file when adopting the remote backend.

The state bucket is intentionally created outside the application Terraform module.
Running `terraform destroy` for the application will not destroy the state bucket.

### Configure Terraform

ElastiCache requires an AUTH token. Generate one:

```sh
openssl rand -hex 32
```

Create `infra/terraform.tfvars`; this file is git-ignored:

```hcl
owner            = "<your-name>"
namespace        = "<environment-name>"
cache_auth_token = "your-generated-token"
```

The token is stored as an SSM `SecureString` for the running service, but Terraform
must also provide it to ElastiCache. As a result, it remains present in Terraform
state. Restrict access to the bootstrapped state bucket.

Variables can also be passed through `TF_VAR_*` environment variables:

```sh
export TF_VAR_owner="<your-name>"
export TF_VAR_namespace="<environment-name>"
export TF_VAR_cache_auth_token="your-generated-token"
```

Optional variables include `aws_region`, `aws_profile`, `ecs_desired_count`,
`container_image_tag`, `log_retention_days`, `cache_node_type`,
`allowed_http_cidrs`, and the public and private subnet CIDRs.

### Existing local deployments

Before the first plan or apply after upgrading an environment created by the original
Terraform file:

1. Set `namespace` to the previous `owner` value to preserve resource names.
2. Run the bootstrap script and its printed `terraform init -migrate-state` command.
3. Import the manually created cache auth parameter so Terraform can manage it:

```sh
terraform -chdir=infra import \
  aws_ssm_parameter.cache_auth_token \
  /gw-<namespace>/cache/auth-token
```

Set `cache_auth_token` to the existing ElastiCache token before applying. Importing
the parameter adopts it without overwriting its value. Fresh deployments can skip
this migration step.

### Apply

```sh
terraform -chdir=infra plan
terraform -chdir=infra apply
```

The initial ECS desired count defaults to `0`, allowing infrastructure creation
before an image exists.

### Deploy

After applying the infrastructure, run:

```sh
./scripts/deploy.sh
```

The deploy script also reads `AWS_PROFILE` and `AWS_REGION`, defaulting to `gw` and
`us-east-1`.

The script builds and uploads dashboard files, builds and pushes the ARM64 gateway
image to the Terraform-created ECR repository, and scales the ECS service to one
task. Terraform ignores subsequent `desired_count` changes so a later apply will not
scale the deployed service back to zero.

Terraform exposes useful deployment details:

```sh
terraform -chdir=infra output
```

### Parameter Store

Terraform populates `cache/auth-token`, `cache/endpoint`, `cache/port`,
`bedrock/guardrail-id`, and `routing/config`. The routing config is seeded from
`gateway/src/gateway/config.json`; later dashboard edits are intentionally ignored by
Terraform so a future `terraform apply` does not overwrite saved UI changes.

### Tearing down

To destroy all Terraform-managed infrastructure for your environment:

```sh
terraform -chdir=infra destroy
```

The separately bootstrapped state bucket remains in place intentionally.

## Documentation

Additional documentation can be found in:

- `gateway/README.md`
- `docs/`

# Amazon Bedrock `model_id`
To find the Amazon Bedrock model_id value, click on the model you want to use here: https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html
