variable "vpc_id" {
  description = "The ID of the VPC"
  type        = string
}

variable "allowed_security_group_ids" {
  description = "The IDs of the security groups to allow access to RDS"
  type        = list(string)
}

variable "db_name" {
  description = "The name of the database"
  type        = string
}

variable "db_user" {
  description = "The database username"
  type        = string
}

variable "db_password" {
  description = "The database password"
  type        = string
}

variable "subnet_group_name" {
  description = "The name of the subnet group for the RDS instance"
  type        = string
}