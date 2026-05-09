data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/builds/${var.name}.zip"
}

resource "aws_sqs_queue" "dead_letter" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "main" {
  name                       = "${var.name}-queue"
  # Must be >= Lambda timeout; 6x is the AWS recommendation
  visibility_timeout_seconds = var.lambda_timeout * 6

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_sqs_queue_policy" "allow_sns" {
  queue_url = aws_sqs_queue.main.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.main.arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = var.sns_topic_arn }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "this" {
  topic_arn            = var.sns_topic_arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.main.arn
  raw_message_delivery = true

  filter_policy_scope = "MessageAttributes"
  filter_policy = jsonencode({
    event_type = var.filter_event_types
  })

  # The queue policy must exist before SNS can deliver any message.
  # Without this, Terraform may create the subscription before the policy
  # is propagated, causing silent delivery failures.
  depends_on = [aws_sqs_queue_policy.allow_sns]
}

module "iam_role" {
  source        = "./iam_role"
  name          = var.name
  sqs_queue_arn = aws_sqs_queue.main.arn
}

resource "aws_lambda_function" "this" {
  function_name = "${var.name}-handler"
  role          = module.iam_role.arn
  filename      = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  handler       = var.lambda_handler
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }
}

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.main.arn
  function_name    = aws_lambda_function.this.arn
  batch_size       = 10
}
