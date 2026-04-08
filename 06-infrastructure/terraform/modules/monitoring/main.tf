# -----------------------------------------------------------------------------
# Monitoring Module — Main
#
# Establishes the full observability stack for the Agentic AI platform:
#   • CloudWatch Dashboard — at-a-glance health of ALB, ECS, and SDLC runs
#   • SNS topic + email subscription for alert routing
#   • CloudWatch Alarms — ALB error rates, ECS CPU/memory, service task counts
#   • Log Metric Filters — custom metrics derived from structured application logs
# -----------------------------------------------------------------------------

locals {
  name_prefix = "platform-${var.environment}"

  common_tags = merge(
    {
      Module      = "monitoring"
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

# -----------------------------------------------------------------------------
# SNS Topic & Email Subscription
# -----------------------------------------------------------------------------

resource "aws_sns_topic" "platform_alerts" {
  name         = "${local.name_prefix}-platform-alerts"
  display_name = "Agentic AI Platform Alerts (${var.environment})"

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-platform-alerts" })
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.platform_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# -----------------------------------------------------------------------------
# CloudWatch Dashboard — Platform Overview
#
# Layout (3-column grid, 8-unit height rows):
#   Row 1: ALB Request Count | ALB 5xx Errors
#   Row 2: ECS CPU — platform-app | ECS CPU — agent-engine
#   Row 3: ECS Memory — platform-app | ECS Memory — agent-engine
#   Row 4: Active SDLC Runs (custom metric, full width)
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "platform_overview" {
  dashboard_name = "${local.name_prefix}-platform-overview"

  dashboard_body = jsonencode({
    widgets = [
      # ---- Row 1: ALB metrics ------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB — Request Count"
          region = "us-east-1"
          view   = "timeSeries"
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "RequestCount",
              "LoadBalancer", var.alb_arn_suffix]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB — 5xx Errors"
          region = "us-east-1"
          view   = "timeSeries"
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count",
              "LoadBalancer", var.alb_arn_suffix]
          ]
          annotations = {
            horizontal = [{ label = "Alarm threshold", value = 10, color = "#ff0000" }]
          }
        }
      },

      # ---- Row 2: ECS CPU ----------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ECS CPU — platform-app"
          region = "us-east-1"
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ECS", "CPUUtilization",
              "ClusterName", var.cluster_name,
              "ServiceName", var.platform_app_service_name]
          ]
          annotations = {
            horizontal = [{ label = "Alarm threshold (80%)", value = 80, color = "#ff0000" }]
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ECS CPU — agent-engine"
          region = "us-east-1"
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ECS", "CPUUtilization",
              "ClusterName", var.cluster_name,
              "ServiceName", var.agent_engine_service_name]
          ]
          annotations = {
            horizontal = [{ label = "Alarm threshold (85%)", value = 85, color = "#ff0000" }]
          }
        }
      },

      # ---- Row 3: ECS Memory -------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "ECS Memory — platform-app"
          region = "us-east-1"
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ECS", "MemoryUtilization",
              "ClusterName", var.cluster_name,
              "ServiceName", var.platform_app_service_name]
          ]
          annotations = {
            horizontal = [{ label = "Alarm threshold (85%)", value = 85, color = "#ff0000" }]
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "ECS Memory — agent-engine"
          region = "us-east-1"
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ECS", "MemoryUtilization",
              "ClusterName", var.cluster_name,
              "ServiceName", var.agent_engine_service_name]
          ]
        }
      },

      # ---- Row 4: Custom metric — Active SDLC Runs ---------------------------
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 24
        height = 6
        properties = {
          title  = "Active SDLC Runs (custom metric)"
          region = "us-east-1"
          view   = "timeSeries"
          stat   = "Maximum"
          period = 60
          metrics = [
            ["AgenticPlatform/${var.environment}", "ActiveSdlcRuns"]
          ]
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms — ALB
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${local.name_prefix}-alb-5xx-high"
  alarm_description   = "ALB is returning more than 10 HTTP 5xx errors in a 5-minute window. Investigate ECS task health and application logs."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-5xx-high" })
}

resource "aws_cloudwatch_metric_alarm" "alb_4xx" {
  alarm_name          = "${local.name_prefix}-alb-4xx-high"
  alarm_description   = "ALB is returning more than 50 HTTP 4xx errors in a 5-minute window. May indicate client misconfiguration, bad authentication tokens, or a crawler."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_ELB_4XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 50
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-4xx-high" })
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms — ECS CPU
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "platform_app_cpu" {
  alarm_name          = "${local.name_prefix}-platform-app-cpu-high"
  alarm_description   = "platform-app ECS service CPU utilization has exceeded 80% for 10 minutes. Consider scaling out or profiling the application."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2   # 2 × 5-minute periods = 10 minutes sustained
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.platform_app_service_name
  }

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-platform-app-cpu-high" })
}

resource "aws_cloudwatch_metric_alarm" "agent_engine_cpu" {
  alarm_name          = "${local.name_prefix}-agent-engine-cpu-high"
  alarm_description   = "agent-engine ECS service CPU utilization has exceeded 85% for 10 minutes. Agent workloads are CPU-intensive; investigate active run counts."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2   # 2 × 5-minute periods = 10 minutes sustained
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.agent_engine_service_name
  }

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-agent-engine-cpu-high" })
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms — ECS Memory
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "platform_app_memory" {
  alarm_name          = "${local.name_prefix}-platform-app-memory-high"
  alarm_description   = "platform-app ECS service memory utilization has exceeded 85% for 5 minutes. Risk of OOMKill; review heap settings or scale task memory."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.platform_app_service_name
  }

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-platform-app-memory-high" })
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms — ECS Service Task Count (Service Disruption)
#
# Fires when the number of running tasks falls below the desired count,
# which indicates tasks are crashing and failing to stay healthy.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "platform_app_task_count" {
  alarm_name          = "${local.name_prefix}-platform-app-task-count-low"
  alarm_description   = "platform-app running task count has been below desired count for 5 minutes. Service may be partially or fully unavailable."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 300
  statistic           = "Average"
  threshold           = var.platform_app_desired_count
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.platform_app_service_name
  }

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-platform-app-task-count-low" })
}

resource "aws_cloudwatch_metric_alarm" "agent_engine_task_count" {
  alarm_name          = "${local.name_prefix}-agent-engine-task-count-low"
  alarm_description   = "agent-engine running task count has been below desired count for 5 minutes. Agent workloads will queue or fail; check ECS events."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 300
  statistic           = "Average"
  threshold           = var.agent_engine_desired_count
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.agent_engine_service_name
  }

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-agent-engine-task-count-low" })
}

# -----------------------------------------------------------------------------
# Log Metric Filters
#
# These filters run against the structured JSON logs produced by each service
# and emit custom CloudWatch metrics that can be alarmed on independently of
# the built-in ECS/ALB metrics.
# -----------------------------------------------------------------------------

# Filter: ERROR lines in platform-app → PlatformErrors metric
resource "aws_cloudwatch_log_metric_filter" "platform_app_errors" {
  name           = "${local.name_prefix}-platform-app-errors"
  log_group_name = "/ecs/platform-app"
  pattern        = "[timestamp, level=ERROR, ...]"

  metric_transformation {
    name          = "PlatformErrors"
    namespace     = "AgenticPlatform/${var.environment}"
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "platform_app_errors" {
  alarm_name          = "${local.name_prefix}-platform-app-error-rate"
  alarm_description   = "platform-app is emitting an elevated number of ERROR log lines. Review /ecs/platform-app log group for root cause."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "PlatformErrors"
  namespace           = "AgenticPlatform/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 25
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-platform-app-error-rate" })
}

# Filter: "Agent run failed" messages in agent-engine → AgentRunFailures metric
resource "aws_cloudwatch_log_metric_filter" "agent_run_failures" {
  name           = "${local.name_prefix}-agent-run-failures"
  log_group_name = "/ecs/agent-engine"
  pattern        = "\"Agent run failed\""

  metric_transformation {
    name          = "AgentRunFailures"
    namespace     = "AgenticPlatform/${var.environment}"
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "agent_run_failures" {
  alarm_name          = "${local.name_prefix}-agent-run-failures"
  alarm_description   = "agent-engine has logged one or more 'Agent run failed' events in the past 5 minutes. Check /ecs/agent-engine logs for failed run IDs."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "AgentRunFailures"
  namespace           = "AgenticPlatform/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.platform_alerts.arn]
  ok_actions    = [aws_sns_topic.platform_alerts.arn]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-agent-run-failures" })
}
