"""Empacota somente os artefatos necessários ao Docker, sem estado nem credenciais."""
from pathlib import Path
import tarfile
root=Path(__file__).resolve().parents[1]
with tarfile.open(root/'frontend-bundle.tar.gz','w:gz') as out:
    for name in ['Dockerfile','install.sh','verify.py','smoke.mjs']:
        out.add(root/'frontend'/name,arcname=name)
    for name in ['server.mjs','policy.mjs','dist/index.html','dist/app.js','dist/app.css','dist/cabine.svg']:
        out.add(root/'portal-react'/name,arcname=name)
