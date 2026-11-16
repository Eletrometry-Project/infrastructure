# Transfere bytes em Base64 ASCII para evitar conversoes de acentos/quebras de linha.
# O conteudo so e executado pelo instalador depois da validacao SHA-256.
function Send-TextSsm([string]$LocalPath, [string]$RemotePath) {
    if ($RemotePath -notmatch '^/tmp/eletrometry-dashboards-[a-f0-9]{32}/(install_dashboards\.py|dashboards/(eletrometry|visao-geral|historico|gestor|tendencias)\.json)$') {
        throw 'Destino remoto inesperado.'
    }
    $bytes = [IO.File]::ReadAllBytes($LocalPath)
    $encoded = [Convert]::ToBase64String($bytes)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $digest = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    $payload = $RemotePath + '.b64'
    Invoke-Remote "set -e; umask 077; : > '$payload'"
    for ($offset = 0; $offset -lt $encoded.Length; $offset += 16000) {
        $chunk = $encoded.Substring($offset, [Math]::Min(16000, $encoded.Length - $offset))
        Invoke-Remote "set -e; printf '%s' '$chunk' >> '$payload'"
    }
    Invoke-Remote "set -e; base64 --decode '$payload' > '$RemotePath'; printf '%s\n' '$digest  $RemotePath' | sha256sum -c -; rm -f '$payload'"
}
