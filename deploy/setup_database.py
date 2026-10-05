#!/usr/bin/env python3
"""Bootstrap automatico do Lab: schema, usuario e senha local do consumidor."""
import json
import os
from pathlib import Path
import tempfile
import time

import mysql.connector

CONFIG = Path('/etc/eletrometry/runtime.json')
SECRETS = Path('/opt/eletrometry-package/bootstrap-secrets.json')
PASSWORD = Path('/etc/eletrometry/mysql-password')


def write_password(path, value):
    fd, temporary_path = tempfile.mkstemp(prefix='.mysql-password-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(value)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def connect_admin(config, secrets, attempts=60):
    for attempt in range(attempts):
        try:
            return mysql.connector.connect(
                host=config['db_host'], port=3306,
                user=secrets['admin_user'], password=secrets['admin_password'],
                ssl_ca=config['ca_file'], ssl_verify_cert=True, ssl_verify_identity=True,
                connection_timeout=5, autocommit=True,
            )
        except mysql.connector.Error as exc:
            if exc.errno not in (2003, 2005, 2006, 2013, 1040) or attempt == attempts - 1:
                raise
            print('Aguardando conexao com o RDS...', flush=True)
            time.sleep(5)


def configure_database(db, app_password, schema):
    cursor = db.cursor()
    try:
        for statement in schema.split(';'):
            if statement.strip():
                cursor.execute(statement)
        cursor.execute("CREATE USER IF NOT EXISTS 'eletrometry_consumer'@'%' IDENTIFIED BY %s REQUIRE SSL", (app_password,))
        cursor.execute("ALTER USER 'eletrometry_consumer'@'%' IDENTIFIED BY %s REQUIRE SSL", (app_password,))
        cursor.execute("GRANT SELECT, INSERT ON eletrometry.leituras TO 'eletrometry_consumer'@'%'")
        cursor.execute("GRANT UPDATE (event_id) ON eletrometry.leituras TO 'eletrometry_consumer'@'%'")
    finally:
        cursor.close()


def main():
    if os.geteuid() != 0:
        raise SystemExit('Execute com sudo na EC2.')
    # Permite repetir o instalador depois de um bootstrap bem-sucedido.
    if not SECRETS.exists() and PASSWORD.exists():
        print('Credencial ja instalada; bootstrap do banco ja concluido.')
        return
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    secrets = json.loads(SECRETS.read_text())
    db = None
    try:
        db = connect_admin(config, secrets)
        configure_database(db, secrets['app_password'], Path('/opt/eletrometry/001-schema.sql').read_text())
        write_password(PASSWORD, secrets['app_password'])
        SECRETS.unlink()
    except mysql.connector.Error as exc:
        raise SystemExit(f'Falha ao preparar MySQL (codigo {exc.errno}); consumidor nao iniciado.') from None
    finally:
        if db is not None:
            db.close()
    print('Banco, tabela e usuario prontos. Senha local instalada.')


if __name__ == '__main__':
    main()
