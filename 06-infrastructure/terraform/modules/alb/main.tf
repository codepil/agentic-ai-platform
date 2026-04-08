# -----------------------------------------------------------------------------
# ALB Module — Main
#
# Creates an internet-facing Application Load Balancer for the Agentic AI
# platform with:
#   • Security group allowing HTTP/HTTPS from the public internet (IPv4 + IPv6)
#   • HTTP → HTTPS redirect listener
#   • HTTPS listener with ACM certificate forwarding to the platform-app TG
#   • WebSocket-aware listener rule with sticky sessions
# -----------------------------------------------------------------------------

locals {
  name_prefix       = "${var.name}-${var.environment}"
  access_logs_enabled = var.access_logs_bucket != ""

  common_tags = merge(
    {
      Module      = "alb"
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

# -----------------------------------------------------------------------------
# Security Group
# -----------------------------------------------------------------------------

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Security group for the ${local.name_prefix} Application Load Balancer. Allows inbound HTTP/HTTPS from the internet."
  vpc_id      = var.vpc_id

  # Allow HTTP from anywhere (IPv4) — redirected to HTTPS by the listener
  ingress {
    description = "HTTP from IPv4"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow HTTP from anywhere (IPv6)
  ingress {
    description      = "HTTP from IPv6"
    from_port        = 80
    to_port          = 80
    protocol         = "tcp"
    ipv6_cidr_blocks = ["::/0"]
  }

  # Allow HTTPS from anywhere (IPv4)
  ingress {
    description = "HTTPS from IPv4"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow HTTPS from anywhere (IPv6)
  ingress {
    description      = "HTTPS from IPv6"
    from_port        = 443
    to_port          = 443
    protocol         = "tcp"
    ipv6_cidr_blocks = ["::/0"]
  }

  # Allow all outbound so the ALB can reach ECS tasks in private subnets
  egress {
    description      = "Allow all outbound traffic"
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# Application Load Balancer
# -----------------------------------------------------------------------------

resource "aws_lb" "this" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"

  security_groups = [aws_security_group.alb.id]
  subnets         = var.public_subnet_ids

  # Prevent accidental deletion; always true in prod via var.deletion_protection
  enable_deletion_protection = var.deletion_protection

  # Drop invalid HTTP headers to prevent request-smuggling attacks
  drop_invalid_header_fields = true

  # Enable IPv6 dual-stack
  ip_address_type = "dualstack"

  # Access logging — only configured when a bucket name is supplied
  dynamic "access_logs" {
    for_each = local.access_logs_enabled ? [1] : []
    content {
      bucket  = var.access_logs_bucket
      prefix  = "${local.name_prefix}-alb"
      enabled = true
    }
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb" })
}

# -----------------------------------------------------------------------------
# Target Group — platform-app (Java Spring Boot, port 8080)
# -----------------------------------------------------------------------------

resource "aws_lb_target_group" "platform_app" {
  name        = "${local.name_prefix}-platform-app-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip" # Required for ECS Fargate (awsvpc networking)

  health_check {
    enabled             = true
    path                = "/actuator/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  # Allow in-flight requests to drain before deregistering a task
  deregistration_delay = 30

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-platform-app-tg" })

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# Listener — HTTP :80 → HTTPS redirect (301)
# -----------------------------------------------------------------------------

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-http-listener" })
}

# -----------------------------------------------------------------------------
# Listener — HTTPS :443 → forward to platform-app target group
# -----------------------------------------------------------------------------

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06" # TLS 1.3 preferred, TLS 1.2 minimum
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.platform_app.arn
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-https-listener" })
}

# -----------------------------------------------------------------------------
# Listener Rule — WebSocket upgrade path /ws/*
#
# WebSocket connections require sticky sessions so that subsequent frames are
# always routed to the same ECS task that handled the initial handshake.
# -----------------------------------------------------------------------------

resource "aws_lb_listener_rule" "websocket" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  condition {
    path_pattern {
      values = ["/ws/*"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.platform_app.arn

    # Sticky session ensures WebSocket frames reach the same backend task
    stickiness {
      enabled  = true
      duration = 86400 # 24 hours in seconds
    }
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-ws-rule" })
}
