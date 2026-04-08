# -----------------------------------------------------------------------------
# Dev Environment — Variable Values
#
# IMPORTANT — DO NOT commit sensitive values to source control.
# Sensitive variables (atlas_org_id, mongo_password_secret_arn, acm_certificate_arn)
# must be set via environment variables:
#
#   export TF_VAR_atlas_org_id="<your-org-id>"
#   export TF_VAR_mongo_password_secret_arn="arn:aws:secretsmanager:..."
#   export TF_VAR_acm_certificate_arn="arn:aws:acm:..."
# -----------------------------------------------------------------------------

# ---- General ----------------------------------------------------------------
environment = "dev"
aws_region  = "us-east-1"

# ---- Networking — single AZ for dev cost savings ----------------------------
vpc_cidr           = "10.10.0.0/16"
availability_zones = ["us-east-1a"]  # Single AZ reduces cross-AZ data transfer costs

public_subnet_cidrs   = ["10.10.0.0/24"]
private_subnet_cidrs  = ["10.10.10.0/24"]
isolated_subnet_cidrs = ["10.10.20.0/24"]

# ---- ALB / TLS — update with your actual domain and cert ARN ----------------
domain_name = "dev.agentic-platform.example.com"
# acm_certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/..."  # set via TF_VAR

# ---- ECS Images — update tags after first docker push -----------------------
platform_app_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/platform-app:latest"
agent_engine_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/agent-engine:latest"

# ---- ECS Scale — minimal for dev --------------------------------------------
platform_app_desired_count = 1
agent_engine_desired_count = 1

# ---- Mock mode — disables real LLM API calls to save cost -------------------
mock_mode = "true"

# ---- MongoDB Atlas ----------------------------------------------------------
mongo_instance_size = "M10"  # Smallest dedicated tier; sufficient for dev workloads
# atlas_org_id              = "..."   # Set via TF_VAR_atlas_org_id
# mongo_password_secret_arn = "..."   # Set via TF_VAR_mongo_password_secret_arn

# ---- Monitoring -------------------------------------------------------------
alert_email = "dev-team@yourcompany.com"

# ---- Misc -------------------------------------------------------------------
deletion_protection = false  # Allow quick teardowns in dev

tags = {
  CostCenter  = "engineering"
  Owner       = "platform-team"
}
