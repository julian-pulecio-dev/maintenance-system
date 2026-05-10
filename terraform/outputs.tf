output "ecs_cluster_name" {
  value = module.ecs_django_core.ecs_cluster_name
}

output "ecs_service_name" {
  value = module.ecs_django_core.ecs_service_name
}

output "outbox_cluster_name" {
  value = module.ecs_outbox_observer.cluster_name
}

output "outbox_service_name" {
  value = module.ecs_outbox_observer.service_name
}

output "migration_task_definition" {
  value = module.ecs_django_core.migration_task_definition
}

output "public_subnets" {
  value = module.vpc.subnet_ids
}

output "ecs_security_group" {
  value = module.vpc.security_group_id
}
