# Windows PowerShell 5.1 / PowerShell 7. Administracao e testes usam SSM (HTTPS).
param(
    [ValidateSet('subir','atualizar','status','testar','simular','iniciar','parar','logs','entrar')]
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
        @{ commands = @($Command); executionTimeout = @([string]$Timeout) } |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $parametersPath -Encoding ASCII
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

if ($Acao -eq 'subir') {
    Push-Location $infra
    try {
        & terraform init -input=false
        Assert-Exit 'terraform init'
        & terraform validate
        Assert-Exit 'terraform validate'
        & terraform apply
        Assert-Exit 'terraform apply'
    } finally { Pop-Location }
    Write-Host 'Infraestrutura provisionada. Aguarde o bootstrap; depois execute .\lab.ps1 status.'
    return
}
$raw = & terraform "-chdir=$infra" output -json lab
Assert-Exit 'Leitura do state original (mantenha infra/terraform.tfstate)'
$script:lab = ($raw -join "`n") | ConvertFrom-Json
$script:instanceId = $lab.consumer_instance_id
$script:awsArgs = @('--region', $lab.aws_region, '--no-cli-pager')
if ($lab.aws_profile) { $script:awsArgs += @('--profile', $lab.aws_profile) }
$identity = (Invoke-Aws @('sts','get-caller-identity','--output','json')) | ConvertFrom-Json
if ($lab.account_id -and $identity.Account -ne $lab.account_id) { throw 'Credenciais pertencem a outra conta. Atualize o perfil do Lab.' }
$info = (Invoke-Aws @('ssm','describe-instance-information','--filters',"Key=InstanceIds,Values=$instanceId",'--output','json')) | ConvertFrom-Json
if (-not ($info.InstanceInformationList | Where-Object { $_.InstanceId -eq $instanceId -and $_.PingStatus -eq 'Online' })) {
    throw "EC2 $instanceId nao esta Online no SSM. Inicie o Lab/EC2 e aguarde o agente; confira credenciais e instance profile."
}
$python = '/opt/eletrometry/venv/bin/python /opt/eletrometry/lab_remote.py'
switch ($Acao) {
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
    'status' { Invoke-Remote "test -f /opt/eletrometry/lab_remote.py || { echo 'Execute .\lab.ps1 atualizar primeiro.'; exit 1; }; $python status" }
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
