<#
.SYNOPSIS
    Importa um arquivo .sql MySQL para o banco de dados local.

.DESCRIPTION
    Este script lê as credenciais do config.yaml, cria o banco de dados
    se necessário, e importa o arquivo .sql com barra de progresso por bytes.

.PARAMETER ArquivoSQL
    Caminho completo para o arquivo .sql a ser importado.

.EXAMPLE
    .\importar.ps1 -ArquivoSQL "dados\backup.sql"
#>

param(
    [string]$ArquivoSQL,
    [switch]$SomenteLerConfig,
    [string]$ConfigPath
)

# Configurações de encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ── Funções auxiliares ──────────────────────────────────────────────────────

function Ler-Config {
    param(
        [string]$ConfigPath
    )

    if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
        $ConfigPath = Join-Path $PSScriptRoot "..\config.yaml"
    }

    if (-not (Test-Path $ConfigPath)) {
        Write-Host "[ERRO] Arquivo config.yaml não encontrado." -ForegroundColor Red
        Write-Host "Execute instalar.bat primeiro." -ForegroundColor Yellow
        exit 1
    }

    $config = @{}
    $secao = ""
    foreach ($linha in Get-Content $ConfigPath -Encoding UTF8) {
        $linha = $linha.Trim()
        if ($linha -eq "") { continue }
        if ($linha.StartsWith("#")) { continue }

        if ($linha -match '^(\w+):\s*(?:#.*)?$') {
            $secao = $matches[1]
            $config[$secao] = @{}
        }
        elseif ($linha -match '^(\w+):\s*(.*)$' -and $secao -ne "") {
            $chave = $matches[1]
            $valorBruto = $matches[2].Trim()

            # Valor entre aspas duplas, permitindo apenas escapes \" e \\,
            # com suporte a comentário inline fora das aspas.
            if ($valorBruto -match '^\s*"((?:[^"\\]|\\["\\])*)"\s*(?:#.*)?$') {
                $valor = [regex]::Replace($matches[1], '\\(["\\])', '$1')
            }
            elseif ($valorBruto -match "^\s*'((?:[^']|'')*)'\s*(?:#.*)?$") {
                $valor = $matches[1] -replace "''", "'"
            }
            else {
                $valor = ($valorBruto -replace '\s+#.*$', '').Trim()
            }

            $config[$secao][$chave] = $valor
        }
    }
    return $config
}

function Formatar-Tamanho {
    param([long]$bytes)
    if ($bytes -ge 1GB) { return "{0:N2} GB" -f ($bytes / 1GB) }
    if ($bytes -ge 1MB) { return "{0:N1} MB" -f ($bytes / 1MB) }
    return "{0:N0} KB" -f ($bytes / 1KB)
}

function Formatar-Duracao {
    param([TimeSpan]$ts)
    if ($ts.TotalHours -ge 1) { return "{0}h {1}min" -f [int]$ts.TotalHours, $ts.Minutes }
    if ($ts.TotalMinutes -ge 1) { return "{0}min {1}s" -f [int]$ts.TotalMinutes, $ts.Seconds }
    return "{0}s" -f [int]$ts.TotalSeconds
}

# ── Início ──────────────────────────────────────────────────────────────────

if ($SomenteLerConfig) {
    $config = Ler-Config -ConfigPath $ConfigPath
    $config | ConvertTo-Json -Depth 5 -Compress
    exit 0
}

if ([string]::IsNullOrWhiteSpace($ArquivoSQL)) {
    Write-Host "[ERRO] Informe o caminho do arquivo .sql para importar." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Importador SQL - SaidJur" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Valida arquivo
if (-not (Test-Path $ArquivoSQL)) {
    Write-Host "[ERRO] Arquivo não encontrado: $ArquivoSQL" -ForegroundColor Red
    exit 1
}

$arquivoInfo = Get-Item $ArquivoSQL
$tamanhoTotal = $arquivoInfo.Length
$tamanhoFormatado = Formatar-Tamanho $tamanhoTotal

Write-Host "Arquivo : $($arquivoInfo.Name)" -ForegroundColor White
Write-Host "Tamanho : $tamanhoFormatado" -ForegroundColor White
Write-Host ""

# Lê configuração
$config = Ler-Config
$dbHost   = $config["banco"]["host"]
$dbPorta  = $config["banco"]["porta"]
$dbUsuario = $config["banco"]["usuario"]
$dbSenha  = $config["banco"]["senha"]
$dbNome   = $config["banco"]["nome"]

# Aviso importante
Write-Host "⚠️  ATENÇÃO" -ForegroundColor Yellow
Write-Host "──────────────────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host "Esta operação pode levar várias horas e exige cerca de" -ForegroundColor Yellow
Write-Host "100 GB livres no disco (para um arquivo de 50 GB)." -ForegroundColor Yellow
Write-Host "NÃO feche esta janela durante a importação." -ForegroundColor Yellow
Write-Host "──────────────────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host ""
$resposta = Read-Host "Deseja continuar? [S/N]"
if ($resposta -notmatch '^[Ss]$') {
    Write-Host "Operação cancelada pelo usuário." -ForegroundColor Yellow
    exit 0
}

# Cria pasta de logs
$logDir = Join-Path $PSScriptRoot "..\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$dataHora = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "importacao_$dataHora.log"

function Log {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp $msg" | Out-File -FilePath $logFile -Encoding UTF8 -Append
}

Log "Início da importação"
Log "Arquivo: $ArquivoSQL ($tamanhoFormatado)"
Log "Banco  : $dbNome em ${dbHost}:${dbPorta}"

Write-Host ""
Write-Host "Log sendo gravado em: $logFile" -ForegroundColor Gray
Write-Host ""

# Verifica mysql no PATH
try {
    $mysqlVersion = mysql --version 2>&1
    Write-Host "[OK] MySQL encontrado: $mysqlVersion" -ForegroundColor Green
    Log "MySQL: $mysqlVersion"
} catch {
    Write-Host "[ERRO] Comando 'mysql' não encontrado no PATH." -ForegroundColor Red
    Write-Host "Consulte INSTALL_WINDOWS.md para adicionar ao PATH." -ForegroundColor Yellow
    Log "ERRO: mysql não encontrado no PATH"
    exit 1
}

# Cria banco de dados se não existir
Write-Host ""
Write-Host "Criando banco de dados '$dbNome' (se não existir)..." -ForegroundColor Cyan

$criarDB = "CREATE DATABASE IF NOT EXISTS ``$dbNome`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

$mysqlCreateArgs = @("-h", $dbHost, "-P", $dbPorta, "-u", $dbUsuario)
if ($dbSenha -ne "") { $mysqlCreateArgs += "-p$dbSenha" }
$mysqlCreateArgs += @("-e", $criarDB)
$resultado = & mysql @mysqlCreateArgs 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] Falha ao conectar ao MySQL." -ForegroundColor Red
    Write-Host "Verifique host, porta, usuário e senha no config.yaml" -ForegroundColor Yellow
    Write-Host "Detalhe: $resultado" -ForegroundColor Gray
    Log "ERRO ao criar banco: $resultado"
    exit 1
}

Write-Host "[OK] Banco de dados pronto." -ForegroundColor Green
Log "Banco criado/verificado com sucesso"

# Importação com progresso
Write-Host ""
Write-Host "Iniciando importação..." -ForegroundColor Cyan
Write-Host "(Isso pode levar de 2 a 12 horas para arquivos de 50 GB)" -ForegroundColor Gray
Write-Host ""

$inicio = Get-Date
$bytesLidos = 0
$bufferSize = 64KB
$buffer = New-Object byte[] $bufferSize

$streamLeitura = [System.IO.File]::OpenRead($ArquivoSQL)

# Monta argumentos do mysql
$mysqlArgs = @(
    "--default-character-set=utf8mb4"
    "-h", $dbHost
    "-P", $dbPorta
    "-u", $dbUsuario
)
if ($dbSenha -ne "") { $mysqlArgs += "-p$dbSenha" }
$mysqlArgs += $dbNome

# Inicia processo mysql
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "mysql"
$processInfo.Arguments = $mysqlArgs -join " "
$processInfo.UseShellExecute = $false
$processInfo.RedirectStandardInput = $true
$processInfo.RedirectStandardError = $true

$processo = New-Object System.Diagnostics.Process
$processo.StartInfo = $processInfo
$processo.Start() | Out-Null

$stdinStream = $processo.StandardInput.BaseStream
$errosTarefa = $processo.StandardError.ReadToEndAsync()

$ultimaAtualizacao = Get-Date

$prefixo = New-Object byte[] 3
$bytesPrefixo = 0
while ($bytesPrefixo -lt 3) {
    $lidoPrefixo = $streamLeitura.Read($prefixo, $bytesPrefixo, 3 - $bytesPrefixo)
    if ($lidoPrefixo -eq 0) { break }
    $bytesPrefixo += $lidoPrefixo
}
$temBomUtf8 = (
    $bytesPrefixo -eq 3 -and
    $prefixo[0] -eq 0xEF -and
    $prefixo[1] -eq 0xBB -and
    $prefixo[2] -eq 0xBF
)

if (-not $temBomUtf8 -and $bytesPrefixo -gt 0) {
    $stdinStream.Write($prefixo, 0, $bytesPrefixo)
}
$bytesLidos += $bytesPrefixo

try {
    while ($true) {
        $lido = $streamLeitura.Read($buffer, 0, $bufferSize)
        if ($lido -eq 0) { break }

        $stdinStream.Write($buffer, 0, $lido)
        $bytesLidos += $lido

        # Atualiza progresso a cada segundo
        $agora = Get-Date
        if (($agora - $ultimaAtualizacao).TotalSeconds -ge 1) {
            $ultimaAtualizacao = $agora
            $pct = [math]::Round(($bytesLidos / $tamanhoTotal) * 100, 1)
            $decorrido = $agora - $inicio
            $velocidade = if ($decorrido.TotalSeconds -gt 0) { $bytesLidos / $decorrido.TotalSeconds } else { 0 }

            $restante = if ($velocidade -gt 0) {
                $bytesRestantes = $tamanhoTotal - $bytesLidos
                [TimeSpan]::FromSeconds($bytesRestantes / $velocidade)
            } else { [TimeSpan]::Zero }

            $status = "Lido: $(Formatar-Tamanho $bytesLidos) de $tamanhoFormatado" +
                      " | Velocidade: $(Formatar-Tamanho ([long]$velocidade))/s" +
                      " | Restante: $(Formatar-Duracao $restante)"

            Write-Progress `
                -Activity "Importando $($arquivoInfo.Name)" `
                -Status $status `
                -PercentComplete $pct
        }
    }
} finally {
    $stdinStream.Close()
    $streamLeitura.Close()
}

$processo.WaitForExit()
Write-Progress -Activity "Importando" -Completed

$fim = Get-Date
$duracao = $fim - $inicio

$erros = $errosTarefa.Result

if ($processo.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "[ERRO] A importação falhou (código $($processo.ExitCode))." -ForegroundColor Red
    Write-Host "Detalhes: $erros" -ForegroundColor Gray
    Log "ERRO na importação (código $($processo.ExitCode)): $erros"
    exit 1
}

if ($erros -and $erros.Trim() -ne "") {
    Write-Host ""
    Write-Host "[AVISO] Mensagens do MySQL durante a importação:" -ForegroundColor Yellow
    Write-Host $erros -ForegroundColor Gray
    Log "Avisos MySQL: $erros"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Importação concluída com sucesso!" -ForegroundColor Green
Write-Host "  Duração total: $(Formatar-Duracao $duracao)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Log "Importação concluída com sucesso"
Log "Duração: $(Formatar-Duracao $duracao)"
Log "Total importado: $(Formatar-Tamanho $bytesLidos)"
