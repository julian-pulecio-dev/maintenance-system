variable "name" {
    description = "A prefix for naming AWS resources"
    type        = string
}

variable "db_name" {
    description = "The name of the database to create in RDS"
    type        = string
}

variable "db_user_secret_arn" {
    description = "ARN of the Secrets Manager secret holding the DB username"
    type        = string
}

variable "db_password_secret_arn" {
    description = "ARN of the Secrets Manager secret holding the DB password"
    type        = string
}

variable "db_host" {
    description = "The hostname of the database"
    type        = string
}

variable "db_port" {
    description = "The port of the database"
    type        = string
}

variable "subnet_ids" {
    description = "A list of subnet IDs for the ECS tasks"
    type        = list(string)
}

variable "security_group_id" {
    description = "The security group ID for the ECS tasks"
    type        = string
}

variable "desired_count" {
  description = "Number of ECS tasks to run. Set to 0 before destroy."
  type        = number
  default     = null
  nullable    = true
}

variable "vpc_id" {
  description = "The VPC ID (required by the ALB)"
  type        = string
}

variable "min_capacity" {
  description = "Minimum number of ECS tasks for autoscaling"
  type        = number
  default     = null
  nullable    = true
}

variable "max_capacity" {
  description = "Maximum number of ECS tasks for autoscaling"
  type        = number
  default     = null
  nullable    = true
}

variable "requests_per_target" {
  description = "Target requests per task per minute before scaling out"
  type        = number
  default     = 1000
}

variable "email_backend" {
  description = "Email backend to use for sending emails"
  type        = string
}

variable "email_default_from" {
  description = "Default 'from' email address for outgoing emails"
  type        = string
}

variable "ses_region" {
  description = "AWS region for SES"
  type        = string
  default     = "us-east-1"
}

