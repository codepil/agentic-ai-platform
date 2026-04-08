# -----------------------------------------------------------------------------
# ALB Module — Variables
# -----------------------------------------------------------------------------

variable "name" {
  description = "Base name used for all ALB resources (e.g. \"platform\")."
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod). Used in resource names and tags."
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where the ALB security group will be created."
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs across at least two AZs for ALB placement."
  type        = list(string)
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate to attach to the HTTPS (port 443) listener."
  type        = string
}

variable "access_logs_bucket" {
  description = "S3 bucket name for ALB access logs. Leave empty (\"\") to disable access logging."
  type        = string
  default     = ""
}

variable "deletion_protection" {
  description = "Enable deletion protection on the ALB. Should be true in production."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Map of additional tags to apply to all ALB resources."
  type        = map(string)
  default     = {}
}
