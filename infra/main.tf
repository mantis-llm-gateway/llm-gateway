provider "aws" {
  region  = "us-east-1"
  profile = "gw"
}


variable "owner" {
  type        = string
  description = "Developer name used to namespace resources (e.g. riz, sam, rey)"
  default     = "admin"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.owner))
    error_message = "owner must be 2-21 chars: lowercase letters, numbers, hyphens; start with a letter."
  }
}
variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public Subnet CIDR Values"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}


variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private Subnet CIDR Values"
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

data "aws_region" "current" {}

data "aws_availability_zones" "available" {}

data "aws_caller_identity" "current" {}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name    = "gateway-vpc"
    Project = "llm_gateway"
  }
}

resource "aws_subnet" "public_subnets" {
  count             = length(var.public_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = element(var.public_subnet_cidrs, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name    = "gw-subnet-public-${data.aws_availability_zones.available.names[count.index]}"
    Project = "llm_gateway"
  }
}

resource "aws_subnet" "private_subnets" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = element(var.private_subnet_cidrs, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name    = "gw-subnet-private-${data.aws_availability_zones.available.names[count.index]}"
    Project = "llm_gateway"
  }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name    = "internet_gateway"
    Project = "llm_gateway"
  }

}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = [for rt in aws_route_table.private_rt : rt.id]

  tags = {
    Name    = "vpc-endpoint-s3"
    Project = "llm_gateway"
  }
}

resource "aws_route_table_association" "public_rta" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.public_subnets[count.index].id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "private_rta" {
  count          = length(var.private_subnet_cidrs)
  subnet_id      = aws_subnet.private_subnets[count.index].id
  route_table_id = aws_route_table.private_rt[count.index].id
}


resource "aws_route_table" "private_rt" {
  count  = length(var.private_subnet_cidrs)
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.public[count.index].id
  }

  tags = {
    Name    = "private_route_table-${data.aws_availability_zones.available.names[count.index]}"
    Project = "llm_gateway"
  }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
  tags = {
    Name    = "public_route_table"
    Project = "llm_gateway"
  }
}

resource "aws_eip" "nat" {
  count  = length(var.public_subnet_cidrs)
  domain = "vpc"

  tags = {
    Name    = "nat-eip-${data.aws_availability_zones.available.names[count.index]}"
    Project = "llm_gateway"
  }
}

resource "aws_nat_gateway" "public" {
  count         = length(var.public_subnet_cidrs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public_subnets[count.index].id

  tags = {
    Name    = "nat-gateway-${data.aws_availability_zones.available.names[count.index]}"
    Project = "llm_gateway"
  }

  depends_on = [aws_internet_gateway.gw]
}

resource "aws_lb" "gw-alb" {
  name               = "gw-${var.owner}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [for subnet in aws_subnet.public_subnets : subnet.id]

  enable_deletion_protection = false

  tags = {
    Name    = "gw-alb"
    Project = "llm_gateway"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.gw-alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.gw-tg.arn
  }
}

resource "aws_security_group" "alb_sg" {
  name   = "gw-${var.owner}-alb-sg"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group_rule" "alb_egress" {
  type                     = "egress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.fargate_sg.id
  security_group_id        = aws_security_group.alb_sg.id
  description              = "Forward to ECS tasks"
}

resource "aws_security_group" "fargate_sg" {
  name        = "gw-${var.owner}-fargate-sg"
  description = "Fargate tasks for LLM gateway"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group_rule" "fargate_ingress" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb_sg.id
  security_group_id        = aws_security_group.fargate_sg.id
  description              = "From ALB only"
}

resource "aws_security_group_rule" "fargate_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.fargate_sg.id
}

resource "aws_security_group_rule" "http_in" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb_sg.id
  description       = "Public HTTP from the internet (dev only)"
}

