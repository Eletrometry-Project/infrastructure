# Os nomes dos recursos preservam a migracao do state da etapa 2 anterior.
resource "aws_security_group" "alb" {
  name_prefix = "eletrometry-grafana-alb-"
  description = "Acesso ao Grafana pelos IPs do grupo"
  vpc_id      = local.vpc_id
}
resource "aws_vpc_security_group_ingress_rule" "web" {
  for_each          = local.ui_cidrs
  security_group_id = aws_security_group.alb.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = each.value
}
resource "aws_vpc_security_group_egress_rule" "grafana" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.observability.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
}
resource "aws_vpc_security_group_ingress_rule" "observability_grafana" {
  security_group_id            = aws_security_group.observability.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
}
resource "aws_lb" "grafana" {
  name_prefix        = "elgraf"
  internal           = false
  load_balancer_type = "application"
  subnets            = [for subnet in aws_subnet.public : subnet.id]
  security_groups    = [aws_security_group.alb.id]
  depends_on         = [aws_route_table_association.public]
}
resource "aws_lb_target_group" "grafana" {
  name_prefix = "elgraf"
  port        = 3000
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = local.vpc_id
  health_check {
    path                = "/api/health"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}
resource "aws_lb_target_group_attachment" "grafana" {
  target_group_arn = aws_lb_target_group.grafana.arn
  target_id        = aws_instance.observability.id
  port             = 3000
}
resource "aws_lb_listener" "grafana" {
  load_balancer_arn = aws_lb.grafana.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.grafana.arn
  }
}
