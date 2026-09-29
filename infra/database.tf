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
  manage_master_user_password  = var.db_password_mode == "managed" ? true : null
  password_wo                  = var.db_password_mode == "write_only" ? var.db_master_password : null
  password_wo_version          = var.db_password_mode == "write_only" ? var.db_password_version : null
  multi_az                     = false
  publicly_accessible          = false
  db_subnet_group_name         = local.db_subnet_group_name
  vpc_security_group_ids       = local.db_sg_ids
  port                         = 3306
  backup_retention_period      = var.db_backup_retention_days
  auto_minor_version_upgrade   = var.db_auto_minor_version_upgrade
  apply_immediately            = false
  deletion_protection          = true
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${var.db_identifier}-final"
  copy_tags_to_snapshot        = true
  performance_insights_enabled = false
  monitoring_interval          = 0
  lifecycle {
    prevent_destroy = true
  }
}
