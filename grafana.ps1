# Compatibilidade: agora tudo pertence ao mesmo Terraform e lab.ps1.
param([ValidateSet('subir','instalar','status','acesso','liberar-ip')][string]$Acao='status')
$map=@{subir='subir'; instalar='reparar-paineis'; status='paineis'; acesso='acesso'; 'liberar-ip'='liberar-ip'}
& (Join-Path $PSScriptRoot 'lab.ps1') $map[$Acao]
