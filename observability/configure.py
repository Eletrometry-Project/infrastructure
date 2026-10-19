#!/usr/bin/env python3
"""Provisiona usuarios e configuracoes na EC2 dos paineis. Nunca imprime senhas."""
import json
import os
from pathlib import Path
import shutil
import time
import mysql.connector
import yaml


ROOT=Path('/etc/eletrometry-observability')
STATE=Path('/var/lib/eletrometry-observability')
BOOTSTRAP=ROOT/'bootstrap.json'
RUNTIME=ROOT/'runtime.json'
CA=ROOT/'global-bundle.pem'
SOURCE=Path('/opt/eletrometry-observability')


def write(path, text, mode=0o600, group=None):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write(text)
    if group:
        shutil.chown(temp,user='root',group=group)
    temp.chmod(mode)
    temp.replace(path)


def reader(config):
    ready=ROOT/'reader-ready'
    user='eletrometry_grafana' if ready.exists() else config['admin_user']
    password=config['mysql_password'] if ready.exists() else config['admin_password']
    db=None
    for attempt in range(120):
        try:
            db=mysql.connector.connect(host=config['db_host'],user=user,password=password,
                database=config['db_name'],ssl_ca=str(CA),ssl_verify_cert=True,
                ssl_verify_identity=True,connection_timeout=5,autocommit=True)
            cursor=db.cursor()
            cursor.execute('SELECT event_id FROM leituras LIMIT 1')
            cursor.fetchall()
            break
        except mysql.connector.Error as exc:
            if db:
                db.close(); db=None
            if exc.errno not in (1049,1146,2003,2005,2006,2013) or attempt==119:
                raise
            print('Aguardando RDS/tabela da etapa operacional...',flush=True)
            time.sleep(5)
    try:
        if not ready.exists():
            cursor.execute("CREATE USER IF NOT EXISTS 'eletrometry_grafana'@'%' IDENTIFIED BY %s REQUIRE SSL",(config['mysql_password'],))
            cursor.execute("ALTER USER 'eletrometry_grafana'@'%' IDENTIFIED BY %s REQUIRE SSL",(config['mysql_password'],))
            cursor.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'eletrometry_grafana'@'%'")
            # Banco fixo do contrato operacional; nao interpola nomes arbitrarios no SQL.
            if config['db_name']!='eletrometry':
                raise ValueError('Este pacote espera o banco eletrometry da etapa 1.')
            cursor.execute("GRANT SELECT ON eletrometry.leituras TO 'eletrometry_grafana'@'%'")
            write(ready,'ok\n')
        cursor.close()
    finally:
        if db:
            db.close()


def datasource(config,cert):
    return {'apiVersion':1,'datasources':[{'name':'Eletrometry MySQL','uid':'eletrometry-mysql',
        'type':'mysql','access':'proxy','url':config['db_host']+':3306','user':'eletrometry_grafana',
        'database':config['db_name'],'isDefault':True,'editable':False,
        'jsonData':{'database':config['db_name'],'timezone':'+00:00','maxOpenConns':5,'maxIdleConns':2,
            'maxIdleConnsAuto':False,'connMaxLifetime':300,'timeInterval':'1s',
            'tlsAuthWithCACert':True,'tlsSkipVerify':False,'tlsAuth':False},
        'secureJsonData':{'password':config['mysql_password'],'tlsCACert':cert}}]}


def neo4j_env(config):
    return '\n'.join([
        'NEO4J_AUTH_FILE=/run/secrets/neo4j_auth',
        'NEO4J_server_default__listen__address=0.0.0.0',
        f"NEO4J_server_bolt_advertised__address={config['public_ip']}:7687",
        f"NEO4J_server_http_advertised__address={config['public_ip']}:7474",
        'NEO4J_server_memory_heap_initial__size=512m',
        'NEO4J_server_memory_heap_max__size=768m',
        'NEO4J_server_memory_pagecache_size=512m',
        'NEO4J_db_memory_transaction_total_max=256m',''])


def main():
    if os.geteuid()!=0:
        raise SystemExit('Execute com sudo na EC2 dos paineis.')
    ROOT.mkdir(parents=True,exist_ok=True); ROOT.chmod(0o700)
    STATE.mkdir(parents=True,exist_ok=True)
    config=json.loads((BOOTSTRAP if BOOTSTRAP.exists() else RUNTIME).read_text())
    if config['db_name']!='eletrometry':
        raise SystemExit('O schema operacional usa o banco eletrometry. Ajuste o contrato antes de trocar esse nome.')
    reader(config)
    runtime={k:v for k,v in config.items() if k not in ('admin_user','admin_password')}
    write(RUNTIME,json.dumps(runtime))
    write('/etc/grafana/provisioning/datasources/eletrometry.yaml',yaml.safe_dump(datasource(runtime,CA.read_text()),sort_keys=False),0o640,'grafana')
    dashboard_path=Path('/var/lib/grafana/dashboards/eletrometry.json')
    for name in ['eletrometry.json','visao-geral.json']:
        write(dashboard_path.parent/name,(SOURCE/'dashboards'/name).read_text(),0o644)
    provider={'apiVersion':1,'providers':[{'name':'Eletrometry','orgId':1,'folder':'Eletrometry','type':'file',
        'disableDeletion':False,'allowUiUpdates':False,'updateIntervalSeconds':30,
        'options':{'path':str(dashboard_path.parent)}}]}
    write('/etc/grafana/provisioning/dashboards/eletrometry.yaml',yaml.safe_dump(provider),0o640,'grafana')
    write('/etc/grafana/eletrometry-admin-password',runtime['grafana_password'],0o640,'grafana')
    write('/etc/grafana/grafana.ini',f'''[server]
http_addr = 0.0.0.0
http_port = 3000
root_url = {runtime['grafana_url']}/
[security]
admin_user = admin
admin_password = $__file{{/etc/grafana/eletrometry-admin-password}}
cookie_samesite = lax
[users]
allow_sign_up = false
auto_assign_org_role = Viewer
[auth.anonymous]
enabled = false
[analytics]
reporting_enabled = false
check_for_updates = false
[dashboards]
default_home_dashboard_path = /var/lib/grafana/dashboards/visao-geral.json
min_refresh_interval = 5s
''',0o640,'grafana')
    write(ROOT/'neo4j.env',neo4j_env(runtime))
    write(ROOT/'neo4j_auth','neo4j/'+runtime['neo4j_password'],0o400)
    os.chown(ROOT/'neo4j_auth',7474,7474)
    BOOTSTRAP.unlink(missing_ok=True)
    print('Grafana configurado com leitor TLS; Neo4j configurado com autenticacao.')

if __name__=='__main__':
    try:
        main()
    except mysql.connector.Error as exc:
        raise SystemExit(f'Falha ao configurar leitor MySQL (codigo {exc.errno}); senhas omitidas.') from None
