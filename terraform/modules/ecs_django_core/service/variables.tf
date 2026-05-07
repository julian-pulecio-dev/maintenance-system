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
  type = number
}

variable "vpc_subnets_ids" {
  type = list(string)
}

variable "vpc_security_group_id" {
  type = string
}

variable "target_group_arn" {
  description = "ARN of the ALB target group to associate with the service"
  type        = string
}