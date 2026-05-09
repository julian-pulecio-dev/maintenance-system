variable "name" {
  description = "Prefix for naming the SQS queues"
  type        = string
}

variable "max_receive_count" {
  description = "Number of times a message can be received before being sent to the DLQ"
  type        = number
  default     = 5
}

variable "visibility_timeout_seconds" {
  description = "Time a message is hidden after being received (should be >= your consumer processing time)"
  type        = number
  default     = 60
}

variable "message_retention_seconds" {
  description = "How long the main queue retains undelivered messages (default: 1 day)"
  type        = number
  default     = 86400
}

variable "dlq_retention_seconds" {
  description = "How long the DLQ retains failed messages before expiring (default: 14 days)"
  type        = number
  default     = 1209600
}
