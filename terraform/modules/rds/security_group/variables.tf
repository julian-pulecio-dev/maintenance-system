variable "name" {
    type = string
}

variable "vpc_id" {
    type = string
}

variable "from_port" {
  type = number
}

variable "to_port" {
  type = number
}

variable "allowed_security_group_ids" {
  type = list(string)
  default = []
}