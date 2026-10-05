# O Lab administra estas roles. Este pacote NAO cria nem altera recursos IAM.
# PassRole/associacao do profile e a confianca IoT ainda precisam ser permitidos pelo Lab.
locals {
  instance_profile_name = var.instance_profile_name
  iot_sqs_role_arn      = var.iot_sqs_role_arn != null ? var.iot_sqs_role_arn : "arn:aws:iam::${var.aws_account_id}:role/LabRole"
}
