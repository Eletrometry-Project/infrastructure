variable "observability_instance_type" {
  description = "EC2 exclusiva para Grafana e Neo4j (minimo 4 GiB nesta configuracao)."
  type        = string
  default     = "t3.medium"
  validation {
    condition     = contains(["t3.medium", "t3.large", "t3.xlarge"], var.observability_instance_type)
    error_message = "Use t3.medium ou maior dentre os tipos listados; Neo4j e Grafana precisam de memoria."
  }
}
variable "ui_allowed_ipv4_cidrs" {
  description = "IPs autorizados para Grafana e Neo4j. Vazio usa o IP administrativo atual."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for cidr in var.ui_allowed_ipv4_cidrs : can(cidrnetmask(cidr)) && can(regex("/32$", cidr)) && cidr != "0.0.0.0/32"])
    error_message = "Use IPv4/32 individuais."
  }
}
locals {
  ui_cidrs = length(var.ui_allowed_ipv4_cidrs) > 0 ? var.ui_allowed_ipv4_cidrs : toset([local.admin_ipv4_cidr])
}
resource "random_password" "grafana_admin" {
  length  = 32
  special = false
}
resource "random_password" "grafana_reader" {
  length  = 32
  special = false
}
resource "random_password" "neo4j" {
  length  = 32
  special = false
}
resource "aws_security_group" "observability" {
  name_prefix = "${local.name}-paineis-"
  description = "Grafana e Neo4j; acesso administrativo individual"
  vpc_id      = local.vpc_id
}
resource "aws_vpc_security_group_egress_rule" "observability" {
  security_group_id = aws_security_group.observability.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
resource "aws_vpc_security_group_ingress_rule" "grafana_mysql" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.observability.id
  ip_protocol                  = "tcp"
  from_port                    = 3306
  to_port                      = 3306
  description                  = "Leitura do Grafana no RDS"
}
resource "aws_vpc_security_group_ingress_rule" "neo4j_http" {
  for_each          = local.ui_cidrs
  security_group_id = aws_security_group.observability.id
  ip_protocol       = "tcp"
  from_port         = 7474
  to_port           = 7474
  cidr_ipv4         = each.value
}
resource "aws_vpc_security_group_ingress_rule" "neo4j_bolt" {
  for_each          = local.ui_cidrs
  security_group_id = aws_security_group.observability.id
  ip_protocol       = "tcp"
  from_port         = 7687
  to_port           = 7687
  cidr_ipv4         = each.value
}
resource "aws_eip" "observability" {
  domain = "vpc"
  tags   = { Name = "${local.name}-paineis", Stage = "2-paineis" }
}
locals {
  observability_runtime = {
    db_host          = aws_db_instance.mysql.address
    db_name          = var.db_initial_database_name
    admin_user       = var.db_master_username
    admin_password   = random_password.admin.result
    mysql_password   = random_password.grafana_reader.result
    grafana_password = random_password.grafana_admin.result
    neo4j_password   = random_password.neo4j.result
    grafana_url      = "http://${aws_lb.grafana.dns_name}"
    public_ip        = aws_eip.observability.public_ip
  }
  observability_sources = concat(
    [for name in ["install.sh", "configure.py", "health.py", "build_dashboard.py", "dashboard_sql.py", "analysis_rules.json", "eletrometry-bootstrap.service"] : {
      path = "/opt/eletrometry-observability/${name}", mode = "0644", content = file("${path.module}/../observability/${name}")
    }],
    [for name in ["Dockerfile", "health.sh", "eletrometry-neo4j.service"] : {
      path = "/opt/eletrometry-observability/neo4j/${name}", mode = "0644", content = file("${path.module}/../observability/neo4j/${name}")
    }],
    [
    { path = "/etc/eletrometry-observability/bootstrap.json", mode = "0600", content = jsonencode(local.observability_runtime) }]
  )
  observability_cloud_init = "#cloud-config\n${jsonencode({
    write_files = [for item in local.observability_sources : {
      path = item.path, permissions = item.mode, owner = "root:root", content = item.content
    }]
    runcmd = [
      ["cp", "/opt/eletrometry-observability/eletrometry-bootstrap.service", "/etc/systemd/system/eletrometry-bootstrap.service"],
      ["systemctl", "daemon-reload"],
      ["systemctl", "enable", "--now", "--no-block", "eletrometry-bootstrap.service"]
    ]
  })}"
}
resource "aws_instance" "observability" {
  ami                         = local.consumer_ami_id
  instance_type               = var.observability_instance_type
  subnet_id                   = local.consumer_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.observability.id]
  key_name                    = local.consumer_key_name
  iam_instance_profile        = local.instance_profile_name
  user_data_base64            = base64gzip(local.observability_cloud_init)
  user_data_replace_on_change = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  tags = { Name = "${local.name}-paineis", Stage = "2-paineis" }
  lifecycle {
    # Preserva os dados locais do Neo4j em atualizacoes de codigo/AMI.
    # Reinstalacao de software: lab.ps1 reparar-paineis; troca de AMI exige migracao planejada.
    ignore_changes = [ami, user_data_base64]
    precondition {
      condition     = length(base64gzip(local.observability_cloud_init)) <= 21844
      error_message = "User-data dos paineis excede o limite EC2 de 16 KiB comprimidos."
    }
  }
  depends_on = [aws_route_table_association.public, aws_vpc_security_group_egress_rule.observability, aws_vpc_security_group_ingress_rule.grafana_mysql]
}
resource "aws_eip_association" "observability" {
  instance_id   = aws_instance.observability.id
  allocation_id = aws_eip.observability.id
}
output "grafana_url" { value = "http://${aws_lb.grafana.dns_name}" }
output "neo4j_browser_url" { value = "http://${aws_eip.observability.public_ip}:7474/browser/" }
output "neo4j_bolt_url" { value = "bolt://${aws_eip.observability.public_ip}:7687" }
output "target_group_arn" { value = aws_lb_target_group.grafana.arn }
output "observability_instance_id" { value = aws_instance.observability.id }
