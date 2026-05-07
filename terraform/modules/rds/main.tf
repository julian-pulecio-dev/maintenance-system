module "rds_security_group" {
  source = "./security_group"
  name   = "rds-security-group"
  vpc_id = var.vpc_id
  from_port = 5432
  to_port = 5432
  allowed_security_group_ids = var.allowed_security_group_ids
}

module "rds_database" {
  source = "./database"
  name = var.db_name
  db_user = var.db_user
  db_password = var.db_password
  db_instance_class = "db.t3.micro"
  db_subnet_group_name = var.subnet_group_name
  security_group_id = module.rds_security_group.security_group_id
}