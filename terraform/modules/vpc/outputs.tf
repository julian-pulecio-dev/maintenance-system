output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.id
}

output "subnet_ids" {
  value = module.vpc_subnets.subnet_ids
}

output "subnet_group_name" {
  value = module.vpc_subnets.subnet_group_name
}

output "security_group_id" {
  value = module.vpc_security_group.security_group_id
}