resource "aws_security_group" "alb_sg" {
  name   = "gw-${var.namespace}-alb-sg"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group_rule" "http_in" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = var.allowed_http_cidrs
  security_group_id = aws_security_group.alb_sg.id
  description       = "Allowed HTTP traffic"
}

resource "aws_security_group_rule" "https_in" {
  count = var.enable_https ? 1 : 0

  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.allowed_http_cidrs
  security_group_id = aws_security_group.alb_sg.id
  description       = "Allowed HTTPS traffic"
}

moved {
  from = aws_security_group_rule.https_in
  to   = aws_security_group_rule.https_in[0]
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
  name        = "gw-${var.namespace}-fargate-sg"
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

resource "aws_security_group" "cache_sg" {
  name        = "gw-${var.namespace}-cache-sg"
  description = "ElastiCache Redis for LLM gateway"
  vpc_id      = aws_vpc.main.id
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
