variable "name" {
  type = string
}

variable "sqs_queue_arn" {
  description = "ARN of the SQS queue this Lambda will consume from"
  type        = string
}

variable "sqs_results_queue_arn" {
  description = "ARN of the results SQS queue (grants sqs:SendMessage). Null if not used."
  type        = string
  default     = null
}

variable "ses_enabled" {
  description = "When true, grants ses:SendEmail to the Lambda role."
  type        = bool
  default     = false
}
