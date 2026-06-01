#!/usr/bin/env bash
set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-gw}"
AWS_REGION="${AWS_REGION:-us-east-1}"
NAMESPACE="${1:-}"

if [[ ! "$NAMESPACE" =~ ^[a-z][a-z0-9-]{1,20}$ ]]; then
  printf 'Usage: %s <namespace>\n' "$0" >&2
  printf 'namespace must be 2-21 chars: lowercase letters, numbers, hyphens; start with a letter.\n' >&2
  exit 1
fi

command -v aws >/dev/null || {
  printf 'aws CLI is required.\n' >&2
  exit 1
}

AWS=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text)"
BUCKET_NAME="gw-${NAMESPACE}-${ACCOUNT_ID}-${AWS_REGION}-terraform-state"

if "${AWS[@]}" s3api head-bucket --bucket "$BUCKET_NAME" >/dev/null 2>&1; then
  printf 'Using existing state bucket: %s\n' "$BUCKET_NAME"
else
  printf 'Creating state bucket: %s\n' "$BUCKET_NAME"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    "${AWS[@]}" s3api create-bucket --bucket "$BUCKET_NAME" >/dev/null
  else
    "${AWS[@]}" s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --create-bucket-configuration "LocationConstraint=$AWS_REGION" >/dev/null
  fi
fi

"${AWS[@]}" s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

"${AWS[@]}" s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

"${AWS[@]}" s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'

printf '\nState bucket is ready. Initialize Terraform with:\n\n'
printf 'terraform -chdir=infra init -migrate-state \\\n'
printf '  -backend-config="bucket=%s" \\\n' "$BUCKET_NAME"
printf '  -backend-config="key=%s/terraform.tfstate" \\\n' "$NAMESPACE"
printf '  -backend-config="region=%s" \\\n' "$AWS_REGION"
printf '  -backend-config="profile=%s" \\\n' "$AWS_PROFILE"
printf '  -backend-config="encrypt=true" \\\n'
printf '  -backend-config="use_lockfile=true"\n'
