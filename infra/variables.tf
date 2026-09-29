variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_account_id" {
  description = "ID da conta de destino; protege contra uso de credenciais de outra conta."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Informe os 12 digitos da conta AWS."
  }
}

variable "environment" {
  type    = string
  default = "lab"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,15}$", var.environment))
    error_message = "Use 2 a 16 caracteres minusculos, numeros e hifens."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
  validation {
    condition     = can(cidrsubnet(var.vpc_cidr, 8, 11))
    error_message = "Informe CIDR IPv4 com espaco para as quatro subnets."
  }
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
  validation {
    condition     = length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2
    error_message = "Informe duas zonas diferentes da regiao escolhida."
  }
}

variable "admin_ipv4_cidr" {
  type = string
  validation {
    condition     = can(cidrnetmask(var.admin_ipv4_cidr)) && can(regex("/32$", var.admin_ipv4_cidr)) && var.admin_ipv4_cidr != "0.0.0.0/32"
    error_message = "Use seu IPv4 publico com /32; nunca 0.0.0.0/0."
  }
}

variable "consumer_ami_id" {
  description = "null pesquisa Ubuntu 24.04 LTS x86_64 oficial; informar ID fixa a AMI."
  type        = string
  default     = null
  validation {
    condition     = var.consumer_ami_id == null || can(regex("^ami-[0-9a-f]+$", var.consumer_ami_id))
    error_message = "Use null ou um ID real de AMI."
  }
}

variable "consumer_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "consumer_root_volume_size" {
  type    = number
  default = 16
}

variable "consumer_root_volume_type" {
  type    = string
  default = "gp3"
}

variable "consumer_root_encrypted" {
  type    = bool
  default = true
}

variable "instance_profile_name" {
  description = "Obrigatorio somente quando create_consumer_iam=false."
  type        = string
  default     = null
  validation {
    condition     = var.create_consumer_iam || try(length(trimspace(var.instance_profile_name)) > 0, false)
    error_message = "Informe o instance profile permitido pelo laboratorio."
  }
}

variable "iot_sqs_role_arn" {
  description = "Obrigatorio somente quando create_iot_iam=false; role deve confiar em iot.amazonaws.com."
  type        = string
  default     = null
  validation {
    condition     = var.create_iot_iam || can(regex("^arn:aws:iam::[0-9]{12}:role/.+$", var.iot_sqs_role_arn))
    error_message = "Informe o ARN da role IoT permitida pelo laboratorio."
  }
}

variable "queue_name" {
  type    = string
  default = "eletrometry-demo"
}

variable "iot_rule_name" {
  type    = string
  default = "eletrometry_demo"
  validation {
    condition     = can(regex("^[A-Za-z0-9_]+$", var.iot_rule_name))
    error_message = "Nome da regra IoT aceita letras, numeros e underscore."
  }
}

variable "iot_sql_version" {
  type    = string
  default = "2016-03-23"
}

variable "db_identifier" {
  type    = string
  default = "eletrometry-lab"
}

variable "db_engine_version" {
  description = "null pesquisa versao padrao disponivel da familia mysql8.4; informar versao fixa a escolha."
  type        = string
  default     = null
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_storage_type" {
  type    = string
  default = "gp2"
}

variable "db_storage_encrypted" {
  type    = bool
  default = true
}

variable "db_initial_database_name" {
  type    = string
  default = "eletrometry"
}

variable "db_master_username" {
  type    = string
  default = "eletrometry_admin"
}

variable "db_backup_retention_days" {
  type    = number
  default = 1
  validation {
    condition     = var.db_backup_retention_days >= 0 && var.db_backup_retention_days <= 35
    error_message = "Retencao de backup deve estar entre 0 e 35 dias."
  }
}

variable "db_max_allocated_storage" {
  type    = number
  default = 0
}

variable "db_password_mode" {
  description = "write_only recebe senha efemera; managed usa Secrets Manager do RDS se permitido."
  type        = string
  default     = "write_only"
  validation {
    condition     = contains(["write_only", "managed"], var.db_password_mode)
    error_message = "O banco novo exige write_only ou managed."
  }
}

variable "db_master_password" {
  description = "Apenas entrada efemera para password_wo. Nao grave em tfvars; use entrada segura no terminal."
  type        = string
  sensitive   = true
  ephemeral   = true
  default     = null
  validation {
    condition     = var.db_password_mode != "write_only" || try(length(var.db_master_password) >= 16, false)
    error_message = "write_only exige senha de pelo menos 16 caracteres via TF_VAR_db_master_password."
  }
}

variable "db_password_version" {
  description = "Incrementar somente quando quiser aplicar nova senha write_only."
  type        = number
  default     = 1
}

variable "db_auto_minor_version_upgrade" {
  type    = bool
  default = true
}
variable "aws_profile" {
  description = "Perfil AWS CLI local; null usa credenciais do ambiente."
  type        = string
  default     = "eletrometry-lab"
}

variable "create_consumer_iam" {
  description = "Criar role, policy e instance profile EC2; false referencia perfil permitido pelo Lab."
  type        = bool
  default     = true
}

variable "create_iot_iam" {
  description = "Criar role e policy IoT para SQS; false referencia role permitida pelo Lab."
  type        = bool
  default     = true
}

variable "existing_key_pair_name" {
  description = "Opcional: key pair ja autorizado pelo Lab; null registra chave publica nova."
  type        = string
  default     = null
}

variable "ssh_public_key_path" {
  description = "Arquivo .pub local. Chave privada nunca passa pelo Terraform."
  type        = string
  default     = "~/.ssh/eletrometry.pub"
  validation {
    condition     = var.existing_key_pair_name != null || try(fileexists(pathexpand(var.ssh_public_key_path)), false)
    error_message = "Gere a chave SSH local e indique seu arquivo .pub, ou informe existing_key_pair_name."
  }
}

