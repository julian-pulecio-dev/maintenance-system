output "arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda.arn
}
