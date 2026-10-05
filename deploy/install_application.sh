#!/usr/bin/env bash
# Atualiza somente a aplicacao; mantem RDS, schema, senha e runtime existentes.
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo 'Execute como root via SSM'; exit 1; }
package_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f /etc/eletrometry/runtime.json
test -f /etc/eletrometry/mysql-password
test -x /opt/eletrometry/venv/bin/python
# Falha antes de alterar servicos se o pacote estiver incompleto.
for part in consumer/consumidor_sqs_mysql.py telemetry/simulador_eletrometry.py telemetry/config_industrial.json deploy/lab_remote.py; do
  test -f "$package_dir/$part"
done
/opt/eletrometry/venv/bin/python -c 'import boto3, mysql.connector; from zoneinfo import ZoneInfo; ZoneInfo("America/Sao_Paulo")'
systemctl stop eletrometry-simulator.service 2>/dev/null || true
systemctl stop eletrometry-consumer.service
install -d -m 0755 /opt/eletrometry/consumer /opt/eletrometry/telemetry
install -d -o eletrometry -g eletrometry -m 0750 /var/lib/eletrometry-simulator
install -m 0644 "$package_dir/consumer/consumidor_sqs_mysql.py" /opt/eletrometry/consumer/
install -m 0644 "$package_dir/telemetry/"*.py "$package_dir/telemetry/"*.json /opt/eletrometry/telemetry/
install -m 0644 "$package_dir/deploy/lab_remote.py" "$package_dir/deploy/check_database.py" "$package_dir/deploy/run_service.py" /opt/eletrometry/
install -m 0644 "$package_dir/deploy/eletrometry-consumer.service" "$package_dir/deploy/eletrometry-simulator.service" /etc/systemd/system/
/opt/eletrometry/venv/bin/python - <<'PY'
import json, os
from pathlib import Path
path = Path('/etc/eletrometry/runtime.json')
config = json.loads(path.read_text(encoding='utf-8-sig'))
config['repo_path'] = '/opt/eletrometry/consumer'
if os.environ.get('ELETROMETRY_IOT_ENDPOINT'):
    config['iot_endpoint'] = os.environ['ELETROMETRY_IOT_ENDPOINT']
path.write_text(json.dumps(config, indent=2))
PY
systemctl daemon-reload
systemctl enable --now eletrometry-consumer.service
/opt/eletrometry/venv/bin/python /opt/eletrometry/check_database.py
systemctl enable --now eletrometry-simulator.service
echo 'Aplicacao integrada instalada. Simulador continuo iniciado. Execute status, testar e simular.'
