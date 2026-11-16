variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,39}$", var.name))
    error_message = "Use 2 a 40 caracteres minusculos, numeros e hifens."
  }
}

variable "account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Informe o ID da conta AWS com 12 digitos."
  }
}

variable "region" {
  type = string
}

variable "lambda_role_arn" {
  type = string
  validation {
    condition     = can(regex("^arn:aws:iam::${var.account_id}:role/.+$", var.lambda_role_arn))
    error_message = "A role existente deve pertencer a conta de destino."
  }
}

variable "source_dir" {
  description = "Diretorio do pacote Python transpiler, incluindo cabines.json."
  type        = string
}

variable "package_path" {
  description = "Caminho local do ZIP; manter entre plan e apply."
  type        = string
}
