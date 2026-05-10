resource "aws_iam_role" "lambda" {
  name = "${var.name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "sqs_consume" {
  name = "${var.name}-sqs-consume"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = [var.sqs_queue_arn]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sqs_consume_attach" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.sqs_consume.arn
}

resource "aws_iam_policy" "sqs_results_publish" {
  count = var.sqs_results_queue_arn != null ? 1 : 0
  name  = "${var.name}-sqs-results-publish"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = [var.sqs_results_queue_arn]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sqs_results_publish_attach" {
  count      = var.sqs_results_queue_arn != null ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.sqs_results_publish[0].arn
}

resource "aws_iam_policy" "dynamodb_idempotency" {
  name = "${var.name}-dynamodb-idempotency"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:PutItem", "dynamodb:GetItem"]
      Resource = [var.dynamodb_table_arn]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dynamodb_idempotency_attach" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.dynamodb_idempotency.arn
}

resource "aws_iam_policy" "ses_send" {
  count = var.ses_enabled ? 1 : 0
  name  = "${var.name}-ses-send"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ses:SendEmail"]
      Resource = ["*"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ses_send_attach" {
  count      = var.ses_enabled ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.ses_send[0].arn
}
