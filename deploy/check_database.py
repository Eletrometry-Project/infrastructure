#!/usr/bin/env python3
"""Consulta o banco com a mesma credencial do consumidor; nao imprime segredos."""
import argparse
import json
from pathlib import Path
import sys
import time

import mysql.connector


def wait_for_event(db, event_id, timeout):
    deadline = time.monotonic() + timeout
    while True:
        cursor = db.cursor()
        try:
            cursor.execute(
                'SELECT COUNT(*), MAX(fase_a), MAX(fase_b), MAX(fase_c) '
                'FROM leituras WHERE event_id = %s', (event_id,)
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row[0]:
            if row[0] != 1 or tuple(float(x) if x is not None else None for x in row[1:]) != (100.0, 101.0, 102.0):
                print('FALHA: evento encontrado, mas quantidade ou valores diferem do teste.')
                return 1
            print(f'OK: {event_id} encontrado no MySQL, 1 linha, fases A=100 B=101 C=102.')
            return 0
        if time.monotonic() >= deadline:
            print('FALHA: evento nao chegou ao MySQL no prazo. Confira logs do consumidor e a role da regra IoT.')
            return 1
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event-id')
    parser.add_argument('--wait', type=int, default=60)
    args = parser.parse_args()
    config = json.loads(Path('/etc/eletrometry/runtime.json').read_text())
    db = mysql.connector.connect(
        host=config['db_host'], user=config['db_user'],
        password=Path('/etc/eletrometry/mysql-password').read_text(),
        database='eletrometry', autocommit=True, connection_timeout=10,
        ssl_ca=config['ca_file'], ssl_verify_cert=True, ssl_verify_identity=True,
    )
    try:
        if args.event_id:
            return wait_for_event(db, args.event_id, args.wait)
        cursor = db.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM leituras')
            print(f'MySQL acessivel; total de leituras: {cursor.fetchone()[0]}.')
        finally:
            cursor.close()
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'Falha ao consultar MySQL ({type(exc).__name__}); confira o bootstrap.', file=sys.stderr)
        sys.exit(1)
