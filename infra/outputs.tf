output "queue_url" {
  value = aws_sqs_queue.telemetry.url
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "db_endpoint" {
  value = aws_db_instance.mysql.address
}

output "consumer_instance_id" {
  value = aws_instance.consumer.id
}

output "consumer_public_ip" {
  value = aws_instance.consumer.public_ip
}

output "runtime_config" {
  description = "Configuracao sem senha para deploy/runtime.json."
  value       = jsondecode(local.runtime_config)
}

output "required_iot_policy" {
  description = "Politica necessaria quando optar por uma role IoT preexistente."
  value = {
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.telemetry.arn }]
  }
}

output "required_consumer_policy" {
  description = "Politica necessaria quando optar por um instance profile preexistente."
  value = {
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
      Resource = aws_sqs_queue.telemetry.arn
    }]
  }
}

output "future_load_balancer" {
  value = {
    status            = "Planejado para etapa 2; nenhum load balancer provisionado nesta etapa."
    proposal          = "Application Load Balancer para site/Grafana; listeners, TLS e targets a validar."
    public_subnet_ids = [for subnet in aws_subnet.public : subnet.id]
  }
}
