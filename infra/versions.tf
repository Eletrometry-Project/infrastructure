terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 6.0" }
    tls    = { source = "hashicorp/tls", version = "~> 4.0" }
    local  = { source = "hashicorp/local", version = "~> 2.0" }
    random = { source = "hashicorp/random", version = "~> 3.0" }
    http   = { source = "hashicorp/http", version = "~> 3.0" }
  }
}
provider "aws" {
  region              = var.aws_region
  profile             = var.aws_profile
  allowed_account_ids = [var.aws_account_id]
  default_tags {
    tags = { Project = "Eletrometry", Environment = var.environment, ManagedBy = "Terraform", Stage = "1-operacional" }
  }
}
