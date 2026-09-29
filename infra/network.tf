locals {
  name                 = "eletrometry-${var.environment}"
  zones                = { for index, zone in var.availability_zones : tostring(index) => zone }
  vpc_id               = aws_vpc.main.id
  consumer_subnet_id   = aws_subnet.public["0"].id
  db_subnet_group_name = aws_db_subnet_group.main.name
  consumer_sg_ids      = [aws_security_group.consumer.id]
  db_sg_ids            = [aws_security_group.database.id]
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = local.name }
}

resource "aws_internet_gateway" "main" {
  vpc_id = local.vpc_id
  tags   = { Name = "${local.name}-igw" }
}

resource "aws_subnet" "public" {
  for_each                = local.zones
  vpc_id                  = local.vpc_id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, tonumber(each.key))
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-public-${each.key}", FutureUse = "ALB-stage-2" }
}

resource "aws_subnet" "database" {
  for_each                = local.zones
  vpc_id                  = local.vpc_id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, tonumber(each.key) + 10)
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-db-${each.key}" }
}

resource "aws_route_table" "public" {
  vpc_id = local.vpc_id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${local.name}-public" }
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "database" {
  vpc_id = local.vpc_id
  tags   = { Name = "${local.name}-database-local-only" }
}

resource "aws_route_table_association" "database" {
  for_each       = aws_subnet.database
  subnet_id      = each.value.id
  route_table_id = aws_route_table.database.id
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-mysql"
  subnet_ids = [for subnet in aws_subnet.database : subnet.id]
}
