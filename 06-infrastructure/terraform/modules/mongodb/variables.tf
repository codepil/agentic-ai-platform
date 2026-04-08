# -----------------------------------------------------------------------------
# MongoDB Atlas Module — Variables
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod). Used in resource names and tags."
  type        = string
}

variable "project_name" {
  description = "Name of the MongoDB Atlas project to create (e.g. \"agentic-ai-platform\")."
  type        = string
}

variable "atlas_org_id" {
  description = "MongoDB Atlas Organization ID under which the project will be created."
  type        = string
  sensitive   = true
}

variable "instance_size" {
  description = "MongoDB Atlas cluster instance size. Use M10 for dev/staging and M30 for production."
  type        = string
  default     = "M30"

  validation {
    condition     = can(regex("^M(10|20|30|40|50|60|80|140|200|300)$", var.instance_size))
    error_message = "instance_size must be a valid Atlas tier such as M10, M30, or M40."
  }
}

variable "vpc_id" {
  description = "ID of the AWS VPC used to create the PrivateLink endpoint."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC. Only this CIDR will be added to the Atlas IP access list, blocking all public internet access."
  type        = string
}

variable "isolated_subnet_ids" {
  description = "List of isolated/private subnet IDs in which the AWS VPC endpoint interface will be placed."
  type        = list(string)
}

variable "aws_region" {
  description = "AWS region where the VPC endpoint and associated resources will be deployed."
  type        = string
  default     = "us-east-1"
}

variable "mongo_password_secret_arn" {
  description = "ARN of the AWS Secrets Manager secret that holds the MongoDB application user password."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Map of additional tags applied to all taggable AWS resources in this module."
  type        = map(string)
  default     = {}
}
