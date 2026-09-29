resource "aws_sqs_queue" "dlq" {
  name                      = "${var.queue_name}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_sqs_queue" "telemetry" {
  name                       = var.queue_name
  fifo_queue                 = false
  receive_wait_time_seconds  = 10
  visibility_timeout_seconds = 120
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.url
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.telemetry.arn]
  })
}

resource "aws_iot_topic_rule" "telemetry" {
  name        = var.iot_rule_name
  description = "Eletrometry: telemetria v1 para SQS"
  enabled     = true
  sql         = "SELECT * FROM 'eletrometry/demo/+/+'"
  sql_version = var.iot_sql_version
  sqs {
    queue_url  = aws_sqs_queue.telemetry.url
    role_arn   = local.iot_sqs_role_arn
    use_base64 = false
  }
  depends_on = [aws_iam_role_policy.iot_sqs]
  lifecycle {
    prevent_destroy = true
  }
}
