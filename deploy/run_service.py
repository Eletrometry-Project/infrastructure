#!/usr/bin/env python3
"""Adaptador systemd para o consumidor original fixado em um commit revisado."""
import json
import logging
import os
import sys
from pathlib import Path

import boto3
import mysql.connector
from botocore.config import Config


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = json.loads(Path("/etc/eletrometry/runtime.json").read_text(encoding="utf-8-sig"))
    sys.path.insert(0, config["repo_path"])
    from consumidor_sqs_mysql import consume

    password_path = Path(os.environ["CREDENTIALS_DIRECTORY"]) / "mysql-password"
    password = password_path.read_text()
    db = None
    try:
        db = mysql.connector.connect(
            host=config["db_host"], port=3306, user=config["db_user"],
            password=password, database="eletrometry", autocommit=False,
            connection_timeout=10, ssl_ca=config["ca_file"],
            ssl_verify_cert=True, ssl_verify_identity=True,
        )
        password = None
        cursor = db.cursor()
        try:
            cursor.execute("SET time_zone = '+00:00'")
        finally:
            cursor.close()
        sqs = boto3.Session(region_name=config["aws_region"]).client(
            "sqs", config=Config(connect_timeout=5, read_timeout=30,
                                 retries={"mode": "standard", "total_max_attempts": 3}),
        )
        return consume(sqs, db, config["queue_url"], 0)
    except Exception as exc:
        # Nao imprimir configuracao, senha ou argumentos de conexao.
        logging.error("Consumidor interrompido (%s); systemd tentara reiniciar.", type(exc).__name__)
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
