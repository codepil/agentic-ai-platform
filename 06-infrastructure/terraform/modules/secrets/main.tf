# -----------------------------------------------------------------------------
# Secrets Module — Main
#
# Creates AWS Secrets Manager secret *shells* for every credential the Agentic
# AI platform needs.  Secret values are intentionally set to a placeholder
# ("REPLACE_ME") so the resource exists in state and can be referenced by the
# ECS module, but the real values MUST be injected before deploying ECS tasks
# (either manually via the console/CLI or through a secrets-rotation pipeline).
#
# All secrets share:
#   • A single customer-managed KMS key (CMK) for encryption at rest
#   • A 7-day recovery window (protects against accidental deletion)
#   • Consistent naming: platform/{environment}/{secret-name}
# -----------------------------------------------------------------------------

locals {
  common_tags = merge(
    {
      Module      = "secrets"
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags,
  )

  # Logical name → metadata for each secret.
  # Terraform iterates over this map to create aws_secretsmanager_secret and
  # aws_secretsmanager_secret_version resources dynamically.
  secrets = {
    okta_issuer_uri = {
      path        = "platform/${var.environment}/okta-issuer-uri"
      description = "Okta OIDC issuer URI used by Spring Security for JWT validation (e.g. https://<tenant>.okta.com/oauth2/default)."
    }
    mongo_uri = {
      path        = "platform/${var.environment}/mongo-uri"
      description = "MongoDB Atlas connection URI including credentials (mongodb+srv://user:pass@cluster/db)."
    }
    anthropic_api_key = {
      path        = "platform/${var.environment}/anthropic-api-key"
      description = "Anthropic API key used by the agent-engine Python FastAPI service to call Claude models."
    }
    slack_webhook_url = {
      path        = "platform/${var.environment}/slack-webhook-url"
      description = "Slack incoming webhook URL for posting agent notifications and alerts."
    }
    jira_token = {
      path        = "platform/${var.environment}/jira-token"
      description = "Jira API token (base64-encoded email:token) for the platform integration service."
    }
    github_token = {
      path        = "platform/${var.environment}/github-token"
      description = "GitHub personal access token or GitHub App installation token for repository operations."
    }
    figma_token = {
      path        = "platform/${var.environment}/figma-token"
      description = "Figma personal access token for the design-asset retrieval agent tool."
    }
  }
}

# -----------------------------------------------------------------------------
# KMS Customer-Managed Key — shared across all Secrets Manager secrets
# -----------------------------------------------------------------------------

resource "aws_kms_key" "secrets" {
  description             = "CMK for Secrets Manager encryption (platform/${var.environment})"
  deletion_window_in_days = 30
  enable_key_rotation     = true # AWS rotates the backing key material annually

  tags = merge(local.common_tags, { Name = "platform-${var.environment}-secrets-cmk" })
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/platform-${var.environment}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# -----------------------------------------------------------------------------
# Secrets Manager Secrets — shells only (no real values stored here)
# -----------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "platform" {
  for_each = local.secrets

  name        = each.value.path
  description = each.value.description
  kms_key_id  = aws_kms_key.secrets.arn

  # 7-day soft-delete window; prevents immediate permanent deletion
  recovery_window_in_days = 7

  tags = merge(local.common_tags, { Name = each.value.path })
}

# -----------------------------------------------------------------------------
# Secret Versions — placeholder values
#
# These versions ensure each secret resource exists with a valid JSON structure
# that the ECS task definition can reference via Secrets Manager ARN.
# IMPORTANT: Replace the placeholder values before deploying ECS services.
#   Option A (manual):  AWS Console → Secrets Manager → <secret> → Retrieve/Edit
#   Option B (CLI):     aws secretsmanager put-secret-value --secret-id <arn> --secret-string '{"value":"real-value"}'
#   Option C (CI/CD):   Use a separate Terraform workspace or pipeline step that
#                       reads from a vault and calls put-secret-value.
#
# The lifecycle ignore_changes on secret_string prevents Terraform from
# overwriting values that were updated outside of Terraform after initial deploy.
# -----------------------------------------------------------------------------

resource "aws_secretsmanager_secret_version" "platform" {
  for_each = local.secrets

  secret_id     = aws_secretsmanager_secret.platform[each.key].id
  secret_string = jsonencode({ value = "REPLACE_ME" })

  lifecycle {
    # Do not overwrite real values on subsequent terraform applies
    ignore_changes = [secret_string]
  }
}
