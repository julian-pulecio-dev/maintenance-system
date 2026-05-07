output "host" {
  value = aws_db_instance.django_db.address
}

output "port" {
  value = aws_db_instance.django_db.port 
}