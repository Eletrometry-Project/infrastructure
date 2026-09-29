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

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv git curl ca-certificates
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
install -m 0644 "$package_dir/deploy/run_service.py" /opt/eletrometry/run_service.py
install -m 0640 "$package_dir/deploy/setup_database.py" /opt/eletrometry/setup_database.py
install -m 0644 "$package_dir/sql/001-schema.sql" /opt/eletrometry/001-schema.sql
install -m 0644 "$package_dir/deploy/eletrometry-consumer.service" /etc/systemd/system/eletrometry-consumer.service
systemctl daemon-reload
systemctl enable eletrometry-consumer.service

echo 'Arquivos instalados. O instalador nao inicia/reinicia o consumidor.'
echo 'Finalize com: sudo /opt/eletrometry/venv/bin/python /opt/eletrometry/setup_database.py'
echo 'Confira e pare o consumidor manual antigo antes de iniciar o novo servico.'
