data "aws_ami" "ubuntu" {
  count       = var.consumer_ami_id == null ? 1 : 0
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}
data "aws_rds_engine_version" "mysql" {
  count                  = var.db_engine_version == null ? 1 : 0
  engine                 = "mysql"
  parameter_group_family = "mysql8.4"
  default_only           = true
  latest                 = true
}
resource "aws_key_pair" "consumer" {
  count      = var.existing_key_pair_name == null ? 1 : 0
  key_name   = "${local.name}-consumer"
  public_key = var.existing_key_pair_name == null ? file(pathexpand(var.ssh_public_key_path)) : null
}
locals {
  consumer_ami_id   = var.consumer_ami_id != null ? var.consumer_ami_id : data.aws_ami.ubuntu[0].id
  db_engine_version = var.db_engine_version != null ? var.db_engine_version : data.aws_rds_engine_version.mysql[0].version_actual
  consumer_key_name = var.existing_key_pair_name != null ? var.existing_key_pair_name : aws_key_pair.consumer[0].key_name
}
output "selected_versions" {
  description = "Fixe estes valores no tfvars antes de aplicar para manter repetibilidade."
  value = {
    consumer_ami_id   = local.consumer_ami_id
    db_engine_version = local.db_engine_version
  }
}
