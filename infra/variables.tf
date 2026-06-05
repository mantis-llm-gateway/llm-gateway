variable "owner" {
  type        = string
  description = "Person responsible for the deployment"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.owner))
    error_message = "owner must be 2-21 chars: lowercase letters, numbers, hyphens; start with a letter."
  }
}

variable "namespace" {
  type        = string
  description = "Namespace used to isolate deployment resources, such as dev or staging"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.namespace))
    error_message = "namespace must be 2-21 chars: lowercase letters, numbers, hyphens; start with a letter."
  }
}

variable "aws_region" {
  type        = string
  description = "AWS region where resources are deployed"
  default     = "us-east-1"
}

variable "aws_profile" {
  type        = string
  description = "Local AWS CLI profile used by Terraform"
  default     = "gw"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDR values"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private subnet CIDR values"
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "cache_auth_token" {
  type        = string
  description = "AUTH token for ElastiCache"
  sensitive   = true
}

variable "ecs_desired_count" {
  type        = number
  description = "Initial ECS task count; deploy.sh scales the service to one task"
  default     = 0
}

variable "container_image_tag" {
  type        = string
  description = "Gateway container image tag"
  default     = "latest"
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention period"
  default     = 14
}

variable "cache_node_type" {
  type        = string
  description = "ElastiCache node type"
  default     = "cache.t4g.micro"
}

variable "enable_https" {
  type        = bool
  description = "Whether to expose an HTTPS listener and redirect public HTTP traffic to HTTPS"
  default     = false
}

variable "acm_certificate_arn" {
  type        = string
  description = "ARN of an ACM certificate for the public gateway hostname"
  default     = null

  validation {
    condition     = var.acm_certificate_arn == null || can(regex("^arn:[^:]+:acm:[^:]+:[0-9]{12}:certificate/.+$", var.acm_certificate_arn))
    error_message = "acm_certificate_arn must be an ACM certificate ARN."
  }
}

variable "gateway_domain_name" {
  type        = string
  description = "Public DNS hostname covered by the ACM certificate, such as gateway.example.com"
  default     = null

  validation {
    condition     = var.gateway_domain_name == null || can(regex("^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$", var.gateway_domain_name))
    error_message = "gateway_domain_name must be a valid DNS hostname."
  }
}

variable "allowed_http_cidrs" {
  type        = list(string)
  description = "CIDR ranges allowed to access the public HTTP and HTTPS listeners"
  default     = ["0.0.0.0/0"]
}

locals {
  ssm_parameter_prefix                   = "/gw-${var.namespace}"
  routing_config_parameter_name          = "${local.ssm_parameter_prefix}/routing/config"
  api_token_hashes_parameter_name        = "${local.ssm_parameter_prefix}/auth/api-token-hashes"
  dashboard_username_parameter_name      = "${local.ssm_parameter_prefix}/auth/dashboard-username"
  dashboard_password_hash_parameter_name = "${local.ssm_parameter_prefix}/auth/dashboard-password-hash"
  api_token_hashes_parameter_arn         = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${local.api_token_hashes_parameter_name}"
  dashboard_username_parameter_arn       = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${local.dashboard_username_parameter_name}"
  dashboard_password_hash_parameter_arn  = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${local.dashboard_password_hash_parameter_name}"
  dashboard_bucket_name                  = "gw-${var.namespace}-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}-dashboard"
  gateway_container_image                = "${aws_ecr_repository.gateway.repository_url}:${var.container_image_tag}"
  gateway_url                            = var.enable_https ? (var.gateway_domain_name != null ? "https://${var.gateway_domain_name}" : null) : "http://${aws_lb.gw-alb.dns_name}"
}
