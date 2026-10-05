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
  default_only           = false
  latest                 = true
}
resource "aws_key_pair" "consumer" {
  count      = var.existing_key_pair_name == null ? 1 : 0
  key_name   = "${local.name}-consumer"
  public_key = var.existing_key_pair_name == null ? (var.ssh_public_key_path != null ? file(pathexpand(var.ssh_public_key_path)) : tls_private_key.consumer[0].public_key_openssh) : null
}
locals {
  consumer_ami_id   = var.consumer_ami_id != null ? var.consumer_ami_id : data.aws_ami.ubuntu[0].id
  db_engine_version = var.db_engine_version != null ? var.db_engine_version : data.aws_rds_engine_version.mysql[0].version_actual
  consumer_key_name = var.existing_key_pair_name != null ? var.existing_key_pair_name : aws_key_pair.consumer[0].key_name
}
output "selected_versions" {
  description = "Versoes escolhidas; opcionalmente fixe no tfvars para futuras recriacoes."
  value = {
    consumer_ami_id   = local.consumer_ami_id
    db_engine_version = local.db_engine_version
  }
}

locals {
  generate_ssh_key = var.existing_key_pair_name == null && var.ssh_public_key_path == null
  private_key_path = "${path.module}/access/eletrometry.pem"
}
resource "tls_private_key" "consumer" {
  count     = local.generate_ssh_key ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}
resource "local_sensitive_file" "ssh_key" {
  count                = local.generate_ssh_key ? 1 : 0
  filename             = local.private_key_path
  content              = tls_private_key.consumer[0].private_key_pem
  file_permission      = "0600"
  directory_permission = "0700"
}
data "http" "admin_ip" {
  count              = var.admin_ipv4_cidr == null ? 1 : 0
  url                = "https://checkip.amazonaws.com"
  request_timeout_ms = 10000
  retry { attempts = 2 }
}
locals {
  admin_ipv4_cidr = var.admin_ipv4_cidr != null ? var.admin_ipv4_cidr : "${trimspace(data.http.admin_ip[0].response_body)}/32"
}

# Endpoint da propria conta; evita IDs/hostnames fixos no simulador.
data "aws_iot_endpoint" "telemetry" {
  endpoint_type = "iot:Data-ATS"
}
