# -----------------------------------------------------------------------------
# ALB Module — Outputs
# -----------------------------------------------------------------------------

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer. Use this as the CNAME/alias target in Route 53."
  value       = aws_lb.this.dns_name
}

output "alb_arn" {
  description = "Full ARN of the Application Load Balancer."
  value       = aws_lb.this.arn
}

output "alb_security_group_id" {
  description = "ID of the security group attached to the ALB. Reference this in ECS task security groups to allow inbound traffic only from the ALB."
  value       = aws_security_group.alb.id
}

output "platform_app_target_group_arn" {
  description = "ARN of the platform-app target group. Pass to the ECS service's load_balancer block."
  value       = aws_lb_target_group.platform_app.arn
}

output "https_listener_arn" {
  description = "ARN of the HTTPS (port 443) listener. Use to attach additional listener rules (e.g. agent-engine routing)."
  value       = aws_lb_listener.https.arn
}
