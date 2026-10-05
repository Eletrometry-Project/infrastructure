# Sem chamadas AWS: testa o plano com valores simulados.
mock_provider "aws" {
  override_during = plan
  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:us-east-1:111111111111/mock-queue"
      url = "https://sqs.us-east-1.amazonaws.com/111111111111/mock-queue"
    }
  }
}
mock_provider "tls" { override_during = plan }
mock_provider "local" { override_during = plan }
mock_provider "random" {
  override_during = plan
  mock_resource "random_password" { defaults = { result = "SyntheticPasswordForTests41" } }
}
mock_provider "http" { override_during = plan }
variables {
  aws_account_id    = "111111111111"
  admin_ipv4_cidr   = "192.0.2.10/32"
  consumer_ami_id   = "ami-0123456789abcdef0"
  db_engine_version = "8.4.7"
}
run "lab_defaults" {
  command = plan
  assert {
    condition     = aws_instance.consumer.iam_instance_profile == "LabInstanceProfile" && one(aws_iot_topic_rule.telemetry.sqs).role_arn == "arn:aws:iam::111111111111:role/LabRole"
    error_message = "Referenciar os recursos existentes do Lab."
  }
  assert {
    condition     = length(tls_private_key.consumer) == 1 && length(local_sensitive_file.ssh_key) == 1
    error_message = "Gerar e salvar a chave automaticamente."
  }
  assert {
    condition     = !aws_db_instance.mysql.publicly_accessible && !aws_db_instance.mysql.multi_az && !aws_db_instance.mysql.deletion_protection && aws_db_instance.mysql.skip_final_snapshot
    error_message = "Banco privado, Single-AZ e descartavel para o Lab."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.ssh.cidr_ipv4 == "192.0.2.10/32" && aws_vpc_security_group_ingress_rule.mysql.referenced_security_group_id == aws_security_group.consumer.id
    error_message = "Preservar acesso SSH individual e MySQL pela EC2."
  }
  assert {
    condition     = aws_instance.consumer.user_data_replace_on_change && aws_instance.consumer.metadata_options[0].http_tokens == "required"
    error_message = "Mudancas no bootstrap exigem recriar EC2; usar credenciais do instance profile via IMDSv2."
  }
}
run "message_contract" {
  command = plan
  assert {
    condition     = !aws_sqs_queue.telemetry.fifo_queue && aws_sqs_queue.telemetry.visibility_timeout_seconds == 120 && aws_sqs_queue.telemetry.receive_wait_time_seconds == 10
    error_message = "Preservar fila Standard e parametros do consumidor."
  }
  assert {
    condition     = aws_iot_topic_rule.telemetry.sql == "SELECT * FROM 'eletrometry/demo/+/+'" && !one(aws_iot_topic_rule.telemetry.sqs).use_base64
    error_message = "Preservar topicos e JSON sem Base64 na acao SQS."
  }
  assert {
    condition     = jsondecode(aws_sqs_queue.telemetry.redrive_policy).maxReceiveCount == 5
    error_message = "Mensagens invalidas devem ir para DLQ apos tentativas."
  }
}
run "existing_key_and_authorized_iot_role" {
  command = plan
  variables {
    existing_key_pair_name = "existing-lab-key"
    iot_sqs_role_arn       = "arn:aws:iam::111111111111:role/ExistingIotRole"
  }
  assert {
    condition     = length(tls_private_key.consumer) == 0 && aws_instance.consumer.key_name == "existing-lab-key" && one(aws_iot_topic_rule.telemetry.sqs).role_arn == var.iot_sqs_role_arn
    error_message = "Respeitar os recursos existentes informados."
  }
}
run "reject_open_ssh" {
  command = plan
  variables { admin_ipv4_cidr = "0.0.0.0/0" }
  expect_failures = [var.admin_ipv4_cidr]
}
