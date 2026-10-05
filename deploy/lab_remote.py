#!/usr/bin/env python3
"""Operacoes do Lab executadas via SSM, com credenciais do instance profile."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

import boto3
import mysql.connector
from botocore.config import Config

ROOT = Path('/opt/eletrometry')
STATE = Path('/var/lib/eletrometry-simulator')
CONFIG = Path('/etc/eletrometry/runtime.json')
AWS_CONFIG = Config(connect_timeout=10, read_timeout=20, retries={'total_max_attempts': 2})


def settings():
    return json.loads(CONFIG.read_text(encoding='utf-8-sig'))


def database(config):
    db = mysql.connector.connect(
        host=config['db_host'], user=config['db_user'],
        password=Path('/etc/eletrometry/mysql-password').read_text(),
        database='eletrometry', autocommit=True, connection_timeout=10,
        ssl_ca=config['ca_file'], ssl_verify_cert=True, ssl_verify_identity=True,
    )
    cursor = db.cursor()
    try:
        cursor.execute("SET time_zone = '+00:00'")
    finally:
        cursor.close()
    return db


def query(db, sql, params=()):
    cursor = db.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def session(config):
    return boto3.Session(region_name=config['aws_region'])


def endpoint(config):
    return config.get('iot_endpoint') or session(config).client('iot', config=AWS_CONFIG).describe_endpoint(
        endpointType='iot:Data-ATS')['endpointAddress']


def service(name):
    return subprocess.run(['systemctl', 'is-active', name], capture_output=True, text=True).stdout.strip()


def queues(config):
    sqs = session(config).client('sqs', config=AWS_CONFIG)
    attrs = sqs.get_queue_attributes(QueueUrl=config['queue_url'], AttributeNames=[
        'ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible', 'RedrivePolicy'])['Attributes']
    print('SQS (contagens aproximadas):', json.dumps(attrs), flush=True)
    if attrs.get('RedrivePolicy'):
        arn = json.loads(attrs['RedrivePolicy'])['deadLetterTargetArn']
        parts = arn.split(':')
        url = sqs.get_queue_url(QueueName=parts[-1], QueueOwnerAWSAccountId=parts[-2])['QueueUrl']
        dlq = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['ApproximateNumberOfMessages'])['Attributes']
        print('DLQ:', json.dumps(dlq), flush=True)


def status(config):
    print('Destino real: host=%s banco=eletrometry tabela=leituras' % config['db_host'], flush=True)
    print('Regiao=%s SQS=%s' % (config['aws_region'], config['queue_url']), flush=True)
    consumer = service('eletrometry-consumer')
    simulator = service('eletrometry-simulator')
    print('Consumidor:', consumer, '| Simulador:', simulator, flush=True)
    db = database(config)
    try:
        count, last, age = query(db, 'SELECT COUNT(*), MAX(recebido_em), TIMESTAMPDIFF(SECOND, MAX(recebido_em), UTC_TIMESTAMP()) FROM leituras')[0]
        print('Total:', count, '| Ultima chegada UTC:', last, '| Atraso em segundos:', age, flush=True)
        rows = query(db, 'SELECT run_id, cabine_id, tipo, fase_a, fase_b, fase_c, recebido_em FROM leituras ORDER BY recebido_em DESC LIMIT 6')
        for row in rows:
            print('Leitura:', row, flush=True)
        if not rows:
            print('Tabela vazia: execute testar e simular; servico ativo nao comprova chegada de dados.', flush=True)
    finally:
        db.close()
    try:
        queues(config)
    except Exception as exc:
        print('Consulta SQS indisponivel:', type(exc).__name__, flush=True)
    if simulator != 'active':
        print('Simulador nao esta ativo: nao espere dados novos dele; use iniciar ou confira logs.', flush=True)
    if simulator == 'active' and (not count or age is None or age > 120):
        print('ALERTA: simulador ativo mas sem chegada recente ao banco. Execute testar e logs.', flush=True)
        return 1
    return 0 if consumer == 'active' else 1


def expected_events(folder):
    expected = {}
    for path in folder.glob('telemetria/**/*.jsonl.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                event = json.loads(line)
                if event['event_id'] in expected:
                    raise RuntimeError('Arquivo tem event_id duplicado')
                expected[event['event_id']] = (event['cabine_id'], event['tipo'])
    return expected


def compare_events(expected, actual):
    actual_map = {row[0]: (row[1], row[2]) for row in actual}
    return len(actual_map) == len(actual) and actual_map == expected


def verify_run(config, run_id, expected, wait=90):
    if not expected:
        raise RuntimeError('Sem eventos esperados; nao e possivel aprovar um teste vazio')
    db = database(config)
    deadline = time.monotonic() + wait
    try:
        while True:
            rows = query(db, 'SELECT event_id, cabine_id, tipo FROM leituras WHERE run_id = %s', (run_id,))
            if compare_events(expected, rows):
                groups = Counter((row[1], row[2]) for row in rows)
                report = {'status': 'OK', 'run_id': run_id, 'db_host': config['db_host'],
                          'expected': len(expected), 'actual': len(rows),
                          'groups': [{'cabine': key[0], 'tipo': key[1], 'linhas': n} for key, n in sorted(groups.items())]}
                STATE.mkdir(parents=True, exist_ok=True)
                (STATE / 'latest-check.json').write_text(json.dumps(report, indent=2))
                print(json.dumps(report, indent=2), flush=True)
                return 0
            if time.monotonic() >= deadline:
                missing = sorted(set(expected) - {row[0] for row in rows})
                print('FALHA run_id=%s: %d linhas no MySQL; %d esperadas. Ausentes (ate 5): %s' %
                      (run_id, len(rows), len(expected), missing[:5]), flush=True)
                return 1
            time.sleep(3)
    finally:
        db.close()


def smoke(config):
    if service('eletrometry-consumer') != 'active':
        raise RuntimeError('Consumidor nao esta ativo; consulte logs')
    run_id = 'smoke-' + uuid.uuid4().hex
    event_id = run_id + ':1'
    item = {'schema_version': 1, 'run_id': run_id, 'event_id': event_id, 'cabine_id': 'cabine-001',
            'tipo': 'corrente', 'sequence': 1, 'timestamp': datetime.now(timezone.utc).isoformat(),
            'valores': dict(A=100, B=101, C=102), 'qualidade': dict(A='ok', B='ok', C='ok')}
    session(config).client('iot-data', endpoint_url='https://' + endpoint(config), config=AWS_CONFIG).publish(
        topic='eletrometry/demo/cabine-001/corrente', qos=1, payload=json.dumps(item).encode())
    print('IoT aceitou:', event_id, '| verificando MySQL...', flush=True)
    return subprocess.call([str(ROOT / 'venv/bin/python'), str(ROOT / 'check_database.py'),
                            '--event-id', event_id, '--wait', '90'])


def simulator_args(config, output, continuous=False, duration=120):
    command = [str(ROOT / 'venv/bin/python'), str(ROOT / 'telemetry/simulador_eletrometry.py'), 'simular',
               '--config', str(ROOT / 'telemetry/config_industrial.json'), '--cabines', '3',
               '--modo', 'tempo-real', '--destino', 'iot', '--regiao', config['aws_region'],
               '--endpoint', endpoint(config), '--executor', 'ec2-lab', '--saida', str(output)]
    return command + (['--continuo'] if continuous else ['--duracao', str(duration)])


def simulate(config, duration):
    if service('eletrometry-consumer') != 'active':
        raise RuntimeError('Consumidor nao esta ativo; consulte logs')
    output = STATE / 'checks' / uuid.uuid4().hex
    output.mkdir(parents=True)
    print('Simulando 3 cabines por %ds. Pasta: %s' % (duration, output), flush=True)
    rc = subprocess.call(simulator_args(config, output, duration=duration))
    manifests = list(output.glob('*/manifesto.json'))
    if rc or len(manifests) != 1:
        raise RuntimeError('Simulador falhou; consulte o resumo e as pendencias em ' + str(output))
    folder = manifests[0].parent
    manifest = json.loads(manifests[0].read_text())
    summary = json.loads((folder / 'resumo.json').read_text())
    expected = expected_events(folder)
    count = 3 * (duration + (duration + 29) // 30)
    if len(expected) != count or summary['mensagens_aceitas_iot'] != count or summary['pendencias'] or summary['erro']:
        raise RuntimeError('Geracao/publicacao incompleta: ' + json.dumps(summary))
    return verify_run(config, manifest['run_id'], expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'testar', 'simular', 'live'])
    parser.add_argument('--duration', type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.duration <= 600:
        parser.error('duration deve estar entre 1 e 600 segundos')
    config = settings()
    if args.action == 'status':
        return status(config)
    if args.action == 'testar':
        return smoke(config)
    if args.action == 'simular':
        return simulate(config, args.duration)
    # Executado como eletrometry; nunca abre credenciais MySQL no modo live.
    return subprocess.call(simulator_args(config, STATE / 'live', continuous=True))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('FALHA (%s): %s' % (type(exc).__name__, exc), file=sys.stderr, flush=True)
        sys.exit(1)
