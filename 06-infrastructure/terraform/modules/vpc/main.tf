###############################################################################
# VPC Module — Agentic AI Platform
#
# Creates a fully-featured 3-tier VPC with:
#   - Public subnets    (10.0.1.0/24, 10.0.2.0/24)   → ALB, NAT Gateways
#   - Private subnets   (10.0.11.0/24, 10.0.12.0/24) → ECS Fargate tasks
#   - Isolated subnets  (10.0.21.0/24, 10.0.22.0/24) → VPC Endpoints, Atlas PrivateLink
#
# Provider requirement: hashicorp/aws ~> 5.0
###############################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

###############################################################################
# Local values
###############################################################################

locals {
  # Merge caller-supplied tags with the module's standard tags.
  # The Name tag is set per-resource below so that each resource gets a
  # meaningful name rather than a shared module-level name.
  common_tags = merge(var.tags, {
    VpcName     = var.vpc_name
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

###############################################################################
# VPC
###############################################################################

resource "aws_vpc" "this" {
  cidr_block = "10.0.0.0/16"

  # DNS hostnames must be enabled for VPC Interface Endpoints to be reachable
  # by their AWS-provided DNS names (e.g., vpce-xxx.secretsmanager.us-east-1.vpce.amazonaws.com).
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-vpc"
  })
}

###############################################################################
# Internet Gateway
###############################################################################

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-igw"
  })
}

###############################################################################
# Public Subnets (one per AZ)
# CIDRs: 10.0.1.0/24 (AZ[0]), 10.0.2.0/24 (AZ[1])
#
# map_public_ip_on_launch = true so that ALB nodes and NAT Gateway EIPs
# can be associated without requiring explicit EIP allocation per instance.
# ECS Fargate tasks are placed in PRIVATE subnets and do NOT get public IPs.
###############################################################################

resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-public-${var.azs[count.index]}"
    Tier = "public"
  })
}

###############################################################################
# Private Subnets (one per AZ)
# CIDRs: 10.0.11.0/24 (AZ[0]), 10.0.12.0/24 (AZ[1])
#
# ECS Fargate tasks run here. Outbound internet traffic (Anthropic API, Slack,
# GitHub, etc.) routes through the NAT Gateway in the same AZ to avoid
# cross-AZ NAT data transfer charges.
###############################################################################

resource "aws_subnet" "private" {
  count = 2

  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.0.${count.index + 11}.0/24"
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-private-${var.azs[count.index]}"
    Tier = "private"
  })
}

###############################################################################
# Isolated Subnets (one per AZ)
# CIDRs: 10.0.21.0/24 (AZ[0]), 10.0.22.0/24 (AZ[1])
#
# These subnets have NO route to the internet (no NAT, no IGW). They are used
# exclusively for VPC Interface Endpoints and the MongoDB Atlas PrivateLink ENI.
# Placing endpoints here ensures that even a misconfigured security group
# cannot use the endpoint ENI as an egress path to the internet.
###############################################################################

resource "aws_subnet" "isolated" {
  count = 2

  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.0.${count.index + 21}.0/24"
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-isolated-${var.azs[count.index]}"
    Tier = "isolated"
  })
}

###############################################################################
# Elastic IPs for NAT Gateways (one per AZ)
#
# EIPs are allocated independently of NAT Gateways so that if a NAT GW is
# destroyed and recreated (e.g., during Terraform replace), the public IP
# stays the same. This is important if the Anthropic or Slack APIs whitelist
# outbound IPs from the platform.
###############################################################################

resource "aws_eip" "nat" {
  count = 2

  domain = "vpc" # "vpc" is the only valid value since EC2-Classic retirement

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-nat-eip-${var.azs[count.index]}"
  })

  # EIPs must be created after the IGW is attached to the VPC.
  # Without the IGW, the EIP cannot route traffic to the internet.
  depends_on = [aws_internet_gateway.this]
}

