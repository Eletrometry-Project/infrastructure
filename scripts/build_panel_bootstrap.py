"""Compact the shipped five dashboards and bootstrap files for EC2 user-data."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "observability"
names = ["install.sh", "configure.py", "health.py", "eletrometry-bootstrap.service",
         "neo4j/Dockerfile", "neo4j/health.sh", "neo4j/eletrometry-neo4j.service"]
files = {name: (source / name).read_text() for name in names}
for name in ["visao-geral", "eletrometry", "gestor", "historico", "tendencias"]:
    path = f"dashboards/{name}.json"
    files[path] = json.dumps(json.loads((source / path).read_text()), ensure_ascii=False, separators=(",", ":"))
payload = json.dumps(files, ensure_ascii=False, separators=(",", ":")).encode()
# Node is already used to compile the React distribution. Ubuntu decodes with brotli.
result = subprocess.run(["node", "-e", "process.stdout.write(require('node:zlib').brotliCompressSync(require('node:fs').readFileSync(0)))"], input=payload, capture_output=True, check=True)
(root / "infra/panel-files.br").write_bytes(result.stdout)
