CREATE DATABASE IF NOT EXISTS eletrometry
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE eletrometry;
CREATE TABLE IF NOT EXISTS leituras (
  event_id VARCHAR(160) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  run_id VARCHAR(96) NOT NULL,
  cabine_id VARCHAR(32) NOT NULL,
  tipo ENUM('corrente', 'temperatura') NOT NULL,
  coletado_em DATETIME(3) NOT NULL,
  recebido_em TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  sequencia BIGINT UNSIGNED NOT NULL,
  fase_a DECIMAL(9,2) NULL,
  fase_b DECIMAL(9,2) NULL,
  fase_c DECIMAL(9,2) NULL,
  qualidade_a VARCHAR(20) NOT NULL,
  qualidade_b VARCHAR(20) NOT NULL,
  qualidade_c VARCHAR(20) NOT NULL,
  PRIMARY KEY (event_id),
  INDEX idx_grafana (cabine_id, tipo, coletado_em)
) ENGINE=InnoDB;
