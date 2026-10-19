# Windows PowerShell 5.1 / PowerShell 7. Administracao e testes usam SSM (HTTPS).
param(
    [ValidateSet('subir','atualizar','status','testar','simular','iniciar','parar','logs','entrar','acesso','paineis','reparar-paineis','liberar-ip','dashboards')]
    [string]$Acao = 'status',
    [ValidateRange(1,600)][int]$Duracao = 120
)
$ErrorActionPreference = 'Stop'
$env:AWS_PAGER = ''
$infra = Join-Path $PSScriptRoot 'infra'
function Assert-Exit([string]$Etapa) {
    if ($LASTEXITCODE -ne 0) { throw "$Etapa falhou (codigo $LASTEXITCODE)." }
}
function Invoke-Aws([string[]]$Argumentos) {
    $result = & aws @Argumentos @script:awsArgs
    Assert-Exit 'AWS CLI (confira a mensagem acima)'
    return ($result -join "`n")
}
function Invoke-Remote([string]$Command, [int]$Timeout = 900) {
    $parametersPath = Join-Path ([IO.Path]::GetTempPath()) ('eletrometry-' + [guid]::NewGuid().ToString('N') + '.json')
    try {
        # Arquivo JSON evita a perda de aspas no Windows PowerShell 5.1.
        $parametersJson = @{ commands = @($Command); executionTimeout = @([string]$Timeout) } | ConvertTo-Json -Depth 4
        # UTF-8 sem BOM preserva acentos dos JSONs e fontes no PowerShell 5.1 e 7.
        [IO.File]::WriteAllText($parametersPath, $parametersJson, (New-Object System.Text.UTF8Encoding($false)))
        $raw = Invoke-Aws @('ssm','send-command','--instance-ids',$script:instanceId,
            '--document-name','AWS-RunShellScript','--parameters',('file://' + $parametersPath),'--output','json')
        $id = ($raw | ConvertFrom-Json).Command.CommandId
        @{ CommandId=$id; InstanceId=$script:instanceId; Region=$script:lab.aws_region } |
            ConvertTo-Json | Set-Content (Join-Path $PSScriptRoot '.lab-last-command.json') -Encoding ASCII
        Write-Host "Executando na EC2 (SSM $id)..."
        $deadline = (Get-Date).AddSeconds($Timeout + 60)
        $poll = 0
        do {
            Start-Sleep -Seconds 3
            $savedPreference = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            $result = & aws ssm get-command-invocation --command-id $id --instance-id $script:instanceId --output json @script:awsArgs 2>&1
            $exitCode = $LASTEXITCODE
            $ErrorActionPreference = $savedPreference
            $raw = ($result | ForEach-Object { $_.ToString() }) -join "`n"
            if ($exitCode -ne 0) {
                if ($raw -match 'InvocationDoesNotExist' -and (Get-Date) -lt $deadline) { continue }
                throw $raw
            }
            $invocation = $raw | ConvertFrom-Json
            if ($invocation.Status -notin @('Pending','InProgress','Delayed','Cancelling')) {
                if ($invocation.StandardOutputContent) { Write-Host $invocation.StandardOutputContent }
                if ($invocation.StandardErrorContent) { Write-Host $invocation.StandardErrorContent }
                if ($invocation.Status -ne 'Success' -or $invocation.ResponseCode -ne 0) {
                    throw "Comando SSM $id terminou com $($invocation.Status), codigo $($invocation.ResponseCode). Use .\lab.ps1 logs."
                }
                return
            }
            $poll++
            if ($poll % 10 -eq 0) { Write-Host "Ainda executando: $($invocation.Status)." }
        } while ((Get-Date) -lt $deadline)
        throw "Tempo local esgotado. A execucao remota pode continuar; CommandId=$id. Nao repita uma simulacao sem conferir o comando."
    } finally { Remove-Item -LiteralPath $parametersPath -ErrorAction SilentlyContinue }
}

