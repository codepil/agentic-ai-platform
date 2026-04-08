################################################################################
# ECS Module — Outputs
################################################################################

# ── Cluster ───────────────────────────────────────────────────────────────────

output "cluster_id" {
  description = "ARN of the ECS cluster. Use this when referencing the cluster from other AWS resources (e.g. CodePipeline, CloudWatch dashboards)."
  value       = aws_ecs_cluster.this.id
}

output "cluster_name" {
  description = "Name of the ECS cluster. Used as the ClusterName dimension in CloudWatch metrics and when constructing appautoscaling resource IDs."
  value       = aws_ecs_cluster.this.name
}

# ── Service Names ─────────────────────────────────────────────────────────────

output "platform_app_service_name" {
  description = "Name of the platform-app ECS service. Useful for CI/CD pipelines that trigger a force-new-deployment via aws ecs update-service."
  value       = aws_ecs_service.platform_app.name
}

output "agent_engine_service_name" {
  description = "Name of the agent-engine ECS service."
  value       = aws_ecs_service.agent_engine.name
}

# ── Security Group IDs ────────────────────────────────────────────────────────

output "platform_app_sg_id" {
  description = "ID of the platform-app security group. Pass to the ALB module so the ALB listener can reference it as an egress target, and to any other service that legitimately needs to call platform-app."
  value       = aws_security_group.platform_app.id
}

output "agent_engine_sg_id" {
  description = "ID of the agent-engine security group. Exposed in case a future internal service (e.g. a batch job) needs to be granted access to port 8000."
  value       = aws_security_group.agent_engine.id
}

# ── Load Balancer ─────────────────────────────────────────────────────────────

output "platform_app_target_group_arn" {
  description = "ARN of the ALB target group for platform-app. Wire this to an ALB listener rule in the calling root module or ALB module."
  value       = aws_lb_target_group.platform_app.arn
}

# ── IAM Roles ─────────────────────────────────────────────────────────────────

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role. Useful if sibling modules (e.g. a scheduled-task module) need to reuse the same execution role rather than creating a duplicate."
  value       = aws_iam_role.ecs_task_execution_role.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role (application-level IAM permissions). Expose so callers can attach additional inline or managed policies without modifying this module."
  value       = aws_iam_role.ecs_task_role.arn
}

# ── CloudWatch Log Groups ─────────────────────────────────────────────────────

output "platform_app_log_group_name" {
  description = "Name of the CloudWatch log group for platform-app container logs. Use in CloudWatch Insights queries or subscription filters."
  value       = aws_cloudwatch_log_group.platform_app.name
}

output "agent_engine_log_group_name" {
  description = "Name of the CloudWatch log group for agent-engine container logs."
  value       = aws_cloudwatch_log_group.agent_engine.name
}
