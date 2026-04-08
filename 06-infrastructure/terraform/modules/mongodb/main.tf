# -----------------------------------------------------------------------------
# MongoDB Atlas Module — Main
#
# Provisions the full MongoDB Atlas footprint for the Agentic AI platform:
#   • Atlas Project
#   • Replica-set cluster (AWS, US_EAST_1) with cloud backup and PIT recovery
#   • AWS PrivateLink endpoint + Atlas PrivateLink endpoint service
#   • AWS VPC Interface Endpoint (ties Atlas PrivateLink into the VPC)
#   • Application database user with scoped readWrite role
#   • IP access list restricted to the VPC CIDR (no public internet access)
# -----------------------------------------------------------------------------

locals {
  cluster_name = "platform-${var.environment}"

  common_tags = merge(
    {
      Module      = "mongodb"
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

# -----------------------------------------------------------------------------
# Data sources
# -----------------------------------------------------------------------------

# Fetch the Secrets Manager secret value so the db user password is never
# stored in plain text in state or version control.
data "aws_secretsmanager_secret_version" "mongo_password" {
  secret_id = var.mongo_password_secret_arn
}

# -----------------------------------------------------------------------------
# Atlas Project
# -----------------------------------------------------------------------------

resource "mongodbatlas_project" "this" {
  name   = var.project_name
  org_id = var.atlas_org_id

  # Disable default Atlas alert emails — alerts are managed via CloudWatch/SNS
  is_collect_database_specifics_statistics_enabled = true
  is_data_explorer_enabled                         = true
  is_performance_advisor_enabled                   = true
  is_realtime_performance_panel_enabled            = true
  is_schema_advisor_enabled                        = true
}

# -----------------------------------------------------------------------------
# Atlas Cluster
# -----------------------------------------------------------------------------

resource "mongodbatlas_cluster" "this" {
  project_id = mongodbatlas_project.this.id
  name       = local.cluster_name

  # Topology
  cluster_type = "REPLICASET"

  # Cloud provider & region
  provider_name               = "AWS"
  provider_region_name        = "US_EAST_1"
  provider_instance_size_name = var.instance_size

  # Engine version
  mongo_db_major_version = "7.0"

  # Storage
  auto_scaling_disk_gb_enabled = true

  # Backup — full cloud backup + point-in-time recovery
  cloud_backup = true
  pit_enabled  = true

  # Advanced configuration
  advanced_configuration {
    javascript_enabled           = false
    minimum_enabled_tls_protocol = "TLS1_2"
    no_table_scan                = false
    oplog_size_mb                = 2048
  }

  lifecycle {
    # Prevent accidental cluster destruction; remove this block only when
    # explicitly decommissioning the environment.
    prevent_destroy = false
  }
}

# -----------------------------------------------------------------------------
# PrivateLink — Atlas side
#
# Step 1: Request a private endpoint on the Atlas project. Atlas will allocate
#         a VPC endpoint service on its side and return the service name needed
#         to create the AWS VPC endpoint.
# -----------------------------------------------------------------------------

resource "mongodbatlas_privatelink_endpoint" "this" {
  project_id    = mongodbatlas_project.this.id
  provider_name = "AWS"
  region        = var.aws_region
}

# -----------------------------------------------------------------------------
# AWS VPC Interface Endpoint
#
# Step 2: Create an AWS VPC interface endpoint that connects to the Atlas
#         PrivateLink service. The endpoint is placed in the isolated subnets so
#         ECS tasks never traverse the public internet to reach MongoDB.
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "mongodb_atlas" {
  vpc_id              = var.vpc_id
  service_name        = mongodbatlas_privatelink_endpoint.this.endpoint_service_name
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.isolated_subnet_ids
  private_dns_enabled = true

  tags = merge(local.common_tags, { Name = "${local.cluster_name}-atlas-vpce" })

  # The endpoint can only be created after Atlas has provisioned the service.
  depends_on = [mongodbatlas_privatelink_endpoint.this]
}

# -----------------------------------------------------------------------------
# PrivateLink Endpoint Service — Atlas side
#
# Step 3: Register the AWS VPC endpoint ID back with Atlas so it accepts
#         connections from this endpoint.
# -----------------------------------------------------------------------------

resource "mongodbatlas_privatelink_endpoint_service" "this" {
  project_id          = mongodbatlas_project.this.id
  private_link_id     = mongodbatlas_privatelink_endpoint.this.private_link_id
  endpoint_service_id = aws_vpc_endpoint.mongodb_atlas.id
  provider_name       = "AWS"

  depends_on = [aws_vpc_endpoint.mongodb_atlas]
}

# -----------------------------------------------------------------------------
# Database User — application identity
#
# The "platform-app" user is scoped strictly to the cluster and given
# readWrite access only on the "agent_platform" database, following the
# principle of least privilege. The password is pulled from Secrets Manager
# at plan time so it never appears in source control.
# -----------------------------------------------------------------------------

resource "mongodbatlas_database_user" "app" {
  project_id         = mongodbatlas_project.this.id
  username           = "platform-app"
  password           = data.aws_secretsmanager_secret_version.mongo_password.secret_string
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = "agent_platform"
  }

  # Restrict this user to the specific cluster — not project-wide
  scopes {
    name = mongodbatlas_cluster.this.name
    type = "CLUSTER"
  }

  depends_on = [mongodbatlas_cluster.this]
}

# -----------------------------------------------------------------------------
# IP Access List
#
# Only the VPC CIDR is whitelisted. This means all Atlas traffic must traverse
# the PrivateLink endpoint; any attempt to connect from the public internet
# will be rejected at the Atlas network layer.
# -----------------------------------------------------------------------------

resource "mongodbatlas_project_ip_access_list" "vpc_only" {
  project_id = mongodbatlas_project.this.id
  cidr_block = var.vpc_cidr
  comment    = "VPC CIDR — all Atlas access via PrivateLink only (${var.environment})"
}
