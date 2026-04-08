################################################################################
# ECS Module — Variable Declarations
################################################################################

variable "cluster_name" {
  description = "Name of the ECS cluster. Used as a prefix for all child resources (services, task definitions, security groups, IAM roles)."
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod). Injected into containers as SPRING_PROFILES_ACTIVE / ENV and used to namespace the Mongo database name."
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC in which ECS tasks and security groups will be created."
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs where Fargate tasks will be placed. Should span at least two Availability Zones for high availability."
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group ID of the Application Load Balancer that fronts platform-app. Only this SG is permitted to reach port 8080 on platform-app tasks."
  type        = string
}

# ── Container Images ──────────────────────────────────────────────────────────

variable "platform_app_image" {
  description = "Fully-qualified Docker image URI for the platform-app service (Java Spring Boot). Example: 123456789012.dkr.ecr.us-east-1.amazonaws.com/platform-app:v1.2.3"
  type        = string
}

variable "agent_engine_image" {
  description = "Fully-qualified Docker image URI for the agent-engine service (Python FastAPI). Example: 123456789012.dkr.ecr.us-east-1.amazonaws.com/agent-engine:v0.9.1"
  type        = string
}

# ── Service Scaling ───────────────────────────────────────────────────────────

variable "platform_app_desired_count" {
  description = "Initial desired task count for the platform-app service. Auto Scaling may adjust this at runtime; Terraform will ignore drift once scaling is active."
  type        = number
  default     = 2
}

variable "agent_engine_desired_count" {
  description = "Initial desired task count for the agent-engine service. Set to 1 for non-production environments to save cost."
  type        = number
  default     = 1
}

# ── Application Configuration ─────────────────────────────────────────────────

variable "agent_engine_base_url" {
  description = "Base URL that platform-app uses to call agent-engine (e.g. http://agent-engine.local:8000 if using ECS Service Connect, or a fixed private IP). Must NOT be a public URL — agent-engine is internal-only."
  type        = string
}

variable "mock_mode" {
  description = "When set to \"true\", agent-engine returns canned LLM responses instead of calling the Anthropic API. Useful for integration testing and cost control in non-production environments."
  type        = string
  default     = "false"

  validation {
    condition     = contains(["true", "false"], var.mock_mode)
    error_message = "mock_mode must be either \"true\" or \"false\"."
  }
}

# ── Secrets Manager ───────────────────────────────────────────────────────────
# Secrets are referenced by ARN rather than by value so that Terraform never
# stores sensitive data in state. The ECS agent pulls the values at task-start
# time using the execution role.
#
# Required keys:
#   okta_issuer_uri    — Okta OAuth2 issuer URI used by platform-app
#   mongo_uri          — MongoDB Atlas connection string (shared by both services)
#   slack_webhook_url  — Slack incoming webhook for platform-app notifications
#   anthropic_api_key  — Anthropic Claude API key for agent-engine
#   jira_token         — Jira API token for the Jira tool integration
#   github_token       — GitHub personal access token for the GitHub tool integration
#   figma_token        — Figma personal access token for the Figma tool integration

variable "secret_arns" {
  description = "Map of logical secret name to Secrets Manager ARN. The execution role will be granted GetSecretValue on exactly these ARNs (least-privilege). See the comment above for required keys."
  type        = map(string)

  validation {
    condition = alltrue([
      for key in ["okta_issuer_uri", "mongo_uri", "slack_webhook_url", "anthropic_api_key", "jira_token", "github_token", "figma_token"] :
      contains(keys(var.secret_arns), key)
    ])
    error_message = "secret_arns must contain keys: okta_issuer_uri, mongo_uri, slack_webhook_url, anthropic_api_key, jira_token, github_token, figma_token."
  }
}

# ── Tagging ───────────────────────────────────────────────────────────────────

variable "tags" {
  description = "Map of tags to apply to all resources created by this module. Merged with resource-specific tags (Name, Service) at each resource."
  type        = map(string)
  default     = {}
}
