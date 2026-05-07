variable "name" {
  type = string
}

variable "db_user" {
  type = string
}

variable "db_password" {
  sensitive = true
}

variable "db_instance_class" {
  type = string
}

variable "security_group_id" {
  type = string
}

variable "db_subnet_group_name" {
  type = string
}