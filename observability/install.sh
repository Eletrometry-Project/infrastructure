#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
base=/opt/eletrometry-observability
state=/var/lib/eletrometry-observability
install -d -m 0700 /etc/eletrometry-observability
install -d -m 0755 "$state"
apt-get -o DPkg::Lock::Timeout=180 update -qq
apt-get -o DPkg::Lock::Timeout=180 install -y -qq ca-certificates curl python3-venv docker.io
install -d -m 0755 /etc/apt/keyrings
curl --fail --silent --show-error --retry 5 https://apt.grafana.com/gpg.key -o /etc/apt/keyrings/grafana.asc
chmod 0644 /etc/apt/keyrings/grafana.asc
printf '%s\n' 'deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main' > /etc/apt/sources.list.d/grafana.list
apt-get -o DPkg::Lock::Timeout=180 update -qq
systemctl mask grafana-server
apt-get -o DPkg::Lock::Timeout=180 install -y -qq grafana
systemctl stop grafana-server
python3 -m venv "$base/venv"
"$base/venv/bin/pip" install --quiet 'mysql-connector-python>=9,<10' 'PyYAML>=6,<7'
curl --fail --silent --show-error --retry 5 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o /etc/eletrometry-observability/global-bundle.pem
"$base/venv/bin/python" "$base/build_dashboard.py"
"$base/venv/bin/python" "$base/configure.py"
systemctl unmask grafana-server
systemctl enable --now grafana-server docker
install -d -o 7474 -g 7474 -m 0750 "$state/neo4j-data" "$state/neo4j-logs"
docker build -t eletrometry-neo4j:5.26.30 "$base/neo4j"
# Configuracao so recria o container; os dados ficam em bind mounts fora dele.
if docker container inspect eletrometry-neo4j >/dev/null 2>&1; then
  docker stop --time 60 eletrometry-neo4j >/dev/null || true
  docker rm eletrometry-neo4j >/dev/null
fi
docker create --name eletrometry-neo4j --restart=always --memory=2304m --cpus=1.5 \
  --log-opt max-size=10m --log-opt max-file=3 \
  --env-file /etc/eletrometry-observability/neo4j.env \
  --publish 7474:7474 --publish 7687:7687 \
  --mount type=bind,src=/etc/eletrometry-observability/neo4j_auth,dst=/run/secrets/neo4j_auth,readonly \
  --mount type=bind,src="$state/neo4j-data",dst=/data \
  --mount type=bind,src="$state/neo4j-logs",dst=/logs \
  eletrometry-neo4j:5.26.30 >/dev/null
install -m 0644 "$base/neo4j/eletrometry-neo4j.service" /etc/systemd/system/eletrometry-neo4j.service
systemctl daemon-reload
systemctl enable eletrometry-neo4j
systemctl restart eletrometry-neo4j
for attempt in $(seq 1 90); do
  health=$(docker inspect --format '{{.State.Health.Status}}' eletrometry-neo4j)
  if [ "$health" = healthy ] && curl --fail --silent http://127.0.0.1:3000/api/health >/dev/null; then
    "$base/venv/bin/python" "$base/health.py"
    touch "$state/installed"
    echo 'Instalacao automatica concluida: Grafana + Neo4j.'
    exit 0
  fi
  sleep 5
done
echo 'Servicos ainda nao saudaveis. Consulte journalctl -u eletrometry-bootstrap e docker logs eletrometry-neo4j.'
exit 1
