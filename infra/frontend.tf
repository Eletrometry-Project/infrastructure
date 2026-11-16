variable "portal_publico" {
  description = "Permitir acesso HTTPS ao portal a partir de qualquer IPv4 durante a demonstracao."
  type        = bool
  default     = true
}

# Instalação da imagem após o apply: lab.ps1 envia o pacote por SSM.
resource "aws_security_group" "frontend" {
  name_prefix = "${local.name}-frontend-"
  description = "Portal Eletrometry em Docker"
  vpc_id      = local.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "frontend_https" {
  for_each          = var.portal_publico ? toset(["0.0.0.0/0"]) : local.ui_cidrs
  security_group_id = aws_security_group.frontend.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_egress_rule" "frontend" {
  security_group_id = aws_security_group.frontend.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "frontend_grafana" {
  security_group_id            = aws_security_group.observability.id
  referenced_security_group_id = aws_security_group.frontend.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
  description                  = "Portal para o Grafana na rede privada"
}

resource "aws_instance" "frontend" {
  ami                         = local.consumer_ami_id
  instance_type               = "t3.micro"
  subnet_id                   = local.consumer_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.frontend.id]
  iam_instance_profile        = local.instance_profile_name
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 16
    encrypted             = true
    delete_on_termination = true
  }
  lifecycle {
    ignore_changes = [ami]
  }
  tags       = { Name = "${local.name}-frontend", Stage = "3-portal" }
  depends_on = [aws_route_table_association.public, aws_vpc_security_group_egress_rule.frontend]
}

resource "aws_eip" "frontend" {
  domain = "vpc"
  tags   = { Name = "${local.name}-frontend" }
}

resource "aws_eip_association" "frontend" {
  instance_id   = aws_instance.frontend.id
  allocation_id = aws_eip.frontend.id
}

output "portal_url" {
  value = "https://${aws_eip.frontend.public_ip}"
}
