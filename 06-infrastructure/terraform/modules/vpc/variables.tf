variable "vpc_name" {
  description = "Name prefix applied to all resources in this module. Used to construct resource Name tags and logical identifiers (e.g., 'agentic-ai' produces 'agentic-ai-vpc', 'agentic-ai-igw', etc.)."
  type        = string
}

variable "environment" {
  description = "Deployment environment name (e.g., 'dev', 'staging', 'prod'). Used in resource Name tags and log group names so operators can distinguish resources across environments in the AWS console."
  type        = string
}

variable "azs" {
  description = "List of exactly two Availability Zone names to deploy into (e.g., ['us-east-1a', 'us-east-1b']). Exactly two AZs are required: one public + one private + one isolated subnet is created per AZ, producing 6 subnets total. The module uses index 0 for the first AZ and index 1 for the second."
  type        = list(string)

  validation {
    condition     = length(var.azs) == 2
    error_message = "Exactly 2 availability zones must be provided."
  }
}

variable "tags" {
  description = "Map of additional tags to merge onto every resource in this module. These are merged with the module-generated Name tag; caller-supplied tags take precedence if keys conflict. Typical keys: Owner, CostCenter, Project, Terraform."
  type        = map(string)
  default     = {}
}
