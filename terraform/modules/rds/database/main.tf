resource "aws_db_instance" "django_db" {
  identifier        = "${var.name}db"
  engine            = "postgres"
  engine_version    = "18.1"
  instance_class    = var.db_instance_class
  allocated_storage = 20

  db_name  = var.name
  username = var.db_user
  password = var.db_password

  publicly_accessible = false
  skip_final_snapshot = true

  db_subnet_group_name = var.db_subnet_group_name

  vpc_security_group_ids = [var.security_group_id]
}