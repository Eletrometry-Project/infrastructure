#!/usr/bin/env bash
# SSM/root: compila a imagem na EC2. Nenhuma senha entra no build.
set -Eeuo pipefail
cd "$(dirname "$0")"
public=$1
grafana=$2
revision=$3
canonical=$4
[[ "$revision" =~ ^[a-f0-9]{64}$ ]]
python3 - "$public" "$grafana" <<'PY'
import ipaddress,sys
for v in sys.argv[1:]: ipaddress.IPv4Address(v)
PY
exec 9>/run/eletrometry-frontend.lock
flock -w 120 9
if ! command -v docker >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get -o DPkg::Lock::Timeout=180 update -qq
  apt-get -o DPkg::Lock::Timeout=180 install -y docker.io openssl curl
fi
systemctl enable --now docker
tls=/var/lib/eletrometry-frontend/tls
data=/var/lib/eletrometry-frontend/data
install -d -o 1000 -g 1000 -m 0700 "$data"
install -d -m 0750 -o root -g 1000 "$tls"
if ! openssl x509 -in "$tls/portal.crt" -noout -checkend 604800 -checkip "$public" 2>/dev/null | grep -q 'does match' || ! openssl x509 -in "$tls/portal.crt" -noout -checkend 604800 >/dev/null 2>&1; then
  umask 077
  openssl req -x509 -nodes -newkey rsa:3072 -sha256 -days 365 \
    -subj "/CN=$public" -addext "subjectAltName=IP:$public" \
    -addext 'basicConstraints=critical,CA:FALSE' -addext 'extendedKeyUsage=serverAuth' \
    -keyout "$tls/new.key" -out "$tls/new.crt" 2>/dev/null
  chown root:1000 "$tls/new.key" "$tls/new.crt"; chmod 0640 "$tls/new.key" "$tls/new.crt"
  mv "$tls/new.key" "$tls/portal.key"; mv "$tls/new.crt" "$tls/portal.crt"
fi
image="eletrometry/portal:${revision:0:16}"
docker build --tag "$image" .
# Confira ACLs nativas antes de aceitar logins no portal.
python3 verify.py "$grafana"
name=eletrometry-portal
old="$name-previous"
# Recupera troca interrompida antes de iniciar outra.
if docker inspect "$old" >/dev/null 2>&1 && ! docker inspect "$name" >/dev/null 2>&1; then
  docker rename "$old" "$name"; docker start "$name" >/dev/null
fi
docker rm -f "$old" >/dev/null 2>&1 || true
if docker inspect "$name" >/dev/null 2>&1; then docker stop "$name" >/dev/null; docker rename "$name" "$old"; fi
rollback(){
  docker rm -f "$name" >/dev/null 2>&1 || true
  if docker inspect "$old" >/dev/null 2>&1; then docker rename "$old" "$name"; docker start "$name" >/dev/null; fi
}
trap rollback ERR
docker run -d --name "$name" --restart unless-stopped --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  -p 443:8443 -v "$data:/var/lib/portal" -v "$tls:/run/portal-tls:ro" \
  -e PORTAL_ORIGIN="https://$public" -e GRAFANA_URL="http://$grafana:3000" -e GRAFANA_CANONICAL_URL="$canonical" "$image" >/dev/null
ok=false
for _ in $(seq 1 20); do
  if curl -fsS --noproxy '*' --connect-to "$public:443:127.0.0.1:443" --cacert "$tls/portal.crt" "https://$public/portal-api/config" | grep -q '"grafana":true'; then ok=true; break; fi
  sleep 1
done
if ! "$ok"; then docker logs --tail 12 "$name"; rollback; exit 1; fi
docker exec "$name" node smoke.mjs
trap - ERR
docker rm "$old" >/dev/null 2>&1 || true
echo "Portal HTTPS ativo na EC2: https://$public"
