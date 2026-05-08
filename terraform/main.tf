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
