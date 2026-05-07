variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "health_check_path" {
  description = "Path used by the ALB health check"
  type        = string
  default     = "/api/schema/"
}
