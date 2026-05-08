module "ecs_cluster" {
  source = "./cluster"
  name   = "${var.name}-ecs-cluster"
}

module "iam_role" {
  source                 = "./iam_role"
  name                   = "${var.name}-ecsTaskExecutionRole-dockerhub"
  db_password_secret_arn = var.db_password_secret_arn
  db_user_secret_arn     = var.db_user_secret_arn
}

module "ecs_task_definition" {
  name   = "${var.name}-ecs-task-definition-app"
  source = "./task"
  iam_role_arn = module.iam_role.arn
  environment_variables = [
    { name = "DB_HOST",                  value = var.db_host },
    { name = "DB_NAME",                  value = var.db_name },
    { name = "DB_PORT",                  value = var.db_port },
    { name = "DJANGO_SETTINGS_MODULE",   value = "app.settings.base" },
    { name = "EMAIL_BACKEND",            value = var.email_backend },
    { name = "DEFAULT_FROM_EMAIL",       value = var.email_default_from },
    { name = "AWS_SES_REGION_NAME",      value = var.ses_region }
  ]
  secret_variables = [
    { name = "DB_USER",     valueFrom = var.db_user_secret_arn },
    { name = "DB_PASSWORD", valueFrom = var.db_password_secret_arn }
  ]
  container_command = []
}

module "ecs_task_definition_migrate" {
  name   = "${var.name}-ecs-task-definition-migrate"
  source = "./task"
  iam_role_arn = module.iam_role.arn
  environment_variables = [
    { name = "DB_HOST",                  value = var.db_host },
    { name = "DB_NAME",                  value = var.db_name },
    { name = "DB_PORT",                  value = var.db_port },
    { name = "DJANGO_SETTINGS_MODULE",   value = "app.settings.base" },
    { name = "EMAIL_BACKEND",            value = var.email_backend },
    { name = "DEFAULT_FROM_EMAIL",       value = var.email_default_from },
    { name = "AWS_SES_REGION_NAME",      value = var.ses_region }
  ]
  secret_variables = [
    { name = "DB_USER",     valueFrom = var.db_user_secret_arn },
    { name = "DB_PASSWORD", valueFrom = var.db_password_secret_arn }
  ]
  container_command = ["python", "manage.py", "migrate", "--noinput"]
}

module "alb" {
  source     = "./alb"
  name       = "${var.name}-alb"
  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids
}

module "ecs_service" {
  source                = "./service"
  name                  = "${var.name}-ecs-service"
  cluster_arn           = module.ecs_cluster.arn
  task_definition_arn   = module.ecs_task_definition.arn
  desired_count         = coalesce(var.desired_count, 1)
  vpc_subnets_ids       = var.subnet_ids
  vpc_security_group_id = var.security_group_id
  target_group_arn      = module.alb.target_group_arn
}

module "autoscaling" {
  source                  = "./autoscaling"
  cluster_name            = module.ecs_cluster.name
  service_name            = module.ecs_service.name
  min_capacity            = coalesce(var.min_capacity, 1)
  max_capacity            = coalesce(var.max_capacity, 10)
  alb_arn_suffix          = module.alb.arn_suffix
  target_group_arn_suffix = module.alb.target_group_arn_suffix
  requests_per_target     = var.requests_per_target
}
