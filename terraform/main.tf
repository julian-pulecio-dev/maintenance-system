data "aws_secretsmanager_secret" "db_password" {
  name = var.db_password_secret_name
}

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = data.aws_secretsmanager_secret.db_password.id
}

data "aws_secretsmanager_secret" "db_user" {
  name = var.db_user_secret_name
}

data "aws_secretsmanager_secret_version" "db_user" {
  secret_id = data.aws_secretsmanager_secret.db_user.id
}


module "vpc" {
  source = "./modules/vpc"
  name = "${var.name}-vpc"
}

module "rds" {
  source                     = "./modules/rds"
  vpc_id                     = module.vpc.vpc_id
  allowed_security_group_ids = [module.vpc.security_group_id]
  db_name                    = var.db_name
  db_user                    = data.aws_secretsmanager_secret_version.db_user.secret_string
  db_password                = data.aws_secretsmanager_secret_version.db_password.secret_string
  subnet_group_name          = module.vpc.subnet_group_name
}

module "sns_outbox_observer" {
  source = "./modules/sns"
  name   = "${var.name}-observer"
}

module "sqs_outbox_results" {
  source = "./modules/sqs"
  name   = "${var.name}-results"
}

module "ecs_outbox_observer" {
  source                 = "./modules/ecs_outbox_observer"
  name                   = "${var.name}-ecs"
  db_name                = var.db_name
  db_user_secret_arn     = data.aws_secretsmanager_secret.db_user.arn
  db_password_secret_arn = data.aws_secretsmanager_secret.db_password.arn
  db_host                = module.rds.database_host
  db_port                = module.rds.database_port
  subnet_ids             = module.vpc.subnet_ids
  security_group_id      = module.vpc.security_group_id
  sns_topic_arn          = module.sns_outbox_observer.topic_arn
  sqs_results_queue_url  = module.sqs_outbox_results.queue_url
  sqs_results_queue_arn  = module.sqs_outbox_results.queue_arn
}


module "ecs_django_core" {
  source                 = "./modules/ecs_django_core"
  name                   = "${var.name}-ecs"
  vpc_id                 = module.vpc.vpc_id
  db_name                = var.db_name
  db_user_secret_arn     = data.aws_secretsmanager_secret.db_user.arn
  db_password_secret_arn = data.aws_secretsmanager_secret.db_password.arn
  db_host                = module.rds.database_host
  db_port                = module.rds.database_port
  email_default_from     = var.email_default_from
  email_backend          = var.email_backend
  subnet_ids             = module.vpc.subnet_ids
  security_group_id      = module.vpc.security_group_id
  desired_count          = var.ecs_desired_count
}

module "ecs_maintenance_checker" {
  source                 = "./modules/ecs_maintenance_checker"
  name                   = "${var.name}-ecs"
  db_name                = var.db_name
  db_user_secret_arn     = data.aws_secretsmanager_secret.db_user.arn
  db_password_secret_arn = data.aws_secretsmanager_secret.db_password.arn
  db_host                = module.rds.database_host
  db_port                = module.rds.database_port
  subnet_ids             = module.vpc.subnet_ids
  security_group_id      = module.vpc.security_group_id
}

module "asset_email_notifier_worker" {
  source             = "./modules/sns_subscriber"
  name               = "${var.name}-asset-email-notifier-worker"
  sns_topic_arn      = module.sns_outbox_observer.topic_arn
  filter_event_types = ["asset.created", "asset.updated", "asset.deleted"]
  source_dir         = "${path.root}/../lambdas/asset_email_notifier"
  shared_dir         = "${path.root}/../lambdas/shared"

  sqs_results_queue_url = module.sqs_outbox_results.queue_url
  sqs_results_queue_arn = module.sqs_outbox_results.queue_arn
  ses_from_email        = var.email_default_from
}

module "work_order_email_notifier_worker" {
  source             = "./modules/sns_subscriber"
  name               = "${var.name}-work-order-notifier"
  sns_topic_arn      = module.sns_outbox_observer.topic_arn
  filter_event_types = [
                        "work_order.created",
                        "work_order.updated",
                        "work_order.deleted",
                        "work_order.assigned",
                        "work_order.started",
                        "work_order.put_on_hold",
                        "work_order.completed",
                        "work_order.cancelled",
                        "work_order.restored",
                        ]
  source_dir         = "${path.root}/../lambdas/work_order_email_notifier"
  shared_dir         = "${path.root}/../lambdas/shared"

  sqs_results_queue_url = module.sqs_outbox_results.queue_url
  sqs_results_queue_arn = module.sqs_outbox_results.queue_arn
  ses_from_email        = var.email_default_from
}

module "asset_maintenance_email_notifier_worker" {
  source             = "./modules/sns_subscriber"
  name               = "${var.name}-asset-maint-notifier"
  sns_topic_arn      = module.sns_outbox_observer.topic_arn
  filter_event_types = ["asset.maintenance.upcoming", "asset.maintenance.overdue"]
  source_dir         = "${path.root}/../lambdas/asset_maintenance_email_notifier"
  shared_dir         = "${path.root}/../lambdas/shared"

  sqs_results_queue_url = module.sqs_outbox_results.queue_url
  sqs_results_queue_arn = module.sqs_outbox_results.queue_arn
  ses_from_email        = var.email_default_from
}
