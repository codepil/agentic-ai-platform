# -----------------------------------------------------------------------------
# Monitoring Module — Outputs
# -----------------------------------------------------------------------------

output "sns_topic_arn" {
  description = "ARN of the SNS topic that receives all CloudWatch alarm notifications."
  value       = aws_sns_topic.platform_alerts.arn
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard for the platform overview."
  value       = aws_cloudwatch_dashboard.platform_overview.dashboard_name
}

output "dashboard_url" {
  description = "Direct URL to the CloudWatch dashboard in the AWS console."
  value       = "https://console.aws.amazon.com/cloudwatch/home#dashboards:name=${aws_cloudwatch_dashboard.platform_overview.dashboard_name}"
}

output "platform_errors_metric_name" {
  description = "Name of the custom CloudWatch metric that counts ERROR log lines from platform-app."
  value       = "PlatformErrors"
}

output "agent_run_failures_metric_name" {
  description = "Name of the custom CloudWatch metric that counts 'Agent run failed' log events from agent-engine."
  value       = "AgentRunFailures"
}
