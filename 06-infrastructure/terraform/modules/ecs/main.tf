################################################################################
# ECS Module — Agentic AI Platform
#
# Two Fargate services:
#   • platform-app  — Java Spring Boot, port 8080, internet-facing via ALB
#   • agent-engine  — Python FastAPI, port 8000, internal-only (no ALB)
#
# Design decisions are called out inline where they are non-obvious.
################################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

################################################################################
# 1. ECS Cluster
################################################################################

resource "aws_ecs_cluster" "this" {
  name = var.cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = var.cluster_name
  })
}

# FARGATE_SPOT is included to reduce compute costs for the agent-engine service,
# which can tolerate interruptions because individual inference requests are
# short-lived and the service can be scaled horizontally. platform-app uses
# on-demand FARGATE only so that user-facing requests are never dropped mid-flight.
resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name = aws_ecs_cluster.this.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

################################################################################
# 2. CloudWatch Log Groups
################################################################################

resource "aws_cloudwatch_log_group" "platform_app" {
  name              = "/ecs/platform-app"
  retention_in_days = 30

  tags = merge(var.tags, {
    Service = "platform-app"
  })
}

resource "aws_cloudwatch_log_group" "agent_engine" {
  name              = "/ecs/agent-engine"
  retention_in_days = 30

  tags = merge(var.tags, {
    Service = "agent-engine"
  })
}

################################################################################
# 3. IAM Roles
################################################################################

# ── Task Execution Role ───────────────────────────────────────────────────────
# Used by the ECS agent (not the container) to pull images and send logs.
# The inline policy scopes Secrets Manager access to only the secret ARNs that
# this cluster actually needs — following least-privilege.

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.cluster_name}-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-task-execution-role"
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "${var.cluster_name}-secrets-access"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = values(var.secret_arns)
      }
    ]
  })
}

# ── Task Role ─────────────────────────────────────────────────────────────────
# Used by the application code running inside the container.
# Only CloudWatch PutMetricData is needed here because both applications use
# the AWS SDK to emit custom metrics. All other AWS calls (S3, Bedrock, etc.)
# are intentionally excluded — services reach external APIs (Anthropic, Mongo
# Atlas, Jira, GitHub) over the public internet, not through AWS IAM.

resource "aws_iam_role" "ecs_task_role" {
  name = "${var.cluster_name}-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-task-role"
  })
}

resource "aws_iam_role_policy" "ecs_task_cloudwatch" {
  name = "${var.cluster_name}-cloudwatch-metrics"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      }
    ]
  })
}

################################################################################
# 4. Security Groups
################################################################################

# ── platform-app Security Group ───────────────────────────────────────────────
# Inbound: only port 8080 from the ALB security group (not the whole VPC).
# Outbound: unrestricted so the service can reach agent-engine (port 8000)
#           and MongoDB Atlas (port 27017) over the internet/VPC peering.

resource "aws_security_group" "platform_app" {
  name        = "${var.cluster_name}-platform-app-sg"
  description = "Security group for platform-app ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTP from ALB only"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  egress {
    description = "Allow all outbound (agent-engine, MongoDB Atlas, etc.)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name    = "${var.cluster_name}-platform-app-sg"
    Service = "platform-app"
  })
}

# ── agent-engine Security Group ───────────────────────────────────────────────
# agent-engine is an INTERNAL service — it is never exposed to the internet.
# It only accepts connections from platform-app. This enforces the trust
# boundary: only authenticated, authorised requests that have passed through
# platform-app's Okta middleware may reach the AI inference layer.
# Outbound: unrestricted so the container can reach Anthropic's API, MongoDB
#           Atlas, Jira, GitHub, and Figma over the internet.

resource "aws_security_group" "agent_engine" {
  name        = "${var.cluster_name}-agent-engine-sg"
  description = "Security group for agent-engine ECS tasks — internal only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTP from platform-app only — not from internet"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.platform_app.id]
  }

  egress {
    description = "Allow all outbound (Anthropic API, MongoDB Atlas, Jira, GitHub, Figma)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name    = "${var.cluster_name}-agent-engine-sg"
    Service = "agent-engine"
  })
}

################################################################################
# 5. Task Definitions
################################################################################

# ── platform-app Task Definition ─────────────────────────────────────────────

