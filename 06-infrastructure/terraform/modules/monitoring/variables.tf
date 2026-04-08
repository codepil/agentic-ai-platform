# -----------------------------------------------------------------------------
# Monitoring Module — Variables
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod). Used in resource names and tags."
  type        = string
}

variable "alb_arn_suffix" {
  description = "The ARN suffix of the Application Load Balancer (the portion after 'app/'). Used in CloudWatch metric dimensions."
  type        = string
}

variable "cluster_name" {
  description = "Name of the ECS cluster where platform-app and agent-engine services run."
  type        = string
}

variable "platform_app_service_name" {
  description = "Name of the platform-app ECS service. Used in CloudWatch ECS metric dimensions and alarm names."
  type        = string
}

variable "agent_engine_service_name" {
  description = "Name of the agent-engine ECS service. Used in CloudWatch ECS metric dimensions and alarm names."
  type        = string
}

variable "platform_app_desired_count" {
  description = "Desired task count for the platform-app ECS service. Alarms trigger when running tasks drop below this value."
  type        = number
  default     = 1
}

variable "agent_engine_desired_count" {
  description = "Desired task count for the agent-engine ECS service. Alarms trigger when running tasks drop below this value."
  type        = number
  default     = 1
}

variable "alert_email" {
  description = "Email address that will receive SNS alert notifications for all CloudWatch alarms."
  type        = string
}

variable "tags" {
  description = "Map of additional tags applied to all taggable resources in this module."
  type        = map(string)
  default     = {}
}
