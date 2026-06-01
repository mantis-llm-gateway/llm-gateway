resource "aws_elasticache_subnet_group" "cache" {
  name        = "gw-${var.namespace}-cache-subnet-group"
  description = "Private subnets for LLM gateway cache"
  subnet_ids  = [for subnet in aws_subnet.private_subnets : subnet.id]
}

resource "aws_elasticache_parameter_group" "cache" {
  name   = "gw-${var.namespace}-cache-params"
  family = "valkey9"

  parameter {
    name  = "reserved-memory-percent"
    value = "50"
  }

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lfu"
  }
}

resource "aws_elasticache_replication_group" "cache" {
  replication_group_id       = "gw-${var.namespace}-cache"
  description                = "LLM gateway shared cache (exact, semantic, rate-limit, circuit-breaker)"
  engine                     = "valkey"
  engine_version             = "9.0"
  node_type                  = var.cache_node_type
  num_cache_clusters         = 1
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.cache.name
  security_group_ids         = [aws_security_group.cache_sg.id]
  parameter_group_name       = aws_elasticache_parameter_group.cache.name
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"
  auth_token                 = var.cache_auth_token
  auto_minor_version_upgrade = true
  snapshot_retention_limit   = 0
  apply_immediately          = true
}
