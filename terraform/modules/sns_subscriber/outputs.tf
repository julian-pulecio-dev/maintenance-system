output "queue_url" {
  description = "URL of the SQS queue receiving filtered SNS messages"
  value       = aws_sqs_queue.main.url
}

output "queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.main.arn
}

output "dlq_url" {
  description = "URL of the dead-letter queue"
  value       = aws_sqs_queue.dead_letter.url
}

output "dlq_arn" {
  description = "ARN of the dead-letter queue"
  value       = aws_sqs_queue.dead_letter.arn
}

output "lambda_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.this.arn
}

output "lambda_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.this.function_name
}