resource "aws_ecs_task_definition" "platform_app" {
  family                   = "${var.cluster_name}-platform-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "platform-app"
      image     = var.platform_app_image
      essential = true

      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]

      # Non-sensitive configuration delivered as plain environment variables.
      # Sensitive values (tokens, URIs with credentials) are injected via
      # secrets so they never appear in the ECS task definition in plaintext.
      environment = [
        {
          name  = "AGENT_ENGINE_BASE_URL"
          value = var.agent_engine_base_url
        },
        {
          name  = "SPRING_PROFILES_ACTIVE"
          value = var.environment
        }
      ]

      # Secrets are pulled from Secrets Manager at task start by the ECS agent
      # (using the execution role). The container sees them as environment
      # variables — Spring Boot picks them up automatically.
      secrets = [
        {
          name      = "OKTA_ISSUER_URI"
          valueFrom = var.secret_arns["okta_issuer_uri"]
        },
        {
          name      = "MONGO_URI"
          valueFrom = var.secret_arns["mongo_uri"]
        },
        {
          name      = "SLACK_WEBHOOK_URL"
          valueFrom = var.secret_arns["slack_webhook_url"]
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.platform_app.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # Spring Boot Actuator health endpoint — used by ECS to determine whether
      # the container is healthy before routing traffic to it.
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8080/actuator/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(var.tags, {
    Name    = "${var.cluster_name}-platform-app"
    Service = "platform-app"
  })
}

# ── agent-engine Task Definition ──────────────────────────────────────────────
# Higher CPU/memory allocation (2 vCPU / 4 GB) because LLM orchestration,
# prompt assembly, and tool-call parsing are CPU-intensive workloads.

resource "aws_ecs_task_definition" "agent_engine" {
  family                   = "${var.cluster_name}-agent-engine"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 2048
  memory                   = 4096
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "agent-engine"
      image     = var.agent_engine_image
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          # MOCK_MODE allows developers/QA to run the service without consuming
          # Anthropic API credits — the engine returns canned responses instead.
          name  = "MOCK_MODE"
          value = var.mock_mode
        },
        {
          name  = "MONGO_DB_NAME"
          value = "agentdb-${var.environment}"
        },
        {
          name  = "ENV"
          value = var.environment
        }
      ]

      secrets = [
        {
          name      = "ANTHROPIC_API_KEY"
          valueFrom = var.secret_arns["anthropic_api_key"]
        },
        {
          name      = "MONGO_URI"
          valueFrom = var.secret_arns["mongo_uri"]
        },
        {
          name      = "JIRA_TOKEN"
          valueFrom = var.secret_arns["jira_token"]
        },
        {
          name      = "GITHUB_TOKEN"
          valueFrom = var.secret_arns["github_token"]
        },
        {
          name      = "FIGMA_TOKEN"
          valueFrom = var.secret_arns["figma_token"]
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.agent_engine.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # FastAPI serves its auto-generated OpenAPI docs at /docs, which acts as
      # a cheap liveness probe (no database round-trip required).
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/docs || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 45
      }
    }
  ])

  tags = merge(var.tags, {
    Name    = "${var.cluster_name}-agent-engine"
    Service = "agent-engine"
  })
}

################################################################################
# Data Sources
################################################################################

data "aws_region" "current" {}

################################################################################
# 6. ALB Target Group (platform-app only)
################################################################################

# A target group is created here (inside the ECS module) so that the module
# is fully self-contained. The caller wires the ALB listener rule externally.
resource "aws_lb_target_group" "platform_app" {
  name        = "${var.cluster_name}-platform-app-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip" # required for Fargate awsvpc networking

  health_check {
    enabled             = true
    path                = "/actuator/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  # Allows in-flight connections to complete during a rolling deployment before
  # the old task is deregistered. Matches the Spring Boot graceful shutdown
  # window (default 30 s).
  deregistration_delay = 30

  tags = merge(var.tags, {
    Name    = "${var.cluster_name}-platform-app-tg"
    Service = "platform-app"
  })
}

################################################################################
# 6. ECS Services
################################################################################

# ── platform-app Service ──────────────────────────────────────────────────────

resource "aws_ecs_service" "platform_app" {
  name            = "${var.cluster_name}-platform-app"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.platform_app.arn
  desired_count   = var.platform_app_desired_count
  launch_type     = "FARGATE"

  # Rolling update — 100 % minimum ensures no downtime during deployments;
  # 200 % maximum allows a full second set of tasks to start before the old
  # set is drained, giving the ALB time to health-check new tasks.
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_controller {
    type = "ECS" # rolling update (not Blue/Green or external)
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.platform_app.id]
    assign_public_ip = false # tasks live in private subnets; ALB is the entry point
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.platform_app.arn
    container_name   = "platform-app"
    container_port   = 8080
  }

  # Prevent Terraform from resetting desired_count when auto-scaling is active.
  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution_role_policy,
    aws_lb_target_group.platform_app,
  ]

  tags = merge(var.tags, {
    Name    = "${var.cluster_name}-platform-app"
    Service = "platform-app"
  })
}

