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

variable "desired_count" {
  description = "Number of ECS tasks to run. Set to 0 before destroy."
  type        = number
  default     = 1
  nullable    = false
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic the outbox observer publishes events to"
  type        = string
}

variable "sqs_results_queue_url" {
  description = "URL of the results SQS queue the observer consumes worker acknowledgements from"
  type        = string
}

variable "sqs_results_queue_arn" {
  description = "ARN of the results SQS queue (grants sqs:ReceiveMessage and sqs:DeleteMessage)"
  type        = string
}
