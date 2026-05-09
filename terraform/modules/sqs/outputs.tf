output "queue_url" {
  description = "URL of the main SQS queue (used by producers to send messages)"
  value       = aws_sqs_queue.main.url
}

output "queue_arn" {
  description = "ARN of the main SQS queue (used for IAM policies)"
  value       = aws_sqs_queue.main.arn
}

output "dlq_url" {
  description = "URL of the dead-letter queue"
  value       = aws_sqs_queue.dead_letter.url
}

output "dlq_arn" {
  description = "ARN of the dead-letter queue (used for IAM policies)"
  value       = aws_sqs_queue.dead_letter.arn
}
