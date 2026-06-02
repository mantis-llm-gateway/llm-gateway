resource "aws_lb" "gw-alb" {
  name               = "gw-${var.namespace}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [for subnet in aws_subnet.public_subnets : subnet.id]

  enable_deletion_protection = false

  tags = {
    Name = "gw-alb"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.gw-alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = var.enable_https ? "redirect" : "forward"
    target_group_arn = var.enable_https ? null : aws_lb_target_group.gw-tg.arn

    dynamic "redirect" {
      for_each = var.enable_https ? [true] : []

      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.gw-alb.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.acm_certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-Res-2021-06"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.gw-tg.arn
  }

  lifecycle {
    precondition {
      condition     = var.acm_certificate_arn != null && var.gateway_domain_name != null
      error_message = "acm_certificate_arn and gateway_domain_name must be set when enable_https is true."
    }
  }
}

moved {
  from = aws_lb_listener.https
  to   = aws_lb_listener.https[0]
}

resource "aws_lb_target_group" "gw-tg" {
  name        = "gw-${var.namespace}-gateway-tg"
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
