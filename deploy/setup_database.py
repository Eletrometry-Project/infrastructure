#!/usr/bin/env python3
"""Migracao idempotente e credencial local. Executar interativamente como root na EC2."""
import getpass
import json
import os
from pathlib import Path
import subprocess
import tempfile

import mysql.connector


def write_password(path, value):
    """Arquivo atomico, root-only; senha nao passa por CLI, Terraform nem variaveis de ambiente."""
    fd, temporary_path = tempfile.mkstemp(prefix=".mysql-password-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(value)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def main():
    if os.geteuid() != 0:
        raise SystemExit("Execute com sudo na EC2.")
    running = subprocess.run(
        ["systemctl", "is-active", "--quiet", "eletrometry-consumer.service"], check=False
    )
    if running.returncode == 0:
        raise SystemExit("Pare o servico antes de trocar credenciais: sudo systemctl stop eletrometry-consumer")
    config = json.loads(Path("/etc/eletrometry/runtime.json").read_text(encoding="utf-8-sig"))
    if config["db_user"] != "eletrometry_consumer":
        raise SystemExit("Este bootstrap prepara apenas o usuario eletrometry_consumer.")
    admin = input("Usuario administrador do RDS: ").strip()
    admin_password = getpass.getpass("Senha do administrador (nao sera salva): ")
    app_password = getpass.getpass("Nova senha de eletrometry_consumer (minimo 16 caracteres): ")
    if len(app_password) < 16 or app_password != getpass.getpass("Confirme a nova senha: "):
        raise SystemExit("Senha curta ou confirmacao diferente; nenhuma alteracao executada.")
    db = None
    try:
        db = mysql.connector.connect(
            host=config["db_host"], port=3306, user=admin, password=admin_password,
            ssl_ca=config["ca_file"], ssl_verify_cert=True, ssl_verify_identity=True,
            connection_timeout=10, autocommit=True,
        )
        admin_password = None
        cursor = db.cursor()
        try:
            # DDL fixo, sem interpolacao de identificadores vindos do usuario.
            for statement in Path("/opt/eletrometry/001-schema.sql").read_text().split(";"):
                if statement.strip():
                    cursor.execute(statement)
            cursor.execute("CREATE USER IF NOT EXISTS 'eletrometry_consumer'@'%' IDENTIFIED BY %s REQUIRE SSL", (app_password,))
            cursor.execute("ALTER USER 'eletrometry_consumer'@'%' IDENTIFIED BY %s REQUIRE SSL", (app_password,))
            cursor.execute("GRANT SELECT, INSERT ON eletrometry.leituras TO 'eletrometry_consumer'@'%'")
            # Necessario para ON DUPLICATE KEY UPDATE event_id=event_id do consumidor original.
            cursor.execute("GRANT UPDATE (event_id) ON eletrometry.leituras TO 'eletrometry_consumer'@'%'")
        finally:
            cursor.close()
        write_password(Path("/etc/eletrometry/mysql-password"), app_password)
    except mysql.connector.Error as exc:
        raise SystemExit(f"Falha MySQL (codigo {exc.errno}); servico nao iniciado. Revise a etapa e execute novamente.") from None
    finally:
        if db is not None:
            db.close()
    print("Schema e usuario preparados. Credencial local root-only instalada.")
    print("Revise os privilegios se este usuario ja existia: GRANT nao remove privilegios anteriores.")
    print("Depois de parar o consumidor manual: sudo systemctl start eletrometry-consumer")


if __name__ == "__main__":
    main()
