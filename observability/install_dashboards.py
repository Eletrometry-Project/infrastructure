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
                print(f"Validando {d['uid']} / painel {panel['id']}...",flush=True)
                result=api('/api/ds/query',{'from':str(start),'to':str(end),'queries':[{**target,'rawSql':substitute(target['rawSql'],start,end)}]})
                q=result.get('results',{}).get('A',{})
                if q.get('error') or q.get('status',200)>=400 or 'frames' not in q:
                    raise RuntimeError(f"SQL inválido em {d['uid']}, painel {panel['id']}: {q.get('error','sem frames')}")
    print(f'Consultas de {len(dashboards)} dashboards validadas (ultimos 5 minutos).')

def contains_config(actual,expected):
    # Grafana adds defaults; every supplied setting must still match.
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and contains_config(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(contains_config(a,e) for a,e in zip(actual,expected))
    return actual==expected


def configure_roles(dashboards,backup):
    # Restrict only the project folder. Refuse to change ACLs on a mixed folder.
    ids = {d['uid'] for d in dashboards}
    meta = api('/api/dashboards/uid/eletrometry-visao-geral')['meta']
    folder = meta.get('folderUid')
    if not folder or meta.get('folderTitle') != 'Eletrometry':
        raise RuntimeError('Pasta Eletrometry nao confirmada; revise as permissoes no Grafana.')
    contents = api('/api/search?folderUIDs='+folder+'&limit=5000')
    if {d['uid'] for d in contents} != ids:
        raise RuntimeError('A pasta contem outros itens; revise suas permissoes antes de restringi-la.')
    teams = {}
    for role in ['Analista','Gestor']:
        name = 'Eletrometry-'+role
        matches = [t for t in api('/api/teams/search?query='+name)['teams'] if t['name']==name]
        teams[role] = matches[0]['id'] if matches else api('/api/teams', {'name':name})['teamId']
    folder_api='/api/folders/'+folder+'/permissions'
    paths={uid:'/api/dashboards/uid/'+uid+'/permissions' for uid in ids}
    (backup/'permissions.json').write_text(json.dumps({path:api(path) for path in [folder_api,*paths.values()]},indent=2))
    analyst = {'teamId':teams['Analista'],'permission':1}
    manager = {'teamId':teams['Gestor'],'permission':1}
    api(folder_api,{'items':[manager]})
    for uid,path in paths.items():
        items=[analyst] if uid in ['eletrometry-visao-geral','eletrometry-cabines'] else []
        api(path,{'items':items})
    print('Permissoes de leitura aplicadas. Atribua cada leitor a Eletrometry-Analista ou Eletrometry-Gestor.')
    
def install(validate=False):
    files=[SOURCE/'dashboards/visao-geral.json',SOURCE/'dashboards/eletrometry.json',SOURCE/'dashboards/historico.json',SOURCE/'dashboards/gestor.json',SOURCE/'dashboards/tendencias.json']
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
                if all(g.get('title')==d['title'] and contains_config(g.get('panels'),d['panels']) and g.get('tags')==d.get('tags') for g,d in zip(loaded,dashboards)):break
            except Exception:
                pass
            time.sleep(3)
        else:raise RuntimeError('Arquivos instalados; Grafana ainda não confirmou carregamento em 90 s.')
    if validate:configure_roles(dashboards,backup)
    print('CONFIRMADO: 5/5 dashboards da entrega v6 carregadas no Grafana.' if validate else 'Arquivos gravados; carregamento nao verificado.')
    for d in dashboards: print(d['title'], '/d/'+d['uid'])
    print('Backup local:',backup)
    print('Visão geral: /d/eletrometry-visao-geral?theme=light')
    print('Cabine: /d/eletrometry-cabines?var-cabine=cabine-001&theme=light')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--validate',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Execute com sudo na EC2 dos painéis.')
    install(args.validate)
