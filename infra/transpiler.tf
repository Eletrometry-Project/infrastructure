# Integrado ao mesmo state e apply do laboratorio.
variable "transpiler_lambda_role_arn" {
  description = "Role existente com trust lambda.amazonaws.com e acesso S3/logs/SQS; null usa LabRole."
  type        = string
  default     = null
  validation {
    condition     = var.transpiler_lambda_role_arn == null || can(regex("^arn:aws:iam::[0-9]{12}:role/.+$", var.transpiler_lambda_role_arn))
    error_message = "Use null ou o ARN de uma role IAM existente."
  }
}

module "transpiler" {
  source = "./modules/transpiler"

  name            = "eletrometry-${var.environment}-elt"
  account_id      = var.aws_account_id
  region          = var.aws_region
  lambda_role_arn = coalesce(var.transpiler_lambda_role_arn, "arn:aws:iam::${var.aws_account_id}:role/LabRole")
  source_dir      = abspath("${path.module}/../transpiler")
  package_path    = abspath("${path.module}/elt-lambda.zip")
}

output "transpiler" {
  description = "Envio de regras e diagnostico; nao contem credenciais."
  value = {
    bucket_name         = module.transpiler.bucket_name
    input_uri           = "s3://${module.transpiler.bucket_name}/entrada/"
    output_uri          = "s3://${module.transpiler.bucket_name}/saida/"
    errors_uri          = "s3://${module.transpiler.bucket_name}/erros/"
    function_name       = module.transpiler.function_name
    log_group           = module.transpiler.log_group
    failure_queue_url   = module.transpiler.failure_queue_url
    region              = var.aws_region
    profile             = var.aws_profile
    account_id          = var.aws_account_id
    role_policy_example = module.transpiler.role_policy_example
  }
}
