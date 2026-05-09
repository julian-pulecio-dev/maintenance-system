module "ecs_cluster" {
  source = "./cluster"
  name   = "${var.name}-outbox-cluster"
}

module "iam_role" {
  source                 = "./iam_role"
  name                   = "${var.name}-outbox-ecsTaskExecutionRole"
  db_password_secret_arn = var.db_password_secret_arn
  db_user_secret_arn     = var.db_user_secret_arn
}

module "ecs_task_definition" {
  source                = "./task"
  name                  = "${var.name}-outbox-task"
  iam_role_arn          = module.iam_role.arn
  sns_topic_arn         = var.sns_topic_arn
  sqs_results_queue_arn = var.sqs_results_queue_arn
  environment_variables = [
    { name = "DB_HOST",                value = var.db_host },
    { name = "DB_NAME",                value = var.db_name },
    { name = "DB_PORT",                value = var.db_port },
    { name = "DJANGO_SETTINGS_MODULE", value = "app.settings.base" },
    { name = "SNS_TOPIC_ARN",          value = var.sns_topic_arn },
    { name = "SQS_RESULTS_URL",        value = var.sqs_results_queue_url },
  ]
  secret_variables = [
    { name = "DB_USER",     valueFrom = var.db_user_secret_arn },
    { name = "DB_PASSWORD", valueFrom = var.db_password_secret_arn }
  ]
  container_command = ["python", "manage.py", "poll_outbox"]
}

module "ecs_service" {
  source                = "./service"
  name                  = "${var.name}-outbox-service"
  cluster_arn           = module.ecs_cluster.arn
  task_definition_arn   = module.ecs_task_definition.arn
  desired_count         = var.desired_count
  vpc_subnets_ids       = var.subnet_ids
  vpc_security_group_id = var.security_group_id
}
