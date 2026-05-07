module "vpc" {
  source = "./network"
}

module "vpc_subnets" {
  source = "./subnets"
  vpc_id = module.vpc.id
  vpc_cidr_block = module.vpc.cidr_block
  name = "${var.name}-subnet"
}

module "vpc_internet_gateway" {
  source = "./internet_gateway"
  vpc_id = module.vpc.id
}

module "vpc_route_table" {
  source = "./route_table"
  vpc_id = module.vpc.id
  igw_id = module.vpc_internet_gateway.id
  subnet_ids = module.vpc_subnets.subnet_ids
}

module "vpc_security_group" {
  source = "./security_group"
  name   = "ecs-security-group"
  vpc_id = module.vpc.id
  from_port = 8000
  to_port = 8000
}