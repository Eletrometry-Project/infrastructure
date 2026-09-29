param(
    [ValidateSet('Plan', 'Apply')]
    [string]$Action = 'Plan'
)

# Para db_password_mode = "write_only". A senha nao e escrita em arquivo.
$ErrorActionPreference = 'Stop'
$infraPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'infra'
$oldPassword = $env:TF_VAR_db_master_password
Push-Location $infraPath
try {
    if (-not (Test-Path 'terraform.tfvars')) {
        throw 'Copie terraform.tfvars.example para terraform.tfvars e configure seu IP antes.'
    }
    if (($Action -eq 'Apply') -and (-not (Test-Path 'reviewed.tfplan'))) {
        throw 'Primeiro gere e revise o plano com -Action Plan.'
    }
    $secret = Read-Host 'Senha administrativa RDS (16+ caracteres; no Apply repita a mesma do Plan)' -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try {
        $env:TF_VAR_db_master_password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $secret.Dispose()
    }

    if ($Action -eq 'Plan') {
        & terraform plan '-out=reviewed.tfplan'
        if ($LASTEXITCODE -ne 0) { throw 'terraform plan falhou; revise a mensagem.' }
        $planJson = & terraform show -json reviewed.tfplan
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel ler o plano.' }
        $planJson | Out-File -FilePath plan.json -Encoding utf8
        & py (Join-Path $PSScriptRoot 'check_plan.py') plan.json
        if ($LASTEXITCODE -ne 0) { throw 'Plano rejeitado: revisar exclusoes/substituicoes.' }
        Write-Host 'Revise o plano. Aplicacao e um passo separado: -Action Apply.'
    }
    else {
        # Executar esta acao significa aplicar o plano ja revisado.
        & terraform apply reviewed.tfplan
        if ($LASTEXITCODE -ne 0) { throw 'Apply incompleto; mantenha state e revise antes de repetir.' }
        $runtime = & terraform output -json runtime_config
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel exportar runtime_config.' }
        $runtime | Out-File -FilePath '../runtime.json' -Encoding utf8
        Write-Host 'Infraestrutura aplicada. Continue com verificacao do cloud-init e setup_database.py.'
    }
}
finally {
    $env:TF_VAR_db_master_password = $oldPassword
    Pop-Location
}
