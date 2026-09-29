# REVISAO 2: criar do zero apos hard reset. Copiar para terraform.tfvars.
aws_account_id = "831154260318" # Conta informada por voce; confirmar ao renovar o Lab.
aws_profile    = "eletrometry-lab"
aws_region     = "us-east-1"

# SUBSTITUIR pelo seu IPv4 publico seguido de /32.
admin_ipv4_cidr = "189.96.237.26/32"

# Gere localmente a chave com ssh-keygen; so o .pub sera registrado na AWS.
ssh_public_key_path = "~/.ssh/eletrometry.pub"

# Terraform cria roles, policies e instance profile quando a conta permite.
create_consumer_iam = true
create_iot_iam      = true

# Se o Lab restringir IAM, usar SOMENTE recursos existentes autorizados:
# create_consumer_iam = false
# instance_profile_name = "LabInstanceProfile" # confirmar nome real
# create_iot_iam = false
# iot_sqs_role_arn = "ARN_REAL_DA_ROLE_QUE_PERMITE_IOT"
# Nao presumir que LabRole permite IoT sem verificar sua confianca.

# AMI e versao MySQL sao pesquisadas no primeiro plan.
# Fixar abaixo os valores de selected_versions e gerar o plano final.
# consumer_ami_id = "ami-ID_REAL"
# db_engine_version = "VERSAO_RESOLVIDA"

db_password_mode = "write_only"
# Nunca escrever a senha neste arquivo. Use scripts/terraform.ps1 no Windows.
