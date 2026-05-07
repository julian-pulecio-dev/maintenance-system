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

variable "email_host" {
  description = "SMTP host for sending emails"
  type        = string
}

variable "email_port" {
  description = "SMTP port for sending emails"
  type        = number
}

variable "email_host_user" {
  description = "SMTP username for sending emails"
  type        = string
}

variable "email_host_password" {
  description = "SMTP password for sending emails"
  type        = string
}

variable "email_default_from" {
  description = "Default 'from' email address for outgoing emails"
  type        = string
}

variable "email_backend" {
  description = "Email backend to use for sending emails"
  type        = string
}