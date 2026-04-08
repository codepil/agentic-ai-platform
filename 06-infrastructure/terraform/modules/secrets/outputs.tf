# -----------------------------------------------------------------------------
# Secrets Module — Outputs
# -----------------------------------------------------------------------------

# Single map output so the ECS module can look up any secret ARN by logical key:
#
#   module.secrets.secret_arns["mongo_uri"]
#   module.secrets.secret_arns["anthropic_api_key"]
#
# Pass individual ARNs into the ECS task definition's secrets block:
#
#   secrets = [
#     {
#       name      = "MONGO_URI"
#       valueFrom = module.secrets.secret_arns["mongo_uri"]
#     },
#     ...
#   ]

output "secret_arns" {
  description = "Map of logical secret name to Secrets Manager ARN. Keys: okta_issuer_uri, mongo_uri, anthropic_api_key, slack_webhook_url, jira_token, github_token, figma_token."
  value = {
    for key, secret in aws_secretsmanager_secret.platform :
    key => secret.arn
  }
}

output "secrets_kms_key_arn" {
  description = "ARN of the KMS CMK used to encrypt all Secrets Manager secrets. Grant this to ECS task execution role's kms:Decrypt policy so containers can read secrets at startup."
  value       = aws_kms_key.secrets.arn
}
