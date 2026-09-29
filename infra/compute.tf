locals {
  runtime_config = jsonencode({
    aws_region = var.aws_region
    queue_url  = aws_sqs_queue.telemetry.url
    db_host    = aws_db_instance.mysql.address
    db_user    = "eletrometry_consumer"
    ca_file    = "/opt/eletrometry/global-bundle.pem"
    repo_path  = "/opt/eletrometry/repo"
  })
  # Nenhum segredo entra no cloud-init. A senha da aplicacao e instalada separadamente.
  bootstrap_files = {
    "install.sh"                   = { path = "/opt/eletrometry-package/deploy/install.sh", mode = "0750", content = file("${path.module}/../deploy/install.sh") }
    "run_service.py"               = { path = "/opt/eletrometry-package/deploy/run_service.py", mode = "0644", content = file("${path.module}/../deploy/run_service.py") }
    "setup_database.py"            = { path = "/opt/eletrometry-package/deploy/setup_database.py", mode = "0640", content = file("${path.module}/../deploy/setup_database.py") }
    "requirements.lock.txt"        = { path = "/opt/eletrometry-package/deploy/requirements.lock.txt", mode = "0644", content = file("${path.module}/../deploy/requirements.lock.txt") }
    "eletrometry-consumer.service" = { path = "/opt/eletrometry-package/deploy/eletrometry-consumer.service", mode = "0644", content = file("${path.module}/../deploy/eletrometry-consumer.service") }
    "001-schema.sql"               = { path = "/opt/eletrometry-package/sql/001-schema.sql", mode = "0644", content = file("${path.module}/../sql/001-schema.sql") }
    "runtime.json"                 = { path = "/opt/eletrometry-package/runtime.json", mode = "0644", content = local.runtime_config }
  }
  cloud_init = "#cloud-config\n${yamlencode({
    write_files = [for item in local.bootstrap_files : {
      path        = item.path
      permissions = item.mode
      owner       = "root:root"
      encoding    = "b64"
      content     = base64encode(item.content)
    }]
    runcmd = [["bash", "/opt/eletrometry-package/deploy/install.sh", "/opt/eletrometry-package/runtime.json"]]
  })}"
}

resource "aws_instance" "consumer" {
  ami                         = local.consumer_ami_id
  instance_type               = var.consumer_instance_type
  subnet_id                   = local.consumer_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = local.consumer_sg_ids
  key_name                    = local.consumer_key_name
  iam_instance_profile        = local.instance_profile_name
  user_data_base64            = base64gzip(local.cloud_init)
  user_data_replace_on_change = false
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    volume_size           = var.consumer_root_volume_size
    volume_type           = var.consumer_root_volume_type
    encrypted             = var.consumer_root_encrypted
    delete_on_termination = true
  }
  tags       = { Name = "${local.name}-consumer" }
  depends_on = [aws_route_table_association.public, aws_vpc_security_group_egress_rule.consumer, aws_iam_role_policy.consumer]
  lifecycle {
    prevent_destroy = true
    # Cloud-init nao e um mecanismo de atualizacao de software; preservar bootstrap ja executado.
    ignore_changes = [user_data, user_data_base64]
  }
}
