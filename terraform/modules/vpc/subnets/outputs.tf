output "subnet_ids" {
  value = aws_subnet.public[*].id
}

output "subnet_group_name" {
  value = aws_db_subnet_group.subnet_group.name
}