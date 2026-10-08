# Espelha os arquivos versionados do projeto (codigo, docs, dicionarios)
# para uma pasta dentro do Google Drive compartilhado, para manter uma
# copia de seguranca sempre atualizada da "arquitetura" do projeto.
#
# IMPORTANTE: nao copiamos a pasta .git inteira nem a pasta do projeto
# "crua" para dentro do Drive. O Google Drive sincroniza arquivo por
# arquivo, sem conhecimento de git - se duas pessoas tivessem a pasta
# .git sincronizada ao mesmo tempo, o repositorio ficaria corrompido
# (o git espera controlar sozinho a escrita desses arquivos). Em vez
# disso, usamos "git ls-files" para pegar a lista exata de arquivos
# que estao commitados (o mesmo que esta no GitHub) e copiamos so eles,
# preservando a estrutura de pastas. Isso tambem evita sincronizar
# venv\, logs\, dados\*.sql, config.yaml (tem senha) e outros arquivos
# locais/temporarios que nao fazem parte da "arquitetura".
#
# Uso:
#   .\scripts\sincronizar_arquitetura_drive.ps1
#   (na primeira vez, pede o caminho da pasta do Drive e salva em
#   drive_backup_destino.txt, na raiz do projeto - esse arquivo e
#   local e nao e versionado)

$ErrorActionPreference = "Stop"

$raizProjeto = Split-Path -Parent $PSScriptRoot
$arquivoDestino = Join-Path $raizProjeto "drive_backup_destino.txt"

# Remove aspas (caso o caminho tenha sido colado com aspas, ex: copiado
# da barra de enderecos do Explorer) e espacos/barra final, que nao
# fazem parte do caminho real e fariam o PowerShell tentar interpretar
# o trecho entre aspas como nome de unidade (ex: '"G').
function Limpar-Caminho([string]$caminho) {
    $c = $caminho.Trim()
    $c = $c.Trim('"', "'")
    $c = $c.TrimEnd('\')
    return $c
}

if (-not (Test-Path $arquivoDestino)) {
    Write-Host ""
    Write-Host "Primeira vez configurando o espelhamento para o Google Drive."
    Write-Host "Informe o caminho completo da pasta do Google Drive compartilhado"
    Write-Host "onde a copia da arquitetura deve ficar (ex: G:\Drives compartilhados\SaidJur\codigo-fonte)."
    Write-Host "Essa pasta sera criada automaticamente se nao existir."
    Write-Host "(Nao precisa colocar aspas, mesmo se o caminho tiver espacos.)"
    Write-Host ""
    $destino = Limpar-Caminho (Read-Host "Caminho da pasta no Google Drive")
    Set-Content -Path $arquivoDestino -Value $destino -Encoding UTF8
} else {
    $destino = Limpar-Caminho (Get-Content -Path $arquivoDestino -Raw)
    # Auto-corrige o arquivo salvo caso tenha sido gravado com aspas
    # numa execucao anterior (self-heal).
    Set-Content -Path $arquivoDestino -Value $destino -Encoding UTF8
}

if (-not (Test-Path $destino)) {
    Write-Host "Criando pasta de destino: $destino"
    New-Item -ItemType Directory -Path $destino -Force | Out-Null
}

Write-Host ""
Write-Host "Sincronizando arquitetura do projeto para:"
Write-Host "  $destino"
Write-Host ""

Push-Location $raizProjeto
try {
    # Lista exata dos arquivos versionados no git (equivalente ao que
    # esta no GitHub nesta branch/commit atual).
    $arquivosVersionados = git ls-files

    if (-not $arquivosVersionados) {
        throw "Nao foi possivel listar arquivos do git. Rode este script de dentro do repositorio."
    }

    $copiados = 0
    foreach ($arquivoRelativo in $arquivosVersionados) {
        $origem = Join-Path $raizProjeto $arquivoRelativo
        $destinoArquivo = Join-Path $destino $arquivoRelativo

        $pastaDestino = Split-Path -Parent $destinoArquivo
        if ($pastaDestino -and -not (Test-Path $pastaDestino)) {
            New-Item -ItemType Directory -Path $pastaDestino -Force | Out-Null
        }

        Copy-Item -Path $origem -Destination $destinoArquivo -Force
        $copiados++
    }

    Write-Host "[OK] $copiados arquivos copiados/atualizados."

    # Remove do destino arquivos que nao existem mais entre os
    # versionados (ex: arquivos renomeados ou apagados do projeto),
    # para o destino continuar um espelho fiel. So mexe dentro da
    # propria pasta de destino dedicada - nunca fora dela.
    $arquivosVersionadosSet = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($a in $arquivosVersionados) {
        [void]$arquivosVersionadosSet.Add(($a -replace '/', '\'))
    }

    $removidos = 0
    Get-ChildItem -Path $destino -Recurse -File | ForEach-Object {
        $relativo = $_.FullName.Substring($destino.Length).TrimStart('\')
        if (-not $arquivosVersionadosSet.Contains($relativo)) {
            Remove-Item -Path $_.FullName -Force
            $removidos++
        }
    }

    if ($removidos -gt 0) {
        Write-Host "[OK] $removidos arquivo(s) obsoleto(s) removido(s) do espelho."
    }

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "  Espelhamento concluido com sucesso!"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host "O Google Drive devera sincronizar essa pasta automaticamente"
    Write-Host "para a nuvem e para os outros computadores que acessam o"
    Write-Host "mesmo drive compartilhado."
} finally {
    Pop-Location
}
