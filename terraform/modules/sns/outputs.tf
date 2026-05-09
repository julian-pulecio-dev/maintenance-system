output "topic_arn" {
  description = "ARN of the SNS topic (used by producers and IAM policies)"
  value       = aws_sns_topic.this.arn
}
