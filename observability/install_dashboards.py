#!/usr/bin/env python3
"""Atualiza apenas dashboards. Preflight SQL via Grafana antes de publicar os JSONs."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request

SOURCE=Path(__file__).resolve().parent
DEST=Path('/var/lib/grafana/dashboards')
INI=Path('/etc/grafana/grafana.ini')

def substitute(query,from_ms,to_ms,cabine='cabine-001'):
    values={'cabine':cabine,'metrica':'temperatura','sensor':'temperatura','fase':'A'}
    for name,value in values.items():
        query=query.replace('${'+name+':sqlstring}',"'"+value.replace("'","''")+"'")
    query=query.replace('${__from}',str(from_ms)).replace('${__to}',str(to_ms))
    query=re.sub(r"\$__timeGroupAlias\(([^,]+),'\$__interval',NULL\)",r'FLOOR(UNIX_TIMESTAMP(\1)/60)*60 AS time',query)
    query=re.sub(r'\$__timeFilter\(([^)]+)\)',lambda m:f'{m[1]} BETWEEN FROM_UNIXTIME({from_ms}/1000) AND FROM_UNIXTIME({to_ms}/1000)',query)
    if '${' in query or '$__' in query:raise ValueError('Macro SQL não resolvida no preflight')
    return query

def api(path,payload=None):
    config=json.loads(Path('/etc/eletrometry-observability/runtime.json').read_text())
    auth=base64.b64encode(('admin:'+config['grafana_password']).encode()).decode()
    req=urllib.request.Request('http://127.0.0.1:3000'+path,data=None if payload is None else json.dumps(payload).encode(),
                              headers={'Authorization':'Basic '+auth,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)

def check_queries(dashboards):
    end=int(time.time()*1000);start=end-300000
    for d in dashboards:
        for panel in d['panels']:
            for target in panel.get('targets',[]):
                if not target.get('rawSql'):continue
                result=api('/api/ds/query',{'from':str(start),'to':str(end),'queries':[{**target,'rawSql':substitute(target['rawSql'],start,end)}]})
                q=result.get('results',{}).get('A',{})
                if q.get('error') or q.get('status',200)>=400 or 'frames' not in q:
                    raise RuntimeError(f"SQL inválido em {d['uid']}, painel {panel['id']}: {q.get('error','sem frames')}")
    print('Consultas das duas dashboards validadas pelo Grafana/MySQL (últimos 5 minutos).')

def install(validate=False):
    files=[SOURCE/'dashboards/visao-geral.json',SOURCE/'dashboards/eletrometry.json']
    dashboards=[json.loads(f.read_text()) for f in files]
    if validate:check_queries(dashboards)
    backup=Path('/var/lib/eletrometry-observability/dashboard-backups')/str(time.time_ns())
    backup.mkdir(parents=True,mode=0o700)
    DEST.mkdir(parents=True,exist_ok=True)
    for source in files:
        dest=DEST/source.name
        if dest.exists():shutil.copy2(dest,backup/dest.name)
        tmp=dest.with_suffix('.tmp');tmp.write_bytes(source.read_bytes());tmp.chmod(0o644);tmp.replace(dest)
    if INI.exists():
        current=INI.read_text()
        changed=current.replace('default_home_dashboard_path = /var/lib/grafana/dashboards/eletrometry.json',
                                'default_home_dashboard_path = /var/lib/grafana/dashboards/visao-geral.json')
        if changed!=current:
            shutil.copy2(INI,backup/'grafana.ini')
            INI.write_text(changed)
            if validate:subprocess.run(['systemctl','restart','grafana-server'],check=True)
    if validate:
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            try:
                loaded=[api('/api/dashboards/uid/'+d['uid'])['dashboard'] for d in dashboards]
                if all(g.get('title')==d['title'] and len(g.get('panels',[]))==len(d['panels']) for g,d in zip(loaded,dashboards)):break
            except Exception:
                time.sleep(3);continue
        else:raise RuntimeError('Arquivos instalados; Grafana ainda não confirmou carregamento em 90 s.')
    print('Dashboards instaladas. Backup local:',backup)
    print('Visão geral: /d/eletrometry-visao-geral?theme=light')
    print('Cabine: /d/eletrometry-cabines?var-cabine=cabine-001&theme=light')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--validate',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Execute com sudo na EC2 dos painéis.')
    install(args.validate)