###############################################################################
# NAT Gateways (one per public subnet / AZ)
#
# One NAT GW per AZ ensures that if an AZ fails, the surviving private subnet
# in the healthy AZ still has outbound internet access through its own NAT GW.
# This avoids the single-NAT-GW anti-pattern where a NAT GW failure in AZ-a
# also kills outbound connectivity for tasks in AZ-b.
#
# Cost note: In dev/non-prod environments, callers may choose to use a single
# NAT GW and accept the AZ-dependency risk. This module always creates 2 to
# enforce the HA design. Override at the calling root module level if needed.
###############################################################################

resource "aws_nat_gateway" "this" {
  count = 2

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-natgw-${var.azs[count.index]}"
  })

  depends_on = [aws_internet_gateway.this]
}

###############################################################################
# Route Table — Public
#
# A single route table is shared across both public subnets because both
# subnets have identical routing (0.0.0.0/0 → IGW). Using a single table
# avoids drift if routes need to be added later (e.g., S3 Gateway endpoint).
###############################################################################

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-rtb-public"
  })
}

resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

###############################################################################
# Route Tables — Private (one per AZ)
#
# Each private subnet gets its OWN route table pointing to the NAT GW in the
# SAME AZ. This is the critical HA pattern: if AZ-a fails (taking NAT-A with
# it), the route table for private-AZ-b still points to NAT-B which is alive.
# A shared private route table would mean all private subnets share the same
# NAT GW, reintroducing the single-point-of-failure.
###############################################################################

resource "aws_route_table" "private" {
  count = 2

  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[count.index].id
  }

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-rtb-private-${var.azs[count.index]}"
  })
}

resource "aws_route_table_association" "private" {
  count = 2

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

###############################################################################
# Route Table — Isolated
#
# A single route table with NO default route. The only entry is the implicit
# local route (10.0.0.0/16 → local) that AWS adds automatically.
# VPC Interface Endpoints in isolated subnets are reachable from private
# subnets via the local route — no IGW or NAT required.
###############################################################################

resource "aws_route_table" "isolated" {
  vpc_id = aws_vpc.this.id

  # No routes defined here — AWS automatically adds the local VPC route.
  # Intentionally no default route to enforce the "isolated" guarantee.

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-rtb-isolated"
  })
}

resource "aws_route_table_association" "isolated" {
  count = 2

  subnet_id      = aws_subnet.isolated[count.index].id
  route_table_id = aws_route_table.isolated.id
}

###############################################################################
# VPC Flow Logs → CloudWatch Logs
#
# Captures ALL traffic (accepted + rejected) for security investigations and
# NAT GW cost analysis. 30-day retention balances compliance needs with cost.
# For PCI-DSS or SOC 2 Type II, increase retention to 90 days and export to S3.
###############################################################################

resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = "/vpc/${var.vpc_name}/flow-logs"
  retention_in_days = 30

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-flow-logs"
  })
}

# IAM role that grants the VPC Flow Logs service permission to write to
# CloudWatch Logs. This is a service-linked pattern: the trust policy allows
# only the vpc-flow-logs.amazonaws.com service to assume the role.
resource "aws_iam_role" "flow_logs" {
  name = "${var.vpc_name}-vpc-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "VPCFlowLogsAssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        # SourceArn condition prevents confused-deputy attacks where another
        # AWS account's Flow Logs service could assume this role.
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:ec2:*:*:vpc-flow-log/*"
          }
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-vpc-flow-logs-role"
  })
}

resource "aws_iam_role_policy" "flow_logs" {
  name = "${var.vpc_name}-vpc-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CreateLogStreamAndPutEvents"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        # Scope to the specific log group rather than "*" to enforce least privilege.
        Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
      }
    ]
  })
}

resource "aws_flow_log" "this" {
  vpc_id          = aws_vpc.this.id
  traffic_type    = "ALL" # Capture ACCEPT + REJECT; use "REJECT" only if cost is a concern
  iam_role_arn    = aws_iam_role.flow_logs.arn
  log_destination = aws_cloudwatch_log_group.flow_logs.arn

  tags = merge(local.common_tags, {
    Name = "${var.vpc_name}-flow-log"
  })
}

###############################################################################
# Data Sources
###############################################################################

# Used in the Flow Logs IAM role's confused-deputy condition.
data "aws_caller_identity" "current" {}
