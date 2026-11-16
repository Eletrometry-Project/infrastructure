#!/usr/bin/env python3
"""SQS -> RDS MySQL. Confirma mensagem somente apos COMMIT (inclusive duplicatas)."""
import argparse
import getpass
import json
import logging
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
import mysql.connector
from botocore.config import Config

LOG = logging.getLogger('eletrometry-sqs-mysql')

INSERT = '''INSERT INTO leituras
    (event_id, run_id, cabine_id, tipo, coletado_em, sequencia,
     fase_a, fase_b, fase_c, qualidade_a, qualidade_b, qualidade_c)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE event_id=event_id'''


def row_from_body(body):
    item = json.loads(body)
    if not isinstance(item, dict) or item.get('schema_version') != 1:
        raise ValueError('mensagem nao segue o contrato de telemetria v1')
    for field, limit in (('event_id', 160), ('run_id', 96), ('cabine_id', 32)):
        if not isinstance(item.get(field), str) or not 1 <= len(item[field]) <= limit:
            raise ValueError(f'{field} invalido')
    if not item['event_id'].isascii() or not re.fullmatch(r'cabine-\d+', item['cabine_id']):
        raise ValueError('identidade de evento/cabine invalida')
    kind = item.get('tipo')
    if kind not in ('corrente', 'temperatura'):
        raise ValueError('tipo invalido')
    if not isinstance(item.get('sequence'), int) or not 0 <= item['sequence'] < 2**64:
        raise ValueError('sequencia invalida')
    values, quality = item.get('valores'), item.get('qualidade')
    if not isinstance(values, dict) or not isinstance(quality, dict) or set(values) != {'A', 'B', 'C'} or set(quality) != {'A', 'B', 'C'}:
        raise ValueError('fases incompletas')
    for phase in 'ABC':
        value = values[phase]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or not 0 <= value < 10**7):
            raise ValueError(f'valor invalido para {phase}')
        if quality[phase] not in ('ok', 'sem_leitura', 'fora_faixa'):
            raise ValueError(f'qualidade invalida para {phase}')
        if (value is None) == (quality[phase] == 'ok'):
            raise ValueError(f'valor e qualidade inconsistentes para {phase}')
    dt = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamp sem fuso')
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return (item['event_id'], item['run_id'], item['cabine_id'], kind, dt, item['sequence'],
            *(values[p] for p in 'ABC'), *(quality[p] for p in 'ABC'))


def consume(sqs, db, queue_url, max_batches):
    batches = accepted = invalid = 0
    last_log = 0.0
    ack_failed = False
    while not max_batches or batches < max_batches:
        response = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=10,
            VisibilityTimeout=120, MessageSystemAttributeNames=['SentTimestamp'])
        messages = response.get('Messages', [])
        if not messages:
            if max_batches:
                break
            continue
        batches += 1
        valid = []
        for msg in messages:
            try:
                row = row_from_body(msg['Body'])
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                invalid += 1
                LOG.error('Mensagem SQS %s invalida; preservada na fila: %s',
                          msg.get('MessageId'), exc)
                continue
            valid.append((msg, row))
        if not valid:
            continue
        started = time.monotonic()
        # Grava imediatamente o lote recebido, sem esperar juntar dez mensagens.
        try:
            cursor = db.cursor()
            try:
                cursor.executemany(INSERT, [row for _, row in valid])
                db.commit()
            finally:
                cursor.close()
        except mysql.connector.Error:
            db.rollback()
            LOG.exception('Falha no MySQL; lote inteiro preservado para nova tentativa.')
            return 1
        db_ms = (time.monotonic() - started) * 1000
        committed_at = time.time()
        queue_ages = []
        for msg, _ in valid:
            try:
                queue_ages.append(committed_at - int(msg['Attributes']['SentTimestamp']) / 1000)
            except (KeyError, ValueError, TypeError):
                pass
        # Confirma SOMENTE depois do commit. Reentregas sao idempotentes por event_id.
        entries = [{'Id': str(i), 'ReceiptHandle': msg['ReceiptHandle']}
                   for i, (msg, _) in enumerate(valid)]
        result = sqs.delete_message_batch(QueueUrl=queue_url, Entries=entries)
        confirmed = {item['Id'] for item in result.get('Successful', [])}
        pending = {item['Id'] for item in entries} - confirmed
        accepted += len(confirmed & {item['Id'] for item in entries})
        if pending:
            ack_failed = True
            LOG.warning('MySQL confirmado; %d mensagens sem confirmacao SQS. '
                        'Reentrega sera deduplicada. Codigos: %s', len(pending),
                        [item.get('Code') for item in result.get('Failed', [])])
        now = time.monotonic()
        if now - last_log >= 5 or (max_batches and batches >= max_batches):
            LOG.info('Lotes %d | confirmadas SQS %d | invalidas preservadas %d | '
                     'ultimo lote %d | MySQL+commit %.1f ms | SQS->commit max %s s',
                     batches, accepted, invalid, len(valid), db_ms,
                     ('%.3f' % max(queue_ages)) if queue_ages else 'indisponivel')
            last_log = now
    return 1 if ack_failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue-url', required=True)
    parser.add_argument('--db-host', required=True, help='Endpoint do RDS, sem :3306.')
    parser.add_argument('--db-user', required=True, help='Usuario MySQL; senha solicitada no terminal.')
    parser.add_argument('--ca-file', required=True, help='Caminho do global-bundle.pem do RDS.')
    parser.add_argument('--regiao', default='us-east-1')
    parser.add_argument('--profile', help='Perfil AWS opcional; omita na EC2 com instance profile.')
    parser.add_argument('--lotes', type=int, default=1, help='Lotes de ate dez mensagens; 0 = continuo.')
    args = parser.parse_args()
    if args.lotes < 0 or not Path(args.ca_file).is_file():
        parser.error('--lotes deve ser >= 0 e --ca-file deve existir.')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    password = getpass.getpass('Senha do MySQL: ')
    db = None
    try:
        db = mysql.connector.connect(host=args.db_host, port=3306, user=args.db_user,
                                     password=password, database='eletrometry', autocommit=False,
                                     connection_timeout=10, ssl_ca=args.ca_file,
                                     ssl_verify_cert=True, ssl_verify_identity=True)
        password = None
        cursor = db.cursor()
        cursor.execute("SET time_zone = '+00:00'")
        cursor.close()
        sqs = boto3.Session(region_name=args.regiao, profile_name=args.profile).client(
            'sqs', config=Config(connect_timeout=5, read_timeout=30,
                                 retries={'mode': 'standard', 'total_max_attempts': 3}))
        return consume(sqs, db, args.queue_url, args.lotes)
    except KeyboardInterrupt:
        LOG.info('Interrompido.')
        return 130
    except Exception:
        LOG.exception('Falha na conexao ou no consumo; mensagens nao confirmadas permanecem na fila.')
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == '__main__':
    sys.exit(main())
