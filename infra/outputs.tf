output "queue_url" { value = aws_sqs_queue.telemetry.url }
output "dlq_url" { value = aws_sqs_queue.dlq.url }
output "db_endpoint" { value = aws_db_instance.mysql.address }
output "consumer_instance_id" { value = aws_instance.consumer.id }
output "consumer_public_ip" { value = aws_instance.consumer.public_ip }
output "runtime_config" { value = jsondecode(local.runtime_config) }
output "lab" {
  description = "Informacoes usadas por lab.ps1; nenhum segredo e exibido."
  value = {
    aws_profile          = var.aws_profile
    aws_region           = var.aws_region
    account_id           = var.aws_account_id
    consumer_public_ip   = aws_instance.consumer.public_ip
    consumer_instance_id = aws_instance.consumer.id
    generated_key        = local.generate_ssh_key
    iot_sqs_role_arn     = local.iot_sqs_role_arn
  }
}
output "next_step" { value = "A EC2 ainda pode estar instalando. Na pasta do projeto: .\\lab.ps1 status; depois .\\lab.ps1 testar" }
output "future_load_balancer" {
  value = "ALB previsto para a etapa 2 (site/Grafana); nao criado nem cobrado por este pacote."
}
