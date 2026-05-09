variable "db_name" {
  type = string
}

variable "db_user_secret_name" {
  description = "Name of the AWS Secrets Manager secret that holds the DB username"
  type        = string
}

variable "db_password_secret_name" {
  description = "Name of the AWS Secrets Manager secret that holds the DB password"
  type        = string
}

variable "name" {
  type = string
}

variable "ecs_desired_count" {
  type     = number
  default  = null
  nullable = true
}

variable "cors_allowed_origins" {
  description = "List of origins allowed to make cross-origin requests to the S3 bucket"
  type        = list(string)
  default     = ["*"]
}

variable "email_backend" {
  description = "Email backend to use for sending emails"
  type        = string
  default     = "django_ses.SESBackend"
}

variable "email_default_from" {
  description = "Default 'from' address for outgoing emails (must be verified in SES)"
  type        = string
}

variable "outbox_observer_schedule" {
  description = "EventBridge Scheduler expression for the outbox observer Lambda. Examples: 'rate(5 minutes)', 'rate(1 hour)', 'cron(0/10 * * * ? *)'"
  type        = string
  default     = "rate(5 minutes)"
}
