# -----------------------------------------------------------------------------
# Secrets Module — Variables
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod). Embedded in every secret path: platform/{environment}/secret-name."
  type        = string
}

variable "tags" {
  description = "Map of additional tags to apply to all Secrets Manager and KMS resources."
  type        = map(string)
  default     = {}
}
