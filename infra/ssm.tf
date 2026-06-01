resource "aws_ssm_parameter" "cache_endpoint" {
  name  = "${local.ssm_parameter_prefix}/cache/endpoint"
  type  = "String"
  value = aws_elasticache_replication_group.cache.primary_endpoint_address
}

resource "aws_ssm_parameter" "cache_port" {
  name  = "${local.ssm_parameter_prefix}/cache/port"
  type  = "String"
  value = tostring(aws_elasticache_replication_group.cache.port)
}

resource "aws_ssm_parameter" "cache_auth_token" {
  name  = "${local.ssm_parameter_prefix}/cache/auth-token"
  type  = "SecureString"
  value = var.cache_auth_token
}

resource "aws_ssm_parameter" "routing_config" {
  name  = local.routing_config_parameter_name
  type  = "String"
  value = file("${path.module}/../gateway/src/gateway/config.json")

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "bedrock_guardrail_id" {
  name  = "${local.ssm_parameter_prefix}/bedrock/guardrail-id"
  type  = "String"
  value = aws_bedrock_guardrail.gw.guardrail_id
}
