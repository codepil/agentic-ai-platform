# -----------------------------------------------------------------------------
# Prod Environment — Variables
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
  description = "Environment identifier. Must be 'prod' for this workspace."
  type        = string
  default     = "prod"
}

# ---- Networking -------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones to use. Prod uses two AZs for high availability."
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
  description = "Public domain name for the platform (e.g. agentic-platform.example.com)."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM TLS certificate for the ALB HTTPS listener."
  type        = string
  sensitive   = true
}

variable "alb_access_logs_bucket" {
  description = "S3 bucket name for ALB access logs. Required in prod for audit and compliance."
  type        = string
  default     = ""
}

# ---- ECS --------------------------------------------------------------------

variable "platform_app_image" {
  description = "Docker image URI for the platform-app service (ECR repo URI + tag). Pin to a specific SHA or semver tag in prod."
  type        = string
}

variable "agent_engine_image" {
  description = "Docker image URI for the agent-engine service (ECR repo URI + tag). Pin to a specific SHA or semver tag in prod."
  type        = string
}

variable "platform_app_desired_count" {
  description = "Desired number of platform-app ECS tasks. Two in prod for high availability."
  type        = number
  default     = 2
}

variable "agent_engine_desired_count" {
  description = "Desired number of agent-engine ECS tasks. Two in prod for high availability."
  type        = number
  default     = 2
}

variable "mock_mode" {
  description = "When 'true', agent-engine runs in mock mode. Always 'false' in production."
  type        = string
  default     = "false"
}

# ---- MongoDB Atlas ----------------------------------------------------------

variable "atlas_org_id" {
  description = "MongoDB Atlas organization ID. Set via TF_VAR_atlas_org_id environment variable."
  type        = string
  sensitive   = true
}

variable "mongo_instance_size" {
  description = "Atlas cluster tier. M30 provides dedicated resources suitable for production workloads."
  type        = string
  default     = "M30"
}

variable "mongo_password_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the MongoDB application user password."
  type        = string
  sensitive   = true
}

# ---- Monitoring -------------------------------------------------------------

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications (on-call distribution list in prod)."
  type        = string
}

# ---- Misc -------------------------------------------------------------------

variable "deletion_protection" {
  description = "Enable deletion protection on ALB. Must be true in prod to prevent accidental destruction."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
