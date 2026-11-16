"""SSM on the Grafana EC2: trust only the private IP of the portal as auth proxy."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ip=ipaddress.IPv4Address(sys.argv[1])
if not ip.is_private: raise ValueError('Endereco privado do frontend esperado')
password=json.loads(Path('/etc/eletrometry-observability/runtime.json').read_text())['grafana_password']
auth=base64.b64encode(('admin:'+password).encode()).decode()
def api(path,data=None):
    req=Request('http://127.0.0.1:3000'+path,headers={'Authorization':'Basic '+auth,'Content-Type':'application/json'},
                data=None if data is None else json.dumps(data).encode())
    with urlopen(req,timeout=15) as r:return json.load(r)

readers_changed = False
for role in ['Analista','Gestor']:
    name='elt-portal-'+role.lower()
    email=name+'@eletrometry.invalid'
    try:user=api('/api/users/lookup?loginOrEmail='+name)
    except HTTPError as err:
        if err.code!=404:raise
        api('/api/admin/users',{'name':name,'login':name,'email':email,'password':secrets.token_urlsafe(48)})
        user=api('/api/users/lookup?loginOrEmail='+name)
    if user['email']!=email or user.get('isGrafanaAdmin') or user.get('isAdmin'):
        raise RuntimeError('Identidade dedicada em conflito. Revise '+name)
    orgs=api('/api/users/%d/orgs'%user['id'])
    if len(orgs)!=1 or orgs[0]['role']!='Viewer':raise RuntimeError('O leitor deve ter apenas o papel Viewer.')
    team_name='Eletrometry-'+role
    team=next((t for t in api('/api/teams/search?query='+team_name)['teams'] if t['name']==team_name),None)
    if not team:raise RuntimeError('Instale as cinco dashboards e suas equipes antes do portal.')
    if user['id'] not in [m['userId'] for m in api('/api/teams/%d/members'%team['id'])]:
        api('/api/teams/%d/members'%team['id'],{'userId':user['id']})
        readers_changed = True
drop=Path('/etc/systemd/system/grafana-server.service.d/eletrometry-frontend.conf')
drop.parent.mkdir(exist_ok=True)
config=f"""[Service]
Environment=GF_AUTH_PROXY_ENABLED=true
Environment=GF_AUTH_PROXY_HEADER_NAME=X-Eletrometry-Reader
Environment=GF_AUTH_PROXY_HEADER_PROPERTY=username
Environment=GF_AUTH_PROXY_AUTO_SIGN_UP=false
Environment=GF_AUTH_PROXY_WHITELIST={ip}
Environment=GF_AUTH_PROXY_ENABLE_LOGIN_TOKEN=false
"""
config_changed = not drop.exists() or drop.read_text() != config
if config_changed:
    tmp=drop.with_suffix('.tmp')
    tmp.write_text(config);os.replace(tmp,drop)
    subprocess.run(['systemctl','daemon-reload'],check=True)
if config_changed or readers_changed:
    subprocess.run(['systemctl','restart','grafana-server'],check=True)
for _ in range(40):
    try:api('/api/health');break
    except (URLError,TimeoutError):time.sleep(1)
else:raise RuntimeError('Grafana indisponivel apos configuracao')
print('Leitores configurados. Auth proxy aceita a EC2 de frontend em '+str(ip))
