"""Gera pacote de reparacao SSM; o provisionamento inicial usa user-data Terraform."""
from pathlib import Path
import runpy
import tarfile
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'observability/build_dashboard.py'),run_name='__main__')
with tarfile.open(root/'observability-bundle.tar.gz','w:gz') as archive:
    for p in sorted((root/'observability').rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            archive.add(p,arcname=str(p.relative_to(root/'observability')))
print('observability-bundle.tar.gz pronto')

# lab.ps1 dashboards usa diretamente os JSONs e o instalador em texto.
