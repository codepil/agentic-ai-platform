# -----------------------------------------------------------------------------
# ECR Module — Outputs
# -----------------------------------------------------------------------------

output "platform_app_repository_url" {
  description = "Full ECR URI for the platform-app repository (e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com/platform-prod/platform-app). Use as the image base in ECS task definitions and CI docker push commands."
  value       = aws_ecr_repository.platform_app.repository_url
}

output "agent_engine_repository_url" {
  description = "Full ECR URI for the agent-engine repository. Use as the image base in ECS task definitions and CI docker push commands."
  value       = aws_ecr_repository.agent_engine.repository_url
}

output "platform_app_repository_name" {
  description = "Short ECR repository name for platform-app (e.g. platform-prod/platform-app). Useful for constructing lifecycle/policy references."
  value       = aws_ecr_repository.platform_app.name
}

output "agent_engine_repository_name" {
  description = "Short ECR repository name for agent-engine (e.g. platform-prod/agent-engine)."
  value       = aws_ecr_repository.agent_engine.name
}

output "ecr_kms_key_arn" {
  description = "ARN of the KMS CMK used to encrypt both ECR repositories. Grant this to any additional principals that need to push/pull encrypted layers."
  value       = aws_kms_key.ecr.arn
}