# ── agent-engine Service ───────────────────────────────────────────────────────
# agent-engine has NO load balancer attachment. It is reachable only by
# platform-app via service-to-service communication within the VPC. This keeps
# the LLM orchestration layer off the public internet and avoids an extra ALB
# cost for an internal service. platform-app resolves agent-engine's address
# using the AGENT_ENGINE_BASE_URL environment variable (e.g. a Cloud Map DNS
# name or a fixed private IP set by ECS Service Connect — wired externally).

resource "aws_ecs_service" "agent_engine" {
  name            = "${var.cluster_name}-agent-engine"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.agent_engine.arn
  desired_count   = var.agent_engine_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_controller {
    type = "ECS"
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.agent_engine.id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution_role_policy,
  ]

  tags = merge(var.tags, {
    Name    = "${var.cluster_name}-agent-engine"
    Service = "agent-engine"
  })
}

################################################################################
# 7. Auto Scaling
################################################################################

# ── platform-app Auto Scaling ─────────────────────────────────────────────────
# min=2 guarantees high availability across two AZs even at zero load.
# max=6 caps spend while providing 3× headroom over the baseline.

resource "aws_appautoscaling_target" "platform_app" {
  max_capacity       = 6
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.platform_app.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "platform_app_cpu_scale_out" {
  name               = "${var.cluster_name}-platform-app-cpu-scale-out"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.platform_app.resource_id
  scalable_dimension = aws_appautoscaling_target.platform_app.scalable_dimension
  service_namespace  = aws_appautoscaling_target.platform_app.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "platform_app_cpu_high" {
  alarm_name          = "${var.cluster_name}-platform-app-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 70

  dimensions = {
    ClusterName = aws_ecs_cluster.this.name
    ServiceName = aws_ecs_service.platform_app.name
  }

  alarm_actions = [aws_appautoscaling_policy.platform_app_cpu_scale_out.arn]

  tags = var.tags
}

resource "aws_appautoscaling_policy" "platform_app_cpu_scale_in" {
  name               = "${var.cluster_name}-platform-app-cpu-scale-in"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.platform_app.resource_id
  scalable_dimension = aws_appautoscaling_target.platform_app.scalable_dimension
  service_namespace  = aws_appautoscaling_target.platform_app.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 300 # longer cooldown on scale-in to avoid flapping
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = -1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "platform_app_cpu_low" {
  alarm_name          = "${var.cluster_name}-platform-app-cpu-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 5 # require sustained low CPU before scaling in
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 30

  dimensions = {
    ClusterName = aws_ecs_cluster.this.name
    ServiceName = aws_ecs_service.platform_app.name
  }

  alarm_actions = [aws_appautoscaling_policy.platform_app_cpu_scale_in.arn]

  tags = var.tags
}

# ── agent-engine Auto Scaling ─────────────────────────────────────────────────
# min=1 (single task is acceptable because there is no user-facing SLA on the
# internal service during off-peak hours). max=4 keeps Anthropic API costs
# bounded — each task can generate significant LLM spend.

resource "aws_appautoscaling_target" "agent_engine" {
  max_capacity       = 4
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.agent_engine.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "agent_engine_cpu_scale_out" {
  name               = "${var.cluster_name}-agent-engine-cpu-scale-out"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.agent_engine.resource_id
  scalable_dimension = aws_appautoscaling_target.agent_engine.scalable_dimension
  service_namespace  = aws_appautoscaling_target.agent_engine.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "agent_engine_cpu_high" {
  alarm_name          = "${var.cluster_name}-agent-engine-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 70

  dimensions = {
    ClusterName = aws_ecs_cluster.this.name
    ServiceName = aws_ecs_service.agent_engine.name
  }

  alarm_actions = [aws_appautoscaling_policy.agent_engine_cpu_scale_out.arn]

  tags = var.tags
}

resource "aws_appautoscaling_policy" "agent_engine_cpu_scale_in" {
  name               = "${var.cluster_name}-agent-engine-cpu-scale-in"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.agent_engine.resource_id
  scalable_dimension = aws_appautoscaling_target.agent_engine.scalable_dimension
  service_namespace  = aws_appautoscaling_target.agent_engine.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 300
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = -1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "agent_engine_cpu_low" {
  alarm_name          = "${var.cluster_name}-agent-engine-cpu-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 30

  dimensions = {
    ClusterName = aws_ecs_cluster.this.name
    ServiceName = aws_ecs_service.agent_engine.name
  }

  alarm_actions = [aws_appautoscaling_policy.agent_engine_cpu_scale_in.arn]

  tags = var.tags
}
