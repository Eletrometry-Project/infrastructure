output "bucket_name" {
  value = aws_s3_bucket.rules.id
}

output "function_name" {
  value = aws_lambda_function.compiler.function_name
}

output "log_group" {
  value = aws_cloudwatch_log_group.lambda.name
}

output "failure_queue_url" {
  value = aws_sqs_queue.failures.url
}

# Apenas exemplo para administrador autorizado; este modulo nao altera IAM.
output "role_policy_example" {
  value = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = ["${aws_s3_bucket.rules.arn}/entrada/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${aws_s3_bucket.rules.arn}/saida/*", "${aws_s3_bucket.rules.arn}/erros/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/${var.name}:*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.failures.arn]
      }
    ]
  })
}
