# -----------------------------------------------------------------------------
# Dev Environment — Provider & Backend Versions
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.14"
    }
  }

  # ---------------------------------------------------------------------------
  # Remote State Backend (S3 + DynamoDB)
  #
  # Uncomment and fill in the values below after running the bootstrap script
  # described in the README (terraform/README.md → "First-time setup").
  #
  # Pre-requisites:
  #   1. S3 bucket:      aws s3api create-bucket --bucket <YOUR_BUCKET> ...
  #   2. DynamoDB table: aws dynamodb create-table --table-name terraform-locks ...
  #   3. Run:            terraform init -reconfigure
  # ---------------------------------------------------------------------------
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "agentic-ai-platform/dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

# -----------------------------------------------------------------------------
# AWS Provider
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "agentic-ai-platform"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# MongoDB Atlas Provider
#
# Credentials are read from environment variables to avoid storing secrets in
# source control:
#   export MONGODB_ATLAS_PUBLIC_KEY="<your-public-key>"
#   export MONGODB_ATLAS_PRIVATE_KEY="<your-private-key>"
# -----------------------------------------------------------------------------

provider "mongodbatlas" {
  # public_key  = var.atlas_public_key   # prefer env var MONGODB_ATLAS_PUBLIC_KEY
  # private_key = var.atlas_private_key  # prefer env var MONGODB_ATLAS_PRIVATE_KEY
}
