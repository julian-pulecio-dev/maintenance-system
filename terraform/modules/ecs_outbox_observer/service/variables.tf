variable "name" {
  type = string
}

variable "cluster_arn" {
  type = string
}

variable "task_definition_arn" {
  type = string
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "vpc_subnets_ids" {
  type = list(string)
}

variable "vpc_security_group_id" {
  type = string
}
