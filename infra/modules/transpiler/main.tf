# Empacota apenas o runtime; exclui testes, caches, exemplos e arquivos locais.
data "archive_file" "lambda" {
  type             = "zip"
  output_path      = var.package_path
  output_file_mode = "0644"

  dynamic "source" {
    for_each = toset(["__init__.py", "compiler.py", "lambda_handler.py", "cabines.json"])
    content {
      content  = file("${var.source_dir}/${source.value}")
      filename = "transpiler/${source.value}"
    }
  }
}

resource "aws_s3_bucket" "rules" {
  bucket_prefix = "${var.name}-"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "rules" {
  bucket                  = aws_s3_bucket.rules.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "rules" {
  bucket = aws_s3_bucket.rules.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "rules" {
  bucket = aws_s3_bucket.rules.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "rules" {
  bucket = aws_s3_bucket.rules.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "tls" {
  bucket = aws_s3_bucket.rules.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.rules.arn, "${aws_s3_bucket.rules.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 14
}

resource "aws_sqs_queue" "failures" {
  name                      = "${var.name}-failures"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled    = true
}

resource "aws_lambda_function" "compiler" {
  function_name    = var.name
  description      = "ELT para SQL; entrada S3 versionada, sem acesso ao banco."
  role             = var.lambda_role_arn
  runtime          = "python3.12"
  handler          = "transpiler.lambda_handler.handler"
  architectures    = ["x86_64"]
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  memory_size      = 256
  timeout          = 30

  depends_on = [aws_cloudwatch_log_group.lambda]
}

resource "aws_lambda_function_event_invoke_config" "compiler" {
  function_name               = aws_lambda_function.compiler.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 3600
  destination_config {
    on_failure {
      destination = aws_sqs_queue.failures.arn
    }
  }
}

resource "aws_lambda_permission" "s3" {
  statement_id   = "AllowRulesBucket"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.compiler.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.rules.arn
  source_account = var.account_id
}

resource "aws_s3_bucket_notification" "rules" {
  bucket = aws_s3_bucket.rules.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.compiler.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "entrada/"
    filter_suffix       = ".elt"
  }
  depends_on = [
    aws_lambda_permission.s3,
    aws_lambda_function_event_invoke_config.compiler,
    aws_s3_bucket_versioning.rules,
    aws_s3_bucket_public_access_block.rules,
    aws_s3_bucket_ownership_controls.rules,
    aws_s3_bucket_server_side_encryption_configuration.rules,
    aws_s3_bucket_policy.tls,
  ]
}