$justApplied = $false
if ($Acao -in @('subir','liberar-ip')) {
    & terraform "-chdir=$infra" init -input=false
    Assert-Exit 'terraform init'
    if ($Acao -eq 'liberar-ip') {
        $ip=(Invoke-RestMethod 'https://checkip.amazonaws.com').Trim()
        if ($ip -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { throw 'IP publico inesperado.' }
        $path=Join-Path $infra 'observability.auto.tfvars.json'
        $cidrs=@("$ip/32")
        if (Test-Path $path) {
            $existing=Get-Content -Raw $path | ConvertFrom-Json
            $cidrs=@(@($existing.ui_allowed_ipv4_cidrs)+$cidrs | Select-Object -Unique)
        }
        @{ui_allowed_ipv4_cidrs=$cidrs} | ConvertTo-Json | Set-Content -LiteralPath $path -Encoding ASCII
    }
    & terraform "-chdir=$infra" validate
    Assert-Exit 'terraform validate'
    & (Join-Path $PSScriptRoot 'scripts/migrate_grafana_state.ps1') -ProjectRoot $PSScriptRoot
    & terraform "-chdir=$infra" plan -out=integrado.tfplan -input=false
    Assert-Exit 'terraform plan'
    $confirm=Read-Host 'Revise o plano. Digite yes para aplicar'
    if ($confirm -cne 'yes') { Write-Host 'Plano nao aplicado.'; return }
    & terraform "-chdir=$infra" apply integrado.tfplan
    Assert-Exit 'terraform apply'
    Remove-Item (Join-Path $infra 'integrado.tfplan') -ErrorAction SilentlyContinue
    $justApplied=$true
    $Acao='status'
}
$raw = & terraform "-chdir=$infra" output -json lab
Assert-Exit 'Leitura do state original (mantenha infra/terraform.tfstate)'
$script:lab = ($raw -join "`n") | ConvertFrom-Json
$script:instanceId = $lab.consumer_instance_id
$script:awsArgs = @('--region', $lab.aws_region, '--no-cli-pager')
if ($lab.aws_profile) { $script:awsArgs += @('--profile', $lab.aws_profile) }
$identity = (Invoke-Aws @('sts','get-caller-identity','--output','json')) | ConvertFrom-Json
if ($lab.account_id -and $identity.Account -ne $lab.account_id) { throw 'Credenciais pertencem a outra conta. Atualize o perfil do Lab.' }
function Wait-Node([string]$Id, [int]$Seconds=30) {
    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        $info=(Invoke-Aws @('ssm','describe-instance-information','--filters',"Key=InstanceIds,Values=$Id",'--output','json')) | ConvertFrom-Json
        if ($info.InstanceInformationList | Where-Object { $_.InstanceId -eq $Id -and $_.PingStatus -eq 'Online' }) { return }
        Write-Host "Aguardando EC2 $Id no SSM..."
        Start-Sleep -Seconds 10
    } while ((Get-Date) -lt $deadline)
    throw "EC2 $Id nao esta Online no SSM. Confira Lab, instance profile e estado da instancia."
}
function Invoke-PanelStatus {
    $saved=$script:instanceId
    try {
        $script:instanceId=$lab.observability_instance_id
        if (-not $script:instanceId) { throw 'Paineis ausentes no state. Execute .\lab.ps1 subir com o pacote integrado.' }
        Wait-Node $script:instanceId $(if ($justApplied) {600} else {30})
        if ($justApplied) {
            Write-Host 'Aguardando instalacao automatica do Grafana e Neo4j (pode levar varios minutos)...'
            Invoke-Remote 'set -e; for i in $(seq 1 240); do if test -f /var/lib/eletrometry-observability/installed; then exit 0; fi; sleep 5; done; echo Instalacao ainda nao concluiu. Consulte journalctl -u eletrometry-bootstrap; exit 1' 1250
        }
        Invoke-Remote 'set -e; systemctl is-active grafana-server eletrometry-neo4j; /opt/eletrometry-observability/venv/bin/python /opt/eletrometry-observability/health.py'
        $targets=(Invoke-Aws @('elbv2','describe-target-health','--target-group-arn',$lab.target_group_arn,'--output','json')) | ConvertFrom-Json
        $target=$targets.TargetHealthDescriptions | Where-Object { $_.Target.Id -eq $script:instanceId }
        Write-Host "ALB: $($target.TargetHealth.State) $($target.TargetHealth.Reason)"
        if ($target.TargetHealth.State -ne 'healthy') { throw 'ALB ainda nao saudavel. Aguarde 30 segundos e rode .\lab.ps1 paineis.' }
        Write-Host "Grafana: $($lab.grafana_url)"
        Write-Host "Neo4j Browser: $($lab.neo4j_browser_url)"
        Write-Host "Neo4j conexao: $($lab.neo4j_bolt_url)"
        Write-Host 'Para ver os logins: .\lab.ps1 acesso'
    } finally { $script:instanceId=$saved }
}
if ($Acao -notin @('acesso','paineis','reparar-paineis','dashboards')) {
    Wait-Node $instanceId $(if ($justApplied) {600} else {30})
    if ($justApplied) {
        Invoke-Remote 'cloud-init status --wait || test -f /etc/eletrometry/runtime.json' 1200
    }
}
$python = '/opt/eletrometry/venv/bin/python /opt/eletrometry/lab_remote.py'
switch ($Acao) {
    'paineis' { Invoke-PanelStatus }
    'acesso' {
        $script:instanceId=$lab.observability_instance_id
        if (-not $instanceId) { throw 'Execute .\lab.ps1 subir primeiro.' }
        Wait-Node $instanceId
        $accessCommand = @'
/opt/eletrometry-observability/venv/bin/python - <<'PYCODE'
import json
with open('/etc/eletrometry-observability/runtime.json') as f:
    d=json.load(f)
print('Grafana - usuario: admin | senha:',d['grafana_password'])
print('Neo4j - usuario: neo4j | senha:',d['neo4j_password'])
PYCODE
'@
        Invoke-Remote $accessCommand
        Write-Host "Grafana: $($lab.grafana_url)"
        Write-Host "Neo4j Browser: $($lab.neo4j_browser_url)"
        Write-Host "Conexao Neo4j: $($lab.neo4j_bolt_url)"
    }
    'dashboards' {
        $script:instanceId=$lab.observability_instance_id
        if (-not $instanceId) { throw 'Execute .\lab.ps1 subir primeiro.' }
        Wait-Node $instanceId
        . (Join-Path $PSScriptRoot 'scripts/send_text_ssm.ps1')
        $remote='/tmp/eletrometry-dashboards-'+[guid]::NewGuid().ToString('N')
        # Valida os dois documentos localmente antes de iniciar a transferencia.
        foreach ($name in @('visao-geral','eletrometry')) {
            $file=Join-Path $PSScriptRoot "observability/dashboards/$name.json"
            $document=[IO.File]::ReadAllText($file) | ConvertFrom-Json
            $expected=if ($name -eq 'visao-geral') {'eletrometry-visao-geral'} else {'eletrometry-cabines'}
            if ($document.uid -ne $expected -or -not $document.panels) { throw "Dashboard invalida: $name" }
        }
        Invoke-Remote "set -e; umask 077; mkdir '$remote'; mkdir '$remote/dashboards'"
        Write-Host 'Enviando instalador e dashboards em texto UTF-8 com verificacao SHA-256...'
        Send-TextSsm (Join-Path $PSScriptRoot 'observability/install_dashboards.py') "$remote/install_dashboards.py"
        foreach ($name in @('visao-geral','eletrometry')) {
            Send-TextSsm (Join-Path $PSScriptRoot "observability/dashboards/$name.json") "$remote/dashboards/$name.json"
        }
        # So executa apos as tres transferencias passarem pela verificacao de integridade.
        Invoke-Remote "set -e; /opt/eletrometry-observability/venv/bin/python $remote/install_dashboards.py --validate; cp $remote/dashboards/*.json /opt/eletrometry-observability/dashboards/; rm -rf $remote" 900
        Write-Host "Abra: $($lab.grafana_url)/d/eletrometry-visao-geral?theme=light"
    }
    'reparar-paineis' {
        $script:instanceId=$lab.observability_instance_id
        if (-not $instanceId) { throw 'Execute .\lab.ps1 subir primeiro.' }
        Wait-Node $instanceId
        $bundle=Join-Path $PSScriptRoot 'observability-bundle.tar.gz'
        $digest=(Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant()
        $encoded=[Convert]::ToBase64String([IO.File]::ReadAllBytes($bundle))
        $remote='/tmp/eletrometry-paineis-'+[guid]::NewGuid().ToString('N')
        Invoke-Remote "umask 077; mkdir -p $remote; : > $remote/payload.b64"
        for ($offset=0; $offset -lt $encoded.Length; $offset+=24000) {
            $chunk=$encoded.Substring($offset,[Math]::Min(24000,$encoded.Length-$offset))
            Invoke-Remote "printf '%s' '$chunk' >> $remote/payload.b64"
        }
        Invoke-Remote "set -e; systemctl stop eletrometry-bootstrap; base64 -d $remote/payload.b64 > $remote/package.tar.gz; echo '$digest  $remote/package.tar.gz' | sha256sum -c -; tar -xzf $remote/package.tar.gz -C /opt/eletrometry-observability; install -m 0644 /opt/eletrometry-observability/eletrometry-bootstrap.service /etc/systemd/system/eletrometry-bootstrap.service; systemctl daemon-reload; rm -f /var/lib/eletrometry-observability/installed; systemctl restart --no-block eletrometry-bootstrap; rm -rf $remote"
        $justApplied=$true
        Invoke-PanelStatus
    }
    'atualizar' {
        $bundle = Join-Path $PSScriptRoot 'app-bundle.tar.gz'
        if (-not (Test-Path $bundle)) { throw 'app-bundle.tar.gz ausente: extraia o pacote completo.' }
        $endpoint = (Invoke-Aws @('iot','describe-endpoint','--endpoint-type','iot:Data-ATS','--query','endpointAddress','--output','text')).Trim()
        if ($endpoint -notmatch '^[A-Za-z0-9-]+\.iot\.[a-z0-9-]+\.amazonaws\.com$') { throw 'Endpoint IoT inesperado.' }
        $bytes = [IO.File]::ReadAllBytes($bundle)
        $digest = (Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant()
        $encoded = [Convert]::ToBase64String($bytes)
        $remote = '/tmp/eletrometry-update-' + [guid]::NewGuid().ToString('N')
        Invoke-Remote "umask 077; mkdir -p $remote; : > $remote/payload.b64"
        for ($offset=0; $offset -lt $encoded.Length; $offset += 24000) {
            $chunk = $encoded.Substring($offset, [Math]::Min(24000, $encoded.Length - $offset))
            Invoke-Remote "printf '%s' '$chunk' >> $remote/payload.b64"
        }
        Invoke-Remote "set -e; base64 -d $remote/payload.b64 > $remote/app.tar.gz; echo '$digest  $remote/app.tar.gz' | sha256sum -c -; tar -xzf $remote/app.tar.gz -C $remote; ELETROMETRY_IOT_ENDPOINT=$endpoint bash $remote/deploy/install_application.sh; rm -rf $remote" 600
    }
    'status' { Invoke-Remote "test -f /opt/eletrometry/lab_remote.py || { echo 'Execute .\lab.ps1 atualizar primeiro.'; exit 1; }; $python status"; Invoke-PanelStatus }
    'testar' { Invoke-Remote "$python testar" 240 }
    'simular' { Invoke-Remote "$python simular --duration $Duracao" ($Duracao + 240) }
    'iniciar' { Invoke-Remote 'systemctl enable --now eletrometry-consumer eletrometry-simulator; systemctl is-active eletrometry-consumer eletrometry-simulator' }
    'parar' { Invoke-Remote 'systemctl disable --now eletrometry-simulator; echo Simulador parado. Consumidor continua esvaziando a fila.' }
    'logs' { Invoke-Remote 'journalctl -u eletrometry-consumer -u eletrometry-simulator -n 80 --no-pager -o short-iso; cloud-init status' }
    'entrar' {
        & aws ssm start-session --target $instanceId @script:awsArgs
        Assert-Exit 'Sessao SSM (este comando opcional requer Session Manager Plugin no PC)'
    }
}
