# Executado pelo lab.ps1; usa o state e as credenciais SSM ja verificados.
function Send-PortalBytes([byte[]]$Bytes,[string]$Remote) {
    if ($Remote -notmatch '^/tmp/eletrometry-frontend-[a-f0-9]{32}/(bundle.tgz|configure.py)$') { throw 'Destino SSM invalido.' }
    $sha=[Security.Cryptography.SHA256]::Create()
    try { $digest=([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
    $encoded=[Convert]::ToBase64String($Bytes)
    Invoke-Remote "umask 077; : > '$Remote.b64'"
    for ($offset=0; $offset -lt $encoded.Length; $offset+=16000) {
        $part=$encoded.Substring($offset,[Math]::Min(16000,$encoded.Length-$offset))
        Invoke-Remote "set -e; printf '%s' '$part' >> '$Remote.b64'"
    }
    Invoke-Remote "set -e; base64 -d '$Remote.b64' > '$Remote'; echo '$digest  $Remote' | sha256sum -c -"
}
function Publish-Frontend([string]$ProjectRoot) {
    if (-not $lab.frontend_instance_id) { throw 'Frontend ausente no state. Execute .\lab.ps1 subir com a pasta infra atualizada.' }
    foreach ($ip in @($lab.frontend_private_ip,$lab.frontend_public_ip,$lab.grafana_private_ip)) {
        if ($ip -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { throw 'IP ausente ou invalido no state.' }
    }
    if ($lab.grafana_url -notmatch '^https?://[A-Za-z0-9.-]+(:[0-9]+)?$') { throw 'URL canonica do Grafana invalida no state.' }
    $bundle=Join-Path $ProjectRoot 'frontend-bundle.tar.gz'
    $config=Join-Path $ProjectRoot 'frontend/configure-grafana.py'
    $stage='/tmp/eletrometry-frontend-'+[guid]::NewGuid().ToString('N')
    $saved=$script:instanceId
    try {
        $script:instanceId=$lab.observability_instance_id
        Wait-Node $script:instanceId 300
        Invoke-Remote "umask 077; mkdir '$stage'"
        Send-PortalBytes ([IO.File]::ReadAllBytes($config)) "$stage/configure.py"
        Invoke-Remote "set -e; python3 '$stage/configure.py' $($lab.frontend_private_ip); rm -rf '$stage'"
        $script:instanceId=$lab.frontend_instance_id
        Wait-Node $script:instanceId 600
        Invoke-Remote "set -e; cloud-init status --wait; umask 077; mkdir '$stage'" 600
        Send-PortalBytes ([IO.File]::ReadAllBytes($bundle)) "$stage/bundle.tgz"
        $revision=(Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant()
        Invoke-Remote "set -e; cd '$stage'; tar -xzf bundle.tgz; bash install.sh $($lab.frontend_public_ip) $($lab.grafana_private_ip) $revision $($lab.grafana_url); cd /; rm -rf '$stage'" 1200
        $pem=Invoke-Remote 'cat /var/lib/eletrometry-frontend/tls/portal.crt' -Capture
        if ($pem.Trim() -notmatch '(?s)^-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----$') { throw 'Resposta SSM sem certificado publico valido.' }
        $crt=Join-Path $ProjectRoot 'portal-lab.cer'
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($crt),$pem.Trim(),[Text.Encoding]::ASCII)
        Write-Host 'Certificado publico recebido por SSM: portal-lab.cer. Veja PORTAL-AWS.md para confiar no certificado do lab.'
        Write-Host "Portal React na AWS: $($lab.portal_url)"
    } finally { $script:instanceId=$saved }
}
