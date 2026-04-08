# -----------------------------------------------------------------------------
# Dev Environment — Variables
#
# Sensitive values (API keys, secret ARNs, org IDs) should be passed via
# environment variables or a secrets manager, never hard-coded in tfvars.
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for all resources in this environment."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment identifier. Must be 'dev' for this workspace."
  type        = string
  default     = "dev"
}

# ---- Networking -------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones to use. Dev uses a single AZ to minimize cost."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets (one per AZ)."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "List of CIDR blocks for private/app-tier subnets (one per AZ)."
  type        = list(string)
}

variable "isolated_subnet_cidrs" {
  description = "List of CIDR blocks for isolated/data-tier subnets (one per AZ). Used for MongoDB PrivateLink endpoints."
  type        = list(string)
}

# ---- ALB / TLS --------------------------------------------------------------

variable "domain_name" {
  description = "Public domain name for the platform (e.g. dev.agentic-platform.example.com). Used to look up the ACM certificate."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM TLS certificate for the ALB HTTPS listener."
  type        = string
}

# ---- ECS --------------------------------------------------------------------

variable "platform_app_image" {
  description = "Docker image URI for the platform-app service (ECR repo URI + tag)."
  type        = string
}

variable "agent_engine_image" {
  description = "Docker image URI for the agent-engine service (ECR repo URI + tag)."
  type        = string
}

variable "platform_app_desired_count" {
  description = "Desired number of platform-app ECS tasks. Set to 1 in dev for cost savings."
  type        = number
  default     = 1
}

variable "agent_engine_desired_count" {
  description = "Desired number of agent-engine ECS tasks. Set to 1 in dev for cost savings."
  type        = number
  default     = 1
}

variable "mock_mode" {
  description = "When 'true', agent-engine runs in mock mode and does not call real LLM APIs. Saves cost during dev/test."
  type        = string
  default     = "true"
}

# ---- MongoDB Atlas ----------------------------------------------------------

variable "atlas_org_id" {
  description = "MongoDB Atlas organization ID. Set via TF_VAR_atlas_org_id environment variable."
  type        = string
  sensitive   = true
}

variable "mongo_instance_size" {
  description = "Atlas cluster tier. M10 is the minimum dedicated tier and is used in dev."
  type        = string
  default     = "M10"
}

variable "mongo_password_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the MongoDB application user password."
  type        = string
  sensitive   = true
}

# ---- Monitoring -------------------------------------------------------------

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications."
  type        = string
}

# ---- Misc -------------------------------------------------------------------

variable "deletion_protection" {
  description = "Enable deletion protection on ALB. Always false in dev to allow quick teardowns."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
