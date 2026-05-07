variable "name" {
    type = string
}

variable "db_password_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the DB password"
  type        = string
}

variable "db_user_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the DB username"
  type        = string
}