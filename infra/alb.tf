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
    type             = "forward"
    target_group_arn = aws_lb_target_group.gw-tg.arn
  }
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
