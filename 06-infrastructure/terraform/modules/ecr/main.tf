# -----------------------------------------------------------------------------
# ECR Module — Main
#
# Creates two private ECR repositories for the Agentic AI platform:
#   • platform-app   — Java Spring Boot service
#   • agent-engine   — Python FastAPI agent orchestration service
#
# Both repositories share:
#   • Immutable image tags (prevents tag mutation; enforce semver/SHA tagging)
#   • Image scanning on every push (Basic scanning via ECR)
#   • KMS customer-managed encryption (one shared CMK for both repos)
#   • Lifecycle policies: keep last 10 tagged; expire untagged after 1 day
#   • Repository policies granting GitHub Actions push and ECS pull rights
# -----------------------------------------------------------------------------

locals {
  common_tags = merge(
    {
      Module      = "ecr"
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

# -----------------------------------------------------------------------------
# KMS Customer-Managed Key — shared across both ECR repositories
# -----------------------------------------------------------------------------

resource "aws_kms_key" "ecr" {
  description             = "CMK for ECR image encryption (${var.environment})"
  deletion_window_in_days = 30
  enable_key_rotation     = true # Rotate the backing key material annually

  tags = merge(local.common_tags, { Name = "platform-${var.environment}-ecr-cmk" })
}

resource "aws_kms_alias" "ecr" {
  name          = "alias/platform-${var.environment}-ecr"
  target_key_id = aws_kms_key.ecr.key_id
}

# -----------------------------------------------------------------------------
# Repository — platform-app (Java Spring Boot)
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "platform_app" {
  name                 = "platform-${var.environment}/platform-app"
  image_tag_mutability = "IMMUTABLE" # Tags cannot be overwritten; enforce immutable deploys

  image_scanning_configuration {
    scan_on_push = true # Runs Basic ECR scanning on every docker push
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }

  tags = merge(local.common_tags, { Name = "platform-${var.environment}/platform-app" })
}

# -----------------------------------------------------------------------------
# Repository — agent-engine (Python FastAPI)
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "agent_engine" {
  name                 = "platform-${var.environment}/agent-engine"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }

  tags = merge(local.common_tags, { Name = "platform-${var.environment}/agent-engine" })
}

# -----------------------------------------------------------------------------
# Lifecycle Policy — reusable JSON template
# Rule 1: Keep the 10 most recent images tagged with any tag (semver, SHA, etc.)
# Rule 2: Expire untagged (dangling) images after 1 day to control storage costs
# -----------------------------------------------------------------------------

locals {
  lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 10 tagged images"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = ["v", "sha-", "release-"]
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Expire untagged (dangling) images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "platform_app" {
  repository = aws_ecr_repository.platform_app.name
  policy     = local.lifecycle_policy
}

resource "aws_ecr_lifecycle_policy" "agent_engine" {
  repository = aws_ecr_repository.agent_engine.name
  policy     = local.lifecycle_policy
}

# -----------------------------------------------------------------------------
# Repository Policy — reusable IAM document
# • GitHub Actions OIDC role: push (ecr:PutImage + layer uploads + auth token)
# • ECS task execution role: pull (GetDownloadUrlForLayer + BatchGetImage + BatchCheckLayerAvailability)
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "ecr_access" {
  # Allow GitHub Actions to push images (CI/CD pipeline)
  statement {
    sid    = "AllowGitHubActionsPush"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [var.github_actions_role_arn]
    }

    actions = [
      "ecr:GetAuthorizationToken",         # Authenticate to the registry
      "ecr:BatchCheckLayerAvailability",   # Check which layers already exist
      "ecr:InitiateLayerUpload",           # Start a layer upload session
      "ecr:UploadLayerPart",               # Upload a layer chunk
      "ecr:CompleteLayerUpload",           # Finalise the layer upload
      "ecr:PutImage",                      # Write the image manifest
      "ecr:DescribeImages",                # Inspect existing images during CI checks
      "ecr:ListImages",                    # List images for tag existence checks
    ]
  }

  # Allow the ECS task execution role to pull images at container start
  statement {
    sid    = "AllowECSPull"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [var.ecs_execution_role_arn]
    }

    actions = [
      "ecr:GetDownloadUrlForLayer",      # Retrieve layer download URL
      "ecr:BatchGetImage",               # Pull image manifest
      "ecr:BatchCheckLayerAvailability", # Verify layers before pulling
    ]
  }
}

resource "aws_ecr_repository_policy" "platform_app" {
  repository = aws_ecr_repository.platform_app.name
  policy     = data.aws_iam_policy_document.ecr_access.json
}

resource "aws_ecr_repository_policy" "agent_engine" {
  repository = aws_ecr_repository.agent_engine.name
  policy     = data.aws_iam_policy_document.ecr_access.json
}
