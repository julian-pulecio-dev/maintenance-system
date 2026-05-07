resource "aws_ecs_service" "ecs_service" {
  name            = var.name
  cluster         = var.cluster_arn
  task_definition = var.task_definition_arn
  desired_count   = var.desired_count

  launch_type            = "FARGATE"
  enable_execute_command = true

  network_configuration {
    subnets          = var.vpc_subnets_ids
    security_groups  = [var.vpc_security_group_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "app"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 60

  wait_for_steady_state = true

  lifecycle {
    ignore_changes = [desired_count]
  }
}
