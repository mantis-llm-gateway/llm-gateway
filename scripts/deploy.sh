#!/usr/bin/env bash
set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-gw}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$ROOT_DIR/infra"
DASHBOARD_DIST="$ROOT_DIR/gateway/src/gateway/dashboard_dist"

for command in aws docker npm terraform; do
  command -v "$command" >/dev/null || {
    printf '%s is required.\n' "$command" >&2
    exit 1
  }
done

terraform_output() {
  terraform -chdir="$TERRAFORM_DIR" output -raw "$1"
}

AWS=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
ECR_REPOSITORY_URL="$(terraform_output ecr_repository_url)"
GATEWAY_CONTAINER_IMAGE="$(terraform_output gateway_container_image)"
DASHBOARD_BUCKET_NAME="$(terraform_output dashboard_bucket_name)"
ECS_CLUSTER_NAME="$(terraform_output ecs_cluster_name)"
ECS_SERVICE_NAME="$(terraform_output ecs_service_name)"
ALB_DNS_NAME="$(terraform_output alb_dns_name)"
ECR_REGISTRY="${ECR_REPOSITORY_URL%%/*}"

printf 'Building dashboard...\n'
npm --prefix "$ROOT_DIR/dashboard" run build

printf 'Uploading dashboard files to s3://%s/...\n' "$DASHBOARD_BUCKET_NAME"
"${AWS[@]}" s3 sync "$DASHBOARD_DIST/" "s3://$DASHBOARD_BUCKET_NAME/" --delete

printf 'Logging in to ECR...\n'
"${AWS[@]}" ecr get-login-password |
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

printf 'Building gateway image %s...\n' "$GATEWAY_CONTAINER_IMAGE"
docker build --platform linux/arm64 --tag "$GATEWAY_CONTAINER_IMAGE" "$ROOT_DIR/gateway"

printf 'Pushing gateway image...\n'
docker push "$GATEWAY_CONTAINER_IMAGE"

printf 'Starting ECS service...\n'
"${AWS[@]}" ecs update-service \
  --cluster "$ECS_CLUSTER_NAME" \
  --service "$ECS_SERVICE_NAME" \
  --desired-count 1 \
  --force-new-deployment >/dev/null

printf '\nDeployment started: http://%s\n' "$ALB_DNS_NAME"
