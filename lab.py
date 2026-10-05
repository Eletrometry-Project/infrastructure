#!/usr/bin/env python3
"""Eletrometry macOS — Python 3 + Docker/Colima; sem dependencias pip.
Coloque ao lado de infra/ e app-bundle.tar.gz, no pacote SSM atualizado.
Uso: python3 lab.py subir|atualizar|status|testar|simular|iniciar|parar|logs|entrar
     python3 lab.py simular --duracao 120
Terraform e AWS CLI rodam em containers; entrar usa AWS CLI + plugin locais.
Credenciais: ~/.aws (incluindo session token do Lab), perfil definido no Terraform.
Imagens configuraveis: LAB_TERRAFORM_IMAGE e LAB_AWS_IMAGE.
O state original permanece em infra/. Nunca apague para repetir um apply.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
TF_IMAGE = os.environ.get('LAB_TERRAFORM_IMAGE', 'hashicorp/terraform:1.13.5')
AWS_IMAGE = os.environ.get('LAB_AWS_IMAGE', 'public.ecr.aws/aws-cli/aws-cli:latest')
ACTIONS = ('subir', 'atualizar', 'status', 'testar', 'simular', 'iniciar', 'parar', 'logs', 'entrar')


def run(args, capture=True):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode:
        # Nao imprimir argumentos: podem conter comandos remotos ou dados do pacote.
        message = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(message or 'Comando falhou (codigo %s).' % result.returncode)
    return (result.stdout or '').strip()


def container(image, args, interactive=False, project=False):
    cmd = ['docker', 'run', '--rm']
    if interactive:
        cmd += ['-i']
        if sys.stdin.isatty() and sys.stdout.isatty():
            cmd += ['-t']
    credentials = Path.home() / '.aws'
    if credentials.is_dir():
        cmd += ['-v', str(credentials) + ':/root/.aws:ro']
    if project:
        cmd += ['-v', str(ROOT) + ':/workspace', '-w', '/workspace/infra']
    for name in sorted(os.environ):
        if name.startswith('TF_VAR_') or name in (
            'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
            'AWS_PROFILE', 'AWS_REGION', 'AWS_DEFAULT_REGION'):
            cmd += ['-e', name]
    cmd += ['-e', 'AWS_PAGER=', '-e', 'AWS_CLI_AUTO_PROMPT=off', image]
    return cmd + list(args)


def terraform(*args, interactive=False):
    return run(container(TF_IMAGE, args, interactive, project=True), capture=not interactive)


class Lab:
    def __init__(self, config):
        self.config = config
        self.instance = config['consumer_instance_id']
        self.region = config['aws_region']
        if not re.fullmatch(r'i-[0-9a-f]+', self.instance):
            raise RuntimeError('consumer_instance_id invalido no output lab.')
        self.aws_args = ['--region', self.region, '--no-cli-pager']
        if config.get('aws_profile'):
            self.aws_args += ['--profile', config['aws_profile']]

    def aws(self, *args, output='json'):
        raw = run(container(AWS_IMAGE, list(args) + self.aws_args + ['--output', output]))
        return json.loads(raw) if output == 'json' else raw

    def check(self):
        identity = self.aws('sts', 'get-caller-identity')
        account = self.config.get('account_id')
        if account and str(identity['Account']) != str(account):
            raise RuntimeError('Credenciais pertencem a outra conta. Atualize o perfil do Lab.')
        info = self.aws('ssm', 'describe-instance-information', '--filters',
                        'Key=InstanceIds,Values=' + self.instance)
        if not any(item.get('InstanceId') == self.instance and item.get('PingStatus') == 'Online'
                   for item in info.get('InstanceInformationList', [])):
            raise RuntimeError('EC2 %s nao esta Online no SSM. Inicie o Lab/EC2 e aguarde '
                               'o agente; confira credenciais e instance profile.' % self.instance)

    def remote(self, command, timeout=900):
        # subprocess recebe lista de argumentos; aspas do JSON nao passam pelo shell.
        parameters = json.dumps({'commands': [command], 'executionTimeout': [str(timeout)]})
        response = self.aws('ssm', 'send-command', '--instance-ids', self.instance,
                            '--document-name', 'AWS-RunShellScript', '--parameters', parameters)
        command_id = response['Command']['CommandId']
        (ROOT / '.lab-last-command.json').write_text(json.dumps({
            'CommandId': command_id, 'InstanceId': self.instance, 'Region': self.region
        }, indent=2) + '\n', encoding='utf-8')
        print('Executando na EC2 (SSM %s)...' % command_id, flush=True)
        deadline = time.monotonic() + timeout + 60
        poll = 0
        while time.monotonic() < deadline:
            time.sleep(3)
            try:
                invocation = self.aws('ssm', 'get-command-invocation', '--command-id', command_id,
                                      '--instance-id', self.instance)
            except RuntimeError as exc:
                if 'InvocationDoesNotExist' in str(exc) and time.monotonic() < deadline:
                    continue
                raise
            status = invocation['Status']
            if status not in ('Pending', 'InProgress', 'Delayed', 'Cancelling'):
                for key in ('StandardOutputContent', 'StandardErrorContent'):
                    if invocation.get(key):
                        print(invocation[key], flush=True)
                if status != 'Success' or invocation.get('ResponseCode') != 0:
                    raise RuntimeError('Comando SSM %s terminou com %s, codigo %s. '
                                       'Use python3 lab.py logs.' %
                                       (command_id, status, invocation.get('ResponseCode')))
                return
            poll += 1
            if poll % 10 == 0:
                print('Ainda executando: %s.' % status, flush=True)
        raise RuntimeError('Tempo local esgotado. A execucao remota pode continuar; '
                           'CommandId=%s. Nao repita uma simulacao sem conferir o comando.' % command_id)

    def update(self):
        bundle = ROOT / 'app-bundle.tar.gz'
        if not bundle.is_file():
            raise RuntimeError('app-bundle.tar.gz ausente: extraia o pacote completo.')
        endpoint = self.aws('iot', 'describe-endpoint', '--endpoint-type', 'iot:Data-ATS',
                            '--query', 'endpointAddress', output='text').strip()
        if not re.fullmatch(r'[A-Za-z0-9-]+\.iot\.[a-z0-9-]+\.amazonaws\.com', endpoint):
            raise RuntimeError('Endpoint IoT inesperado.')
        payload = bundle.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        encoded = base64.b64encode(payload).decode('ascii')
        remote = '/tmp/eletrometry-update-' + uuid.uuid4().hex
        self.remote('set -e; umask 077; mkdir -p {0}; : > {0}/payload.b64'.format(remote))
        for offset in range(0, len(encoded), 24000):
            chunk = encoded[offset:offset + 24000]
            self.remote("printf '%%s' '%s' >> %s/payload.b64" % (chunk, remote))
        self.remote("set -e; base64 -d {0}/payload.b64 > {0}/app.tar.gz; "
                    "echo '{1}  {0}/app.tar.gz' | sha256sum -c -; "
                    "tar -xzf {0}/app.tar.gz -C {0}; "
                    "ELETROMETRY_IOT_ENDPOINT={2} bash {0}/deploy/install_application.sh; "
                    "rm -rf {0}".format(remote, digest, endpoint), 600)

    def act(self, action, duration):
        python = '/opt/eletrometry/venv/bin/python /opt/eletrometry/lab_remote.py'
        if action == 'atualizar':
            self.update()
        elif action == 'status':
            self.remote("test -f /opt/eletrometry/lab_remote.py || { "
                        "echo 'Execute python3 lab.py atualizar primeiro.'; exit 1; }; " + python + ' status')
        elif action == 'testar':
            self.remote(python + ' testar', 240)
        elif action == 'simular':
            self.remote(python + ' simular --duration %d' % duration, duration + 240)
        elif action == 'iniciar':
            self.remote('set -e; systemctl enable --now eletrometry-consumer eletrometry-simulator; '
                        'systemctl is-active eletrometry-consumer eletrometry-simulator')
        elif action == 'parar':
            self.remote('set -e; systemctl disable --now eletrometry-simulator; '
                        'echo Simulador parado. Consumidor continua esvaziando a fila.')
        elif action == 'logs':
            self.remote('journalctl -u eletrometry-consumer -u eletrometry-simulator '
                        '-n 80 --no-pager -o short-iso; cloud-init status')
        elif action == 'entrar':
            if not shutil.which('aws') or not shutil.which('session-manager-plugin'):
                raise RuntimeError('A acao entrar requer AWS CLI e Session Manager Plugin no Mac. '
                                   'Como alternativa, abra EC2 > Conectar > Session Manager no console AWS. '
                                   'As demais acoes usam Docker.')
            run(['aws', 'ssm', 'start-session', '--target', self.instance] + self.aws_args, capture=False)


def duration_value(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('Duracao deve ser um inteiro de 1 a 600.')
    if not 1 <= number <= 600:
        raise argparse.ArgumentTypeError('Duracao deve estar entre 1 e 600 segundos.')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('acao', nargs='?', default='status', choices=ACTIONS)
    parser.add_argument('--duracao', '-d', type=duration_value, default=120)
    args = parser.parse_args()
    os.environ['AWS_PAGER'] = ''
    if not (ROOT / 'infra').is_dir():
        raise RuntimeError('Coloque lab.py na raiz do pacote atualizado, ao lado de infra/.')
    if not shutil.which('docker'):
        raise RuntimeError('Docker nao encontrado no PATH. Use o Docker CLI com Colima.')
    try:
        run(['docker', 'info'])
    except RuntimeError:
        raise RuntimeError('Docker indisponivel. Execute colima start e tente novamente.')
    if args.acao == 'subir':
        terraform('init', '-input=false', interactive=True)
        terraform('validate', interactive=True)
        terraform('apply', interactive=True)
        print('Infraestrutura provisionada. Aguarde o bootstrap; depois execute python3 lab.py status.')
        return
    try:
        config = json.loads(terraform('output', '-json', 'lab'))
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError('Falha ao ler output lab. Use o pacote SSM atualizado e mantenha '
                           'infra/terraform.tfstate. Detalhe: %s' % exc)
    lab = Lab(config)
    lab.check()
    lab.act(args.acao, args.duracao)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrompido localmente. Operacoes AWS podem continuar; confira '
              '.lab-last-command.json antes de repetir uma simulacao.', file=sys.stderr)
        sys.exit(130)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print('Erro: %s' % error, file=sys.stderr)
        sys.exit(1)

