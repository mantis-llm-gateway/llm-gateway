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

variable "allowed_http_cidrs" {
  type        = list(string)
  description = "CIDR ranges allowed to access the public HTTP listener"
  default     = ["0.0.0.0/0"]
}

locals {
  ssm_parameter_prefix          = "/gw-${var.namespace}"
  routing_config_parameter_name = "${local.ssm_parameter_prefix}/routing/config"
  dashboard_bucket_name         = "gw-${var.namespace}-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}-dashboard"
  gateway_container_image       = "${aws_ecr_repository.gateway.repository_url}:${var.container_image_tag}"
}
