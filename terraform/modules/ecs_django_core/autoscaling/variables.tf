variable "cluster_name" {
  type = string
}

variable "service_name" {
  type = string
}

variable "min_capacity" {
  description = "Minimum number of ECS tasks"
  type        = number
  default     = 2
}

variable "max_capacity" {
  description = "Maximum number of ECS tasks"
  type        = number
  default     = 10
}

variable "alb_arn_suffix" {
  description = "ARN suffix of the ALB (used for the ALBRequestCountPerTarget metric)"
  type        = string
}

variable "target_group_arn_suffix" {
  description = "ARN suffix of the ALB target group"
  type        = string
}

variable "requests_per_target" {
  description = "Target number of requests per task per minute before scaling out"
  type        = number
  default     = 1000
}
