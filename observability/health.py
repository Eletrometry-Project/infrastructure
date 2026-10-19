#!/usr/bin/env python3
"""Verifica consultas reais no Grafana/MySQL e Neo4j, sem escrever dados."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

RUNTIME=Path('/etc/eletrometry-observability/runtime.json')


def main():
    config=json.loads(RUNTIME.read_text())
    auth=base64.b64encode(('admin:'+config['grafana_password']).encode()).decode()
    def request(path,payload=None):
        req=urllib.request.Request('http://127.0.0.1:3000'+path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Authorization':'Basic '+auth,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:
            return json.load(response)
    request('/api/health')
    ds=request('/api/datasources/uid/eletrometry-mysql/health')
    if ds.get('status')!='OK':
        raise SystemExit('Datasource MySQL indisponivel.')
    result=request('/api/ds/query',{'from':'now-5m','to':'now','queries':[{'refId':'A','datasource':{'type':'mysql','uid':'eletrometry-mysql'},'format':'table',
        'rawSql':"SELECT cabine_id, COUNT(*) AS leituras_5min FROM leituras WHERE coletado_em >= UTC_TIMESTAMP() - INTERVAL 5 MINUTE GROUP BY cabine_id ORDER BY cabine_id"}]})
    query=result.get('results',{}).get('A',{})
    if query.get('error') or query.get('status',200)>=400 or 'frames' not in query:
        raise SystemExit('Consulta MySQL pelo Grafana falhou.')
    print('Grafana: OK | Consulta ao RDS via TLS: OK')
    rows=0
    for frame in query['frames']:
        fields=[f['name'] for f in frame['schema']['fields']]
        for row in zip(*frame.get('data',{}).get('values',[])):
            print(json.dumps(dict(zip(fields,row)),ensure_ascii=False)); rows+=1
    if not rows:
        print('Sem leituras nos ultimos 5 minutos; confira o simulador e o periodo.')
    subprocess.run(['docker','exec','eletrometry-neo4j','/opt/eletrometry-health.sh'],check=True,timeout=30)
    print('Neo4j: OK | Consulta autenticada RETURN 1: OK')
    print('Neo4j e um banco separado; nao ha sincronizacao automatica RDS -> Neo4j nesta entrega.')

if __name__=='__main__':
    try:
        main()
    except urllib.error.HTTPError as exc:
        sys.exit(f'Grafana HTTP {exc.code}; se alterou a senha admin, atualize runtime.json localmente.')
    except urllib.error.URLError:
        sys.exit('Grafana local indisponivel.')
    except subprocess.SubprocessError:
        sys.exit('Consulta Neo4j falhou. Confira docker logs eletrometry-neo4j.')
