#!/usr/bin/env bash
set -euo pipefail
umask 022

if [[ "$EUID" -ne 0 ]]; then
  echo 'Execute com sudo. Este instalador prepara a EC2 Ubuntu.' >&2
  exit 1
fi
if [[ "$#" -ne 1 || ! -f "$1" ]]; then
  echo 'Uso: sudo bash deploy/install.sh /caminho/runtime.json' >&2
  exit 1
fi

package_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_config="$(realpath "$1")"
repo_commit='038b257430c7fbad19cf0d42d7353a4f795eb5d3'
simulator_commit='866a56ea07f48e18773d27288cc20ed97f90f4f1'

export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 update
apt-get -o Acquire::Retries=3 install -y python3-venv git curl ca-certificates
if ! id eletrometry >/dev/null 2>&1; then
  useradd --system --home-dir /opt/eletrometry --shell /usr/sbin/nologin eletrometry
fi
install -d -m 0755 /opt/eletrometry /etc/eletrometry

# Verifica o checkout antes de instalar dependencias ou executar codigo.
if [[ ! -d /opt/eletrometry/repo/.git ]]; then
  if [[ -e /opt/eletrometry/repo ]]; then
    echo '/opt/eletrometry/repo existe sem .git; revise antes de prosseguir.' >&2
    exit 1
  fi
  git clone https://github.com/Eletrometry-Project/sqs-consumer.git /opt/eletrometry/repo
fi
if [[ -n "$(git -C /opt/eletrometry/repo status --porcelain)" ]]; then
  echo 'Checkout contem alteracoes locais; preservar e revisar antes da instalacao.' >&2
  exit 1
fi
git -C /opt/eletrometry/repo fetch origin "$repo_commit"
git -C /opt/eletrometry/repo checkout --detach "$repo_commit"
test "$(git -C /opt/eletrometry/repo rev-parse HEAD)" = "$repo_commit"

python3 -m venv /opt/eletrometry/venv
/opt/eletrometry/venv/bin/python -m pip install -r "$package_dir/deploy/requirements.lock.txt"
curl --fail --silent --show-error --location --retry 3 \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o /opt/eletrometry/global-bundle.pem
chmod 0644 /opt/eletrometry/global-bundle.pem

install -m 0644 "$runtime_config" /etc/eletrometry/runtime.json
install -m 0644 "$package_dir/deploy/check_database.py" /opt/eletrometry/check_database.py
install -m 0644 "$package_dir/deploy/run_service.py" /opt/eletrometry/run_service.py
install -m 0640 "$package_dir/deploy/setup_database.py" /opt/eletrometry/setup_database.py
install -m 0644 "$package_dir/sql/001-schema.sql" /opt/eletrometry/001-schema.sql
install -m 0644 "$package_dir/deploy/eletrometry-consumer.service" /etc/systemd/system/eletrometry-consumer.service
systemctl daemon-reload
systemctl stop eletrometry-consumer.service
/opt/eletrometry/venv/bin/python /opt/eletrometry/setup_database.py
systemctl enable --now eletrometry-consumer.service
# Fontes fixadas, iguais as copias incluidas no ZIP. O bootstrap baixa esses commits.
install -d "$package_dir/consumer" "$package_dir/telemetry"
cp /opt/eletrometry/repo/consumidor_sqs_mysql.py "$package_dir/consumer/"
if [[ ! -d /opt/eletrometry/simulator-source/.git ]]; then
  git clone https://github.com/Eletrometry-Project/telemetry-simulator.git /opt/eletrometry/simulator-source
fi
git -C /opt/eletrometry/simulator-source fetch origin "$simulator_commit"
git -C /opt/eletrometry/simulator-source checkout --detach "$simulator_commit"
test "$(git -C /opt/eletrometry/simulator-source rev-parse HEAD)" = "$simulator_commit"
cp /opt/eletrometry/simulator-source/simulador_eletrometry.py /opt/eletrometry/simulator-source/*.json "$package_dir/telemetry/"
bash "$package_dir/deploy/install_application.sh"
echo 'Bootstrap concluido: consumidor e simulador continuo iniciados. Execute lab.ps1 testar.' 
