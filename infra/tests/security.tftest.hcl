# Todos os acessos AWS destes testes sao simulados. Nao usar provider real aqui.
mock_provider "aws" {
  override_during = plan
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::111111111111:role/mock-created-role" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:us-east-1:111111111111/mock-queue"
      url = "https://sqs.us-east-1.amazonaws.com/111111111111/mock-queue"
    }
  }
}

variables {
  aws_account_id         = "111111111111"
  admin_ipv4_cidr        = "192.0.2.10/32"
  consumer_ami_id        = "ami-0123456789abcdef0"
  existing_key_pair_name = "mock-key"
  queue_name             = "eletrometry-test"
  iot_rule_name          = "eletrometry_test"
  db_identifier          = "eletrometry-test"
  db_engine_version      = "8.0.43"
  db_master_username     = "test_admin"
  db_password_mode       = "managed"
}

run "private_database_and_restricted_access" {
  command = plan
  assert {
    condition     = !aws_db_instance.mysql.publicly_accessible && !aws_db_instance.mysql.multi_az
    error_message = "Banco da etapa 1 deve ser privado e Single-AZ."
  }
  assert {
    condition     = length(aws_subnet.database) == 2 && length(aws_subnet.public) == 2
    error_message = "Rede deve preparar duas AZs, inclusive para o ALB futuro."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.ssh.cidr_ipv4 == "192.0.2.10/32"
    error_message = "SSH nao pode ser liberado para a internet inteira."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.mysql.referenced_security_group_id == aws_security_group.consumer.id && aws_vpc_security_group_ingress_rule.mysql.from_port == 3306
    error_message = "MySQL deve aceitar apenas o SG do consumidor."
  }
  assert {
    condition     = aws_db_instance.mysql.deletion_protection && !aws_db_instance.mysql.skip_final_snapshot
    error_message = "Protecao de exclusao e snapshot final devem estar habilitados."
  }
  assert {
    condition     = aws_instance.consumer.metadata_options[0].http_tokens == "required"
    error_message = "EC2 deve exigir IMDSv2."
  }
}

run "queue_delivery_and_dlq" {
  command = plan
  assert {
    condition     = !aws_sqs_queue.telemetry.fifo_queue && aws_sqs_queue.telemetry.visibility_timeout_seconds == 120 && aws_sqs_queue.telemetry.receive_wait_time_seconds == 10
    error_message = "Fila deve preservar parametros compatíveis com o consumidor."
  }
  assert {
    condition     = jsondecode(aws_sqs_queue.telemetry.redrive_policy).maxReceiveCount == 5 && aws_sqs_queue.dlq.message_retention_seconds > aws_sqs_queue.telemetry.message_retention_seconds
    error_message = "DLQ precisa de limite de tentativas e retencao maior que a fila principal."
  }
  assert {
    condition     = aws_iot_topic_rule.telemetry.sql == "SELECT * FROM 'eletrometry/demo/+/+'" && !one(aws_iot_topic_rule.telemetry.sqs).use_base64
    error_message = "Regra deve preservar contrato de topicos e JSON sem Base64."
  }
}

run "reject_open_ssh" {
  command = plan
  variables { admin_ipv4_cidr = "0.0.0.0/0" }
  expect_failures = [var.admin_ipv4_cidr]
}

run "reject_new_database_without_password_strategy" {
  command = plan
  variables { db_password_mode = "keep" }
  expect_failures = [var.db_password_mode]
}

run "write_only_password_input" {
  command = plan
  variables {
    db_password_mode   = "write_only"
    db_master_password = "Synthetic-test-only-41!"
  }
  assert {
    condition     = aws_db_instance.mysql.password_wo_version == 1
    error_message = "Senha efemera precisa usar argumento write-only versionado."
  }
}

run "create_scoped_iam" {
  command = plan
  assert {
    condition     = length(aws_iam_role.consumer) == 1 && length(aws_iam_role.iot_sqs) == 1 && length(aws_iam_instance_profile.consumer) == 1
    error_message = "Por padrao, criar as duas roles e o instance profile do projeto."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.iot_sqs[0].policy).Statement[0].Resource == aws_sqs_queue.telemetry.arn && jsondecode(aws_iam_role_policy.consumer[0].policy).Statement[0].Resource == aws_sqs_queue.telemetry.arn
    error_message = "Permissoes das roles devem se limitar a fila de telemetria."
  }
  assert {
    condition     = jsondecode(aws_iam_role.iot_sqs[0].assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == var.aws_account_id
    error_message = "Role IoT deve restringir a conta de origem."
  }
}

run "use_authorized_lab_roles" {
  command = plan
  variables {
    create_consumer_iam   = false
    create_iot_iam        = false
    instance_profile_name = "MockLabInstanceProfile"
    iot_sqs_role_arn      = "arn:aws:iam::111111111111:role/mock-authorized-iot"
  }
  assert {
    condition     = length(aws_iam_role.consumer) == 0 && length(aws_iam_role.iot_sqs) == 0 && length(aws_iam_instance_profile.consumer) == 0
    error_message = "Modo Lab deve referenciar roles sem criar ou editar IAM protegido."
  }
  assert {
    condition     = aws_instance.consumer.iam_instance_profile == "MockLabInstanceProfile" && one(aws_iot_topic_rule.telemetry.sqs).role_arn == var.iot_sqs_role_arn
    error_message = "Usar exatamente o perfil e a role autorizados informados."
  }
}
