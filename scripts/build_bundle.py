#!/usr/bin/env python3
"""Recria o pacote de aplicacao enviado pelo lab.ps1 atualizar. Sem state/segredos."""
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]
with tarfile.open(ROOT / 'app-bundle.tar.gz', 'w:gz') as archive:
    for directory in ('deploy', 'telemetry', 'consumer'):
        for file in sorted((ROOT / directory).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                archive.add(file, arcname=file.relative_to(ROOT))
print('app-bundle.tar.gz gerado')
