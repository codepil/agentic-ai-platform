# -----------------------------------------------------------------------------
# Dev Environment — Root Module
#
# Wires together all platform modules for the development environment.
# Dev is optimised for cost:
#   • Single AZ (no cross-AZ data transfer charges)
#   • M10 MongoDB cluster (smallest dedicated tier)
#   • Single ECS task per service
#   • Mock mode enabled (no real LLM API calls)
#   • Deletion protection disabled (quick teardown during development)
# -----------------------------------------------------------------------------

locals {
  env = "dev"

  common_tags = merge(
    {
      Project     = "agentic-ai-platform"
      Environment = local.env
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------

module "vpc" {
  source = "../../modules/vpc"

  environment           = local.env
  vpc_cidr              = var.vpc_cidr
  availability_zones    = var.availability_zones    # single AZ in dev
  public_subnet_cidrs   = var.public_subnet_cidrs
  private_subnet_cidrs  = var.private_subnet_cidrs
  isolated_subnet_cidrs = var.isolated_subnet_cidrs

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Secrets Manager
# -----------------------------------------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  environment = local.env

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# ECR
# -----------------------------------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"

  environment = local.env

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# ALB
# -----------------------------------------------------------------------------

module "alb" {
  source = "../../modules/alb"

  name                = "platform"
  environment         = local.env
  vpc_id              = module.vpc.vpc_id
  public_subnet_ids   = module.vpc.public_subnet_ids
  acm_certificate_arn = var.acm_certificate_arn
  deletion_protection = var.deletion_protection  # false in dev

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# ECS
# -----------------------------------------------------------------------------

module "ecs" {
  source = "../../modules/ecs"

  environment = local.env
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids

  alb_security_group_id   = module.alb.security_group_id
  platform_app_target_group_arn = module.alb.platform_app_target_group_arn

  platform_app_image         = var.platform_app_image
  agent_engine_image         = var.agent_engine_image
  platform_app_desired_count = var.platform_app_desired_count
  agent_engine_desired_count = var.agent_engine_desired_count

  # Pass secrets and config through to the task definitions
  secrets_manager_arns = module.secrets.secret_arns
  mongo_connection_string_secret_arn = module.secrets.mongo_connection_string_arn

  mock_mode = var.mock_mode  # "true" — avoids real LLM API charges in dev

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# MongoDB Atlas
# -----------------------------------------------------------------------------

module "mongodb" {
  source = "../../modules/mongodb"

  environment  = local.env
  project_name = "agentic-ai-platform-${local.env}"
  atlas_org_id = var.atlas_org_id

  instance_size = var.mongo_instance_size  # M10

  vpc_id              = module.vpc.vpc_id
  vpc_cidr            = var.vpc_cidr
  isolated_subnet_ids = module.vpc.isolated_subnet_ids
  aws_region          = var.aws_region

  mongo_password_secret_arn = var.mongo_password_secret_arn

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Monitoring
# -----------------------------------------------------------------------------

module "monitoring" {
  source = "../../modules/monitoring"

  environment = local.env

  alb_arn_suffix            = module.alb.alb_arn_suffix
  cluster_name              = module.ecs.cluster_name
  platform_app_service_name = module.ecs.platform_app_service_name
  agent_engine_service_name = module.ecs.agent_engine_service_name

  platform_app_desired_count = var.platform_app_desired_count
  agent_engine_desired_count = var.agent_engine_desired_count

  alert_email = var.alert_email

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Outputs — surfaced at the environment level for convenience
# -----------------------------------------------------------------------------

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  value       = module.alb.dns_name
}

output "ecr_platform_app_url" {
  description = "ECR repository URL for platform-app images."
  value       = module.ecr.platform_app_repository_url
}

output "ecr_agent_engine_url" {
  description = "ECR repository URL for agent-engine images."
  value       = module.ecr.agent_engine_repository_url
}

output "mongodb_cluster_id" {
  description = "MongoDB Atlas cluster ID."
  value       = module.mongodb.cluster_id
}

output "mongodb_connection_strings" {
  description = "MongoDB Atlas connection strings (standard + private PrivateLink URI)."
  value       = module.mongodb.cluster_connection_strings
  sensitive   = true
}

output "monitoring_dashboard_url" {
  description = "URL of the CloudWatch platform overview dashboard."
  value       = module.monitoring.dashboard_url
}

output "sns_alerts_topic_arn" {
  description = "ARN of the SNS topic receiving CloudWatch alarm notifications."
  value       = module.monitoring.sns_topic_arn
}
