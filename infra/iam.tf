locals {
  instance_profile_name = var.create_consumer_iam ? aws_iam_instance_profile.consumer[0].name : var.instance_profile_name
  iot_sqs_role_arn      = var.create_iot_iam ? aws_iam_role.iot_sqs[0].arn : var.iot_sqs_role_arn
  consumer_policy = {
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
      Resource = aws_sqs_queue.telemetry.arn
    }]
  }
  iot_policy = {
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.telemetry.arn }]
  }
}
resource "aws_iam_role" "consumer" {
  count = var.create_consumer_iam ? 1 : 0
  name  = "${local.name}-consumer"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy" "consumer" {
  count  = var.create_consumer_iam ? 1 : 0
  name   = "consume-telemetry"
  role   = aws_iam_role.consumer[0].id
  policy = jsonencode(local.consumer_policy)
}
resource "aws_iam_instance_profile" "consumer" {
  count = var.create_consumer_iam ? 1 : 0
  name  = "${local.name}-consumer"
  role  = aws_iam_role.consumer[0].name
}
resource "aws_iam_role" "iot_sqs" {
  count = var.create_iot_iam ? 1 : 0
  name  = "${local.name}-iot-sqs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "iot.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.aws_account_id }
        ArnEquals    = { "aws:SourceArn" = "arn:aws:iot:${var.aws_region}:${var.aws_account_id}:rule/${var.iot_rule_name}" }
      }
    }]
  })
}
resource "aws_iam_role_policy" "iot_sqs" {
  count  = var.create_iot_iam ? 1 : 0
  name   = "send-telemetry"
  role   = aws_iam_role.iot_sqs[0].id
  policy = jsonencode(local.iot_policy)
}