resource "aws_lb_target_group" "gw-tg" {
  name        = "gw-${var.owner}-gateway-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_ecr_repository" "gateway" {
  name                 = "gw-${var.owner}/gateway"
  image_tag_mutability = "MUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_ecr_lifecycle_policy" "gateway" {
  repository = aws_ecr_repository.gateway.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images, prune older"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

resource "aws_ssm_parameter" "cache_endpoint" {
  name  = "/gw-${var.owner}/cache/endpoint"
  type  = "String"
  value = aws_elasticache_replication_group.cache.primary_endpoint_address

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_ssm_parameter" "cache_port" {
  name  = "/gw-${var.owner}/cache/port"
  type  = "String"
  value = tostring(aws_elasticache_replication_group.cache.port)

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_bedrock_guardrail" "gw" {
  name        = "gw-${var.owner}-guardrails"
  description = "LLM gateway content + PII + prompt injection guardrail"

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "financial-advice"
      definition = "Specific recommendations for buying, selling, or holding financial instruments. Does not include general financial education or definitions of financial concepts."
      type       = "DENY"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "UK_UNIQUE_TAXPAYER_REFERENCE_NUMBER"
      action = "ANONYMIZE"
    }
  }

  blocked_input_messaging   = "This request was blocked by content policy"
  blocked_outputs_messaging = "This request was blocked by content policy"

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_bedrock_guardrail_version" "gw" {
  guardrail_arn = aws_bedrock_guardrail.gw.guardrail_arn
  description   = "v1 - Initial version"
}

resource "aws_ssm_parameter" "bedrock_guardrail_id" {
  name  = "/gw-${var.owner}/bedrock/guardrail-id"
  type  = "String"
  value = aws_bedrock_guardrail.gw.guardrail_id

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_cloudwatch_log_group" "gw" {
  name              = "/ecs/gw-${var.owner}/gateway"
  retention_in_days = 14

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_ecs_cluster" "gw" {
  name = "gw-${var.owner}-cluster"

  tags = {
    Name    = "gw-${var.owner}-cluster"
    Project = "llm_gateway"
  }
}

resource "aws_ecs_task_definition" "gw" {
  family                   = "gw-${var.owner}-gateway"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name      = "gateway"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.region}.amazonaws.com/gw-${var.owner}/gateway:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
      name          = "gateway-http"
      appProtocol   = "http"
    }]

    environment = [
      { name = "PORT", value = "8000" },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "AWS_REGION", value = data.aws_region.current.region },
      { name = "BEDROCK_GUARDRAIL_VERSION", value = "1" },
      { name = "BEDROCK_EMBEDDING_MODEL", value = "amazon.titan-embed-text-v2:0" }
    ]

    secrets = [
      { name = "CACHE_ENDPOINT", valueFrom = aws_ssm_parameter.cache_endpoint.arn },
      { name = "CACHE_PORT", valueFrom = aws_ssm_parameter.cache_port.arn },
      { name = "CACHE_AUTH_TOKEN", valueFrom = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter/gw-${var.owner}/cache/auth-token" },
      { name = "BEDROCK_GUARDRAIL_ID", valueFrom = aws_ssm_parameter.bedrock_guardrail_id.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/gw-${var.owner}/gateway"
        "awslogs-region"        = data.aws_region.current.region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_iam_role" "ecs_execution_role" {
  name = "gw-${var.owner}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "gw-${var.owner}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "gw-${var.owner}-ecs-task-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeBedrockModels"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:inference-profile/*"
        ]
      },
      {
        Sid      = "ApplyGuardrail"
        Effect   = "Allow"
        Action   = "bedrock:ApplyGuardrail"
        Resource = "arn:aws:bedrock:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:guardrail/*"
      },
      {
        Sid    = "BedrockMarketplaceSubscriptions"
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe",
          "aws-marketplace:Unsubscribe"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_execution_ssm_policy" {
  name = "gw-${var.owner}-ecs-execution-ssm-policy"
  role = aws_iam_role.ecs_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadGatewayParameters"
        Effect = "Allow"
        Action = [
          "ssm:GetParameters",
          "ssm:GetParameter",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter/gw-${var.owner}/*"
      },
      {
        Sid      = "DecryptSecureStrings"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${data.aws_region.current.region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

variable "cache_auth_token" {
  type        = string
  description = "AUTH token for ElastiCache"
  sensitive   = true
}

resource "aws_security_group" "cache_sg" {
  name        = "gw-${var.owner}-cache-sg"
  description = "ElastiCache Redis for LLM gateway"
  vpc_id      = aws_vpc.main.id

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_security_group_rule" "cache_ingress" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.fargate_sg.id
  security_group_id        = aws_security_group.cache_sg.id
  description              = "From Fargate tasks only"
}

resource "aws_elasticache_subnet_group" "cache" {
  name        = "gw-${var.owner}-cache-subnet-group"
  description = "Private subnets for LLM gateway cache"
  subnet_ids  = [for subnet in aws_subnet.private_subnets : subnet.id]

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_elasticache_parameter_group" "cache" {
  name   = "gw-${var.owner}-cache-params"
  family = "valkey9"

  parameter {
    name  = "reserved-memory-percent"
    value = "50"
  }

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lfu"
  }

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_elasticache_replication_group" "cache" {
  replication_group_id       = "gw-${var.owner}-cache"
  description                = "LLM gateway shared cache (exact, semantic, rate-limit, circuit-breaker)"
  engine                     = "valkey"
  engine_version             = "9.0"
  node_type                  = "cache.t4g.micro"
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

  tags = {
    Project = "llm_gateway"
  }
}

resource "aws_ecs_service" "gw" {
  name            = "gw-${var.owner}-gateway-service"
  cluster         = aws_ecs_cluster.gw.id
  task_definition = aws_ecs_task_definition.gw.arn
  desired_count   = 0
  depends_on      = [aws_lb_listener.http]

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    base              = 0
    weight            = 1
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = false
  }

  health_check_grace_period_seconds = 30
  enable_ecs_managed_tags           = true
  propagate_tags                    = "NONE"

  network_configuration {
    subnets          = [for subnet in aws_subnet.private_subnets : subnet.id]
    security_groups  = [aws_security_group.fargate_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.gw-tg.arn
    container_name   = "gateway"
    container_port   = 8000
  }

  tags = {
    Project = "llm_gateway"
  }
}
