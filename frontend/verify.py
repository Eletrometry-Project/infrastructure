"""Verifica permissões reais da EC2 de frontend antes de publicar o portal."""
import json
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = 'http://' + sys.argv[1] + ':3000'
roles = ['analista', 'gestor']
uids = ['visao-geral', 'cabines', 'gestor', 'historico', 'tendencias']


def read(role, path):
    request = Request(base + path, headers={'X-Eletrometry-Reader': 'elt-portal-' + role})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


for role in roles:
    if read(role, '/api/user')['login'] != 'elt-portal-' + role:
        raise RuntimeError('Identidade do leitor inesperada: ' + role)

deadline = time.monotonic() + 60
while True:
    missing = []
    for role in roles:
        for uid in uids:
            full_uid = 'eletrometry-' + uid
            should_read = role == 'gestor' or uid in ['visao-geral', 'cabines']
            try:
                dashboard = read(role, '/api/dashboards/uid/' + full_uid)['dashboard']
            except HTTPError as error:
                if error.code not in (403, 404):
                    raise
                if should_read:
                    missing.append(role + '/' + uid)
            else:
                if dashboard['uid'] != full_uid or not should_read:
                    raise RuntimeError(f'Acesso inesperado: {role} / {uid}')
    if not missing:
        break
    if time.monotonic() >= deadline:
        raise RuntimeError('Permissão de leitura ausente: ' + ', '.join(missing))
    time.sleep(2)

print('Grafana privado: identidade e permissoes das 5 dashboards confirmadas para ambos os perfis.')
