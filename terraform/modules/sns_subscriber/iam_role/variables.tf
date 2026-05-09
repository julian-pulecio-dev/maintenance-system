variable "name" {
  type = string
}

variable "sqs_queue_arn" {
  description = "ARN of the SQS queue this Lambda will consume from"
  type        = string
}
