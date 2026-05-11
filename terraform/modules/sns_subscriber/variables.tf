variable "name" {
  description = "Prefix for all resources created by this module"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic to subscribe to"
  type        = string
}

variable "filter_event_types" {
  description = "List of event_type values to filter on (e.g. ['asset.created', 'asset.updated'])"
  type        = list(string)
}

variable "source_dir" {
  description = "Absolute path to the Lambda source directory (will be zipped automatically)"
  type        = string
}

variable "lambda_handler" {
  description = "Lambda handler in the format file.function (e.g. 'handler.handle')"
  type        = string
  default     = "handler.handle"
}

variable "lambda_runtime" {
  description = "Lambda runtime identifier"
  type        = string
  default     = "python3.12"
}

variable "lambda_timeout" {
  description = "Lambda execution timeout in seconds"
  type        = number
  default     = 30
}

variable "environment_variables" {
  description = "Environment variables to inject into the Lambda function"
  type        = map(string)
  default     = {}
}

variable "max_receive_count" {
  description = "Number of times a message can be received before being sent to the DLQ"
  type        = number
  default     = 3
}

variable "ses_from_email" {
  description = "Verified SES sender address. When set, injected as SES_FROM_EMAIL and grants ses:SendEmail to the Lambda role."
  type        = string
  default     = null
}

variable "sqs_results_queue_url" {
  description = "URL of the results SQS queue. When set, injected as SQS_RESULTS_URL env var in the Lambda."
  type        = string
  default     = null
}

variable "sqs_results_queue_arn" {
  description = "ARN of the results SQS queue. When set, grants sqs:SendMessage to the Lambda role."
  type        = string
  default     = null
}

variable "sqs_results_enabled" {
  description = "Set to true when sqs_results_queue_arn is provided. Must be a static bool — Terraform cannot use the ARN itself in a count condition."
  type        = bool
  default     = false
}
