# AWS inteiramente simulada; archive real para testar o pacote.
mock_provider "aws" {
  mock_resource "aws_s3_bucket" {
    defaults = {
      id  = "elt-test-bucket"
      arn = "arn:aws:s3:::elt-test-bucket"
    }
  }
  mock_resource "aws_lambda_function" {
    defaults = {
      arn = "arn:aws:lambda:us-east-1:123456789012:function:elt-test"
    }
  }
  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:us-east-1:123456789012:elt-test-failures"
      url = "https://sqs.us-east-1.amazonaws.com/123456789012/elt-test-failures"
    }
  }
}

variables {
  name            = "elt-test"
  account_id      = "123456789012"
  region          = "us-east-1"
  lambda_role_arn = "arn:aws:iam::123456789012:role/LabRole"
  source_dir      = "../../../transpiler"
  package_path    = "./elt-lambda-test.zip"
}

run "deploy_contract" {
  command = apply

  assert {
    condition     = aws_s3_bucket_versioning.rules.versioning_configuration[0].status == "Enabled"
    error_message = "A Lambda exige VersionId."
  }
  assert {
    condition     = aws_s3_bucket.rules.force_destroy == false && aws_s3_bucket_public_access_block.rules.block_public_policy
    error_message = "O bucket deve permanecer privado e nao ser esvaziado pelo destroy."
  }
  assert {
    condition     = one(aws_s3_bucket_notification.rules.lambda_function).filter_prefix == "entrada/" && one(aws_s3_bucket_notification.rules.lambda_function).filter_suffix == ".elt"
    error_message = "Saidas/erros nao podem disparar novas compilacoes."
  }
  assert {
    condition     = aws_lambda_permission.s3.source_account == var.account_id && aws_lambda_permission.s3.source_arn == aws_s3_bucket.rules.arn
    error_message = "Invocacao deve ficar limitada ao bucket e conta."
  }
  assert {
    condition     = aws_lambda_function.compiler.source_code_hash == data.archive_file.lambda.output_base64sha256 && length(data.archive_file.lambda.output_base64sha256) == 44
    error_message = "Mudancas no codigo precisam atualizar o ZIP da Lambda."
  }
  assert {
    condition     = aws_lambda_function.compiler.handler == "transpiler.lambda_handler.handler" && aws_lambda_function.compiler.runtime == "python3.12"
    error_message = "Entrypoint deve corresponder ao pacote."
  }
  assert {
    condition     = aws_lambda_function_event_invoke_config.compiler.destination_config[0].on_failure[0].destination == aws_sqs_queue.failures.arn
    error_message = "Falhas operacionais devem ter destino SQS."
  }
}

run "reject_other_account_role" {
  command = plan
  variables {
    lambda_role_arn = "arn:aws:iam::999999999999:role/LabRole"
  }
  expect_failures = [var.lambda_role_arn]
}
