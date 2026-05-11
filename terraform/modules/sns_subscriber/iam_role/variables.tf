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

variable "sqs_results_enabled" {
  description = "Whether to grant sqs:SendMessage on the results queue. Must be a static bool — do not derive from resource attributes."
  type        = bool
  default     = false
}

variable "ses_enabled" {
  description = "When true, grants ses:SendEmail to the Lambda role."
  type        = bool
  default     = false
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB idempotency table (grants PutItem and GetItem)."
  type        = string
}
