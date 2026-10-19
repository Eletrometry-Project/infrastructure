# Transporta fontes UTF-8 legiveis; nao compacta nem executa o conteudo enviado.
# Invoke-Remote e fornecida por lab.ps1. Destino limitado a pasta temporaria da atualizacao.
function Send-TextSsm([string]$LocalPath, [string]$RemotePath) {
    if ($RemotePath -notmatch '^/tmp/eletrometry-dashboards-[a-f0-9]{32}/(install_dashboards\.py|dashboards/(eletrometry|visao-geral)\.json)$') {
        throw 'Destino remoto inesperado.'
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
    $content = [IO.File]::ReadAllText($LocalPath, $utf8)
    if ($content.Contains([string][char]0)) { throw 'Arquivo de texto contem NUL.' }
    $bytes = $utf8.GetBytes($content)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $digest = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    Invoke-Remote "set -e; umask 077; : > '$RemotePath'"
    $offset = 0
    while ($offset -lt $content.Length) {
        $count = [Math]::Min(8000, $content.Length - $offset)
        do {
            if ([char]::IsHighSurrogate($content[$offset + $count - 1])) { $count-- }
            $part = $content.Substring($offset, $count)
            # Aspas POSIX: caracteres como $, crase e substituicoes permanecem texto.
            $quoted = "'" + $part.Replace("'", "'" + [char]34 + "'" + [char]34 + "'") + "'"
            $command = "printf '%s' $quoted >> '$RemotePath'"
            if ($utf8.GetByteCount($command) -le 20000) { break }
            $count = [int][Math]::Floor($count / 2)
        } while ($count -gt 0)
        if ($count -le 0) { throw 'Nao foi possivel dividir o texto para SSM.' }
        Invoke-Remote $command
        $offset += $count
    }
    Invoke-Remote "printf '%s\n' '$digest  $RemotePath' | sha256sum -c -"
}
