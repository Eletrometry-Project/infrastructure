variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_account_id" {
  description = "ID da conta de destino; protege contra uso de credenciais de outra conta."
  type        = string
  default     = "131374841349"
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
  description = "null detecta o IPv4 publico automaticamente; use um /32 se precisar sobrescrever."
  type        = string
  default     = null
  validation {
    condition     = var.admin_ipv4_cidr == null || (can(cidrnetmask(var.admin_ipv4_cidr)) && can(regex("/32$", var.admin_ipv4_cidr)) && var.admin_ipv4_cidr != "0.0.0.0/32")
    error_message = "Use null para deteccao automatica ou seu IPv4 publico/32."
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
  description = "Instance profile PREEXISTENTE autorizado pelo Lab; nenhum IAM sera criado."
  type        = string
  default     = "LabInstanceProfile"
}

variable "iot_sqs_role_arn" {
  description = "Role PREEXISTENTE assumivel por IoT com sqs:SendMessage. null tenta LabRole, sem garantir que o Lab a autorize para IoT."
  type        = string
  default     = null
  validation {
    condition     = var.iot_sqs_role_arn == null || can(regex("^arn:aws:iam::[0-9]{12}:role/.+$", var.iot_sqs_role_arn))
    error_message = "Informe null ou ARN de uma role existente autorizada para IoT."
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
  description = "null pesquisa versao disponivel mais recente da familia mysql8.4; informar versao fixa a escolha."
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
  default = 0
  validation {
    condition     = var.db_backup_retention_days >= 0 && var.db_backup_retention_days <= 35
    error_message = "Retencao de backup deve estar entre 0 e 35 dias."
  }
}

variable "db_max_allocated_storage" {
  type    = number
  default = 0
}




variable "db_auto_minor_version_upgrade" {
  type    = bool
  default = true
}
variable "aws_profile" {
  description = "Perfil AWS CLI local; null usa credenciais do ambiente."
  type        = string
  default     = "default"
}



variable "existing_key_pair_name" {
  description = "Opcional: key pair ja autorizado pelo Lab; null gera e registra uma chave automaticamente."
  type        = string
  default     = null
}



variable "ssh_public_key_path" {
  description = "Opcional: reutilizar o .pub que voce ja criou. null gera uma chave nova automaticamente."
  type        = string
  default     = null
  validation {
    condition     = var.ssh_public_key_path == null || try(fileexists(pathexpand(var.ssh_public_key_path)), false)
    error_message = "O arquivo .pub informado nao existe. Use null para gerar a chave automaticamente."
  }
}
