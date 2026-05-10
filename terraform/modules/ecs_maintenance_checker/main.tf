module "ecs_cluster" {
  source = "./cluster"
  name   = "${var.name}-maintenance-cluster"
}

module "iam_role" {
  source                 = "./iam_role"
  name                   = "${var.name}-maintenance-ecsTaskExecutionRole"
  db_password_secret_arn = var.db_password_secret_arn
  db_user_secret_arn     = var.db_user_secret_arn
}

resource "aws_cloudwatch_log_group" "ecs_app" {
  name              = "/ecs/${var.name}-maintenance-task"
  retention_in_days = 14
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.name}-maintenance-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.name}-maintenance-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"

  execution_role_arn = module.iam_role.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = "julianpuleciodev/maintenance-system"
      essential = true
      command   = ["python", "manage.py", "check_maintenance"]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs_app.name
          awslogs-region        = "us-east-1"
          awslogs-stream-prefix = "app"
        }
      }

      environment = [
        { name = "DB_HOST",                value = var.db_host },
        { name = "DB_NAME",                value = var.db_name },
        { name = "DB_PORT",                value = tostring(var.db_port) },
        { name = "DJANGO_SETTINGS_MODULE", value = "app.settings.base" },
      ]
      secrets = [
        { name = "DB_USER",     valueFrom = var.db_user_secret_arn },
        { name = "DB_PASSWORD", valueFrom = var.db_password_secret_arn },
      ]
    }
  ])
}

resource "aws_iam_role" "eventbridge" {
  name = "${var.name}-maintenance-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "eventbridge_run_task" {
  name = "${var.name}-maintenance-eventbridge-run-task"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.app.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [module.iam_role.arn, aws_iam_role.ecs_task.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eventbridge_run_task_attach" {
  role       = aws_iam_role.eventbridge.name
  policy_arn = aws_iam_policy.eventbridge_run_task.arn
}

resource "aws_cloudwatch_event_rule" "maintenance_check" {
  name                = "${var.name}-maintenance-check"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "maintenance_check" {
  rule     = aws_cloudwatch_event_rule.maintenance_check.name
  arn      = module.ecs_cluster.arn
  role_arn = aws_iam_role.eventbridge.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.app.arn
    task_count          = 1
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = var.subnet_ids
      security_groups  = [var.security_group_id]
      assign_public_ip = true
    }
  }
}
