# -----------------------------------------------------------------------------
# Prod Environment — Variable Values
#
# IMPORTANT — DO NOT commit sensitive values to source control.
# Sensitive variables (atlas_org_id, mongo_password_secret_arn, acm_certificate_arn)
# must be set via environment variables:
#
#   export TF_VAR_atlas_org_id="<your-org-id>"
#   export TF_VAR_mongo_password_secret_arn="arn:aws:secretsmanager:..."
#   export TF_VAR_acm_certificate_arn="arn:aws:acm:..."
#
# Apply changes to prod through CI/CD only — never run terraform apply locally
# against production without peer review and change-management approval.
# -----------------------------------------------------------------------------

# ---- General ----------------------------------------------------------------
environment = "prod"
aws_region  = "us-east-1"

# ---- Networking — two AZs for high availability ----------------------------
vpc_cidr           = "10.20.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]

public_subnet_cidrs   = ["10.20.0.0/24", "10.20.1.0/24"]
private_subnet_cidrs  = ["10.20.10.0/24", "10.20.11.0/24"]
isolated_subnet_cidrs = ["10.20.20.0/24", "10.20.21.0/24"]

# ---- ALB / TLS — update with your actual domain and cert ARN ----------------
domain_name        = "agentic-platform.example.com"
alb_access_logs_bucket = "your-alb-access-logs-bucket-prod"
# acm_certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/..."  # set via TF_VAR

# ---- ECS Images — always pin to immutable SHA-tagged images in prod ----------
platform_app_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/platform-app:1.0.0"
agent_engine_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/agent-engine:1.0.0"

# ---- ECS Scale — two tasks per service for HA ------------------------------
platform_app_desired_count = 2
agent_engine_desired_count = 2

# ---- Mock mode OFF — real LLM API calls in prod ----------------------------
mock_mode = "false"

# ---- MongoDB Atlas ----------------------------------------------------------
mongo_instance_size = "M30"  # Production tier with dedicated resources
# atlas_org_id              = "..."   # Set via TF_VAR_atlas_org_id
# mongo_password_secret_arn = "..."   # Set via TF_VAR_mongo_password_secret_arn

# ---- Monitoring -------------------------------------------------------------
alert_email = "platform-oncall@yourcompany.com"

# ---- Misc -------------------------------------------------------------------
deletion_protection = true  # Prevents accidental ALB deletion in production

tags = {
  CostCenter  = "engineering"
  Owner       = "platform-team"
  Criticality = "high"
}
