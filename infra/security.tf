resource "aws_security_group" "consumer" {
  name_prefix = "${local.name}-consumer-"
  description = "SSH administrativo; consumidor sem entrada HTTP"
  vpc_id      = local.vpc_id
}

resource "aws_security_group" "database" {
  name_prefix = "${local.name}-mysql-"
  description = "MySQL somente a partir do consumidor"
  vpc_id      = local.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.consumer.id
  description       = "IP administrativo individual"
  cidr_ipv4         = local.admin_ipv4_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "mysql" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.consumer.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "consumer" {
  security_group_id = aws_security_group.consumer.id
  description       = "SQS HTTPS, repositorios de pacotes e RDS; restringir na evolucao da rede"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
