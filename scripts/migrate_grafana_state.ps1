# Consolida somente os recursos conhecidos da etapa 2 no state local principal.
param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference='Stop'
$oldDir=Join-Path $ProjectRoot 'grafana/infra'
$oldState=Join-Path $oldDir 'terraform.tfstate'
$newState=Join-Path $ProjectRoot 'infra/terraform.tfstate'
if (-not (Test-Path $oldState)) { return }
$old=Get-Content -Raw $oldState | ConvertFrom-Json
$managed=@($old.resources | Where-Object { $_.mode -eq 'managed' })
if ($managed.Count -eq 0) { return }
if (-not (Test-Path $newState)) { throw 'Existe state da etapa 2, mas falta o state da etapa 1. Pare e recupere o arquivo original.' }
$new=Get-Content -Raw $newState | ConvertFrom-Json
$targetArn=$old.outputs.target_group_arn.value
$account=$new.outputs.lab.value.account_id
if (-not $account -or $targetArn -notlike "arn:aws:elasticloadbalancing:*:${account}:targetgroup/*") {
    throw 'Nao foi possivel confirmar que os dois states pertencem a mesma conta.'
}
$map=[ordered]@{
    'aws_security_group.alb'='aws_security_group.alb'
    'aws_vpc_security_group_ingress_rule.web'='aws_vpc_security_group_ingress_rule.web'
    'aws_vpc_security_group_egress_rule.grafana'='aws_vpc_security_group_egress_rule.grafana'
    'aws_vpc_security_group_ingress_rule.consumer_grafana'='aws_vpc_security_group_ingress_rule.observability_grafana'
    'aws_lb.grafana'='aws_lb.grafana'
    'aws_lb_target_group.grafana'='aws_lb_target_group.grafana'
    'aws_lb_target_group_attachment.grafana'='aws_lb_target_group_attachment.grafana'
    'aws_lb_listener.grafana'='aws_lb_listener.grafana'
}
foreach ($resource in $managed) {
    $address="$($resource.type).$($resource.name)"
    if ($resource.module -or -not $map.Contains($address)) { throw "Recurso nao previsto no state antigo: $address. Migracao interrompida antes de alterar arquivos." }
    $destination=$map[$address]
    if (@($new.resources | Where-Object { "$($_.type).$($_.name)" -eq $destination -and $_.mode -eq 'managed' }).Count -gt 0) {
        throw "Destino $destination ja existe no state principal. Nao sera sobrescrito."
    }
}
# Se houver interrompimento, as proximas execucoes movem apenas recursos restantes.
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$backup=Join-Path $ProjectRoot ('.state-backup-integracao-'+$stamp)
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $oldState -Destination (Join-Path $backup 'grafana.tfstate')
Copy-Item -LiteralPath $newState -Destination (Join-Path $backup 'principal.tfstate')
$cidrFile=Join-Path $ProjectRoot 'infra/observability.auto.tfvars.json'
if (-not (Test-Path $cidrFile)) {
    $web=$managed | Where-Object { $_.type -eq 'aws_vpc_security_group_ingress_rule' -and $_.name -eq 'web' }
    $cidrs=@($web.instances | ForEach-Object { $_.attributes.cidr_ipv4 } | Where-Object { $_ } | Select-Object -Unique)
    if ($cidrs.Count -gt 0) {
        @{ui_allowed_ipv4_cidrs=$cidrs} | ConvertTo-Json | Set-Content -LiteralPath $cidrFile -Encoding ASCII
    }
}
Write-Host "Consolidando o state da etapa 2. Backups: $backup"
foreach ($resource in $managed) {
    $address="$($resource.type).$($resource.name)"
    # Endereco do recurso completo move todas as instancias for_each sem problemas de aspas no PS 5.1.
    & terraform "-chdir=$ProjectRoot/infra" state mv "-state=$oldState" "-state-out=$newState" $address $map[$address]
    if ($LASTEXITCODE -ne 0) { throw "Migracao interrompida em $address. Preserve os dois states e os backups; nao execute apply." }
}
Write-Host 'State consolidado. Use apenas lab.ps1 e infra/ a partir de agora.'
