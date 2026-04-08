# -----------------------------------------------------------------------------
# ECR Module — Variables
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod). Embedded in repository names."
  type        = string
}

variable "github_actions_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions OIDC. Granted push permissions on both repositories."
  type        = string
}

variable "ecs_execution_role_arn" {
  description = "ARN of the ECS task execution IAM role. Granted pull (ecr:GetDownloadUrlForLayer, ecr:BatchGetImage, ecr:BatchCheckLayerAvailability) permissions on both repositories."
  type        = string
}

variable "tags" {
  description = "Map of additional tags to apply to all ECR resources."
  type        = map(string)
  default     = {}
}
