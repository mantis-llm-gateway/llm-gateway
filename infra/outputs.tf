output "ecr_repository_url" {
  description = "ECR repository where gateway images should be pushed"
  value       = aws_ecr_repository.gateway.repository_url
}

output "gateway_container_image" {
  description = "Gateway image reference used by the ECS task definition"
  value       = local.gateway_container_image
}

output "dashboard_bucket_name" {
  description = "S3 bucket where dashboard build files should be uploaded"
  value       = aws_s3_bucket.dashboard.bucket
}

output "alb_dns_name" {
  description = "Public ALB DNS name"
  value       = aws_lb.gw-alb.dns_name
}

output "alb_zone_id" {
  description = "Canonical hosted zone ID for a Route 53 alias to the ALB"
  value       = aws_lb.gw-alb.zone_id
}

output "gateway_url" {
  description = "Public URL for the gateway"
  value       = local.gateway_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name used by deployment scripts"
  value       = aws_ecs_cluster.gw.name
}

output "ecs_service_name" {
  description = "ECS service name used by deployment scripts"
  value       = aws_ecs_service.gw.name
}

output "ssm_parameter_prefix" {
  description = "Prefix for gateway runtime configuration parameters"
  value       = local.ssm_parameter_prefix
}

output "cache_endpoint_parameter_name" {
  description = "SSM parameter containing the cache endpoint"
  value       = aws_ssm_parameter.cache_endpoint.name
}

output "cache_port_parameter_name" {
  description = "SSM parameter containing the cache port"
  value       = aws_ssm_parameter.cache_port.name
}

output "bedrock_guardrail_id_parameter_name" {
  description = "SSM parameter containing the Bedrock guardrail ID"
  value       = aws_ssm_parameter.bedrock_guardrail_id.name
}
