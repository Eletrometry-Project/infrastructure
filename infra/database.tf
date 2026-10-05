resource "aws_db_instance" "mysql" {
  identifier                   = var.db_identifier
  engine                       = "mysql"
  engine_version               = local.db_engine_version
  instance_class               = var.db_instance_class
  allocated_storage            = var.db_allocated_storage
  max_allocated_storage        = var.db_max_allocated_storage
  storage_type                 = var.db_storage_type
  storage_encrypted            = var.db_storage_encrypted
  db_name                      = var.db_initial_database_name
  username                     = var.db_master_username
  password                     = random_password.admin.result
  multi_az                     = false
  publicly_accessible          = false
  db_subnet_group_name         = local.db_subnet_group_name
  vpc_security_group_ids       = local.db_sg_ids
  port                         = 3306
  backup_retention_period      = var.db_backup_retention_days
  auto_minor_version_upgrade   = var.db_auto_minor_version_upgrade
  apply_immediately            = true
  deletion_protection          = false
  skip_final_snapshot          = true
  copy_tags_to_snapshot        = true
  performance_insights_enabled = false
  monitoring_interval          = 0
}

# Senhas geradas uma vez e mantidas no state local. Nao publicar o state.
resource "random_password" "admin" {
  length  = 24
  special = false
}
resource "random_password" "consumer" {
  length  = 24
  special = false
}
