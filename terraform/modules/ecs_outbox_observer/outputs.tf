output "cluster_name" {
  value = module.ecs_cluster.name
}

output "service_name" {
  value = module.ecs_service.name
}

output "log_group_name" {
  value = module.ecs_task_definition.log_group_name
}
