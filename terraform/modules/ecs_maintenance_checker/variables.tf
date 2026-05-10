variable "name" {
  description = "A prefix for naming AWS resources"
  type        = string
}

variable "db_name" {
  description = "The name of the database"
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
  description = "A list of subnet IDs for the ECS task"
  type        = list(string)
}

variable "security_group_id" {
  description = "The security group ID for the ECS task"
  type        = string
}

variable "schedule_expression" {
  description = "EventBridge schedule expression for triggering the maintenance check"
  type        = string
  default     = "rate(5 minutes)"
}
