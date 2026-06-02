resource "aws_cloudwatch_log_group" "gw" {
  name              = "/ecs/gw-${var.namespace}/gateway"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "gw" {
  name = "gw-${var.namespace}-cluster"

  tags = {
    Name = "gw-${var.namespace}-cluster"
  }
}

resource "aws_ecs_task_definition" "gw" {
  family                   = "gw-${var.namespace}-gateway"
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
    image     = local.gateway_container_image
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
      { name = "PARAMETER_STORE_CONFIG_KEY", value = aws_ssm_parameter.routing_config.name },
      { name = "DASHBOARD_S3_BUCKET", value = aws_s3_bucket.dashboard.bucket },
      { name = "BEDROCK_GUARDRAIL_VERSION", value = "1" },
      { name = "BEDROCK_EMBEDDING_MODEL", value = "amazon.titan-embed-text-v2:0" }
    ]

    secrets = [
      { name = "CACHE_ENDPOINT", valueFrom = aws_ssm_parameter.cache_endpoint.arn },
      { name = "CACHE_PORT", valueFrom = aws_ssm_parameter.cache_port.arn },
      { name = "CACHE_AUTH_TOKEN", valueFrom = aws_ssm_parameter.cache_auth_token.arn },
      { name = "BEDROCK_GUARDRAIL_ID", valueFrom = aws_ssm_parameter.bedrock_guardrail_id.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.gw.name
        "awslogs-region"        = data.aws_region.current.region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "gw" {
  name            = "gw-${var.namespace}-gateway-service"
  cluster         = aws_ecs_cluster.gw.id
  task_definition = aws_ecs_task_definition.gw.arn
  desired_count   = var.ecs_desired_count
  depends_on      = [aws_lb_listener.http, aws_lb_listener.https]

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

  lifecycle {
    ignore_changes = [desired_count]
  }
}
