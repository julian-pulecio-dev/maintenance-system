resource "aws_security_group" "ecs" {
  name   = var.name
  vpc_id = var.vpc_id

  ingress {
    from_port   = var.from_port
    to_port     = var.to_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    security_groups = var.allowed_security_group_ids != [] ? var.allowed_security_group_ids : null
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
