<#
.SYNOPSIS
    Exporta (mysqldump) o banco de dados local para um arquivo .sql, para
    migração/transferência a outro computador (ex: servidor dedicado).

.DESCRIPTION
    Lê as credenciais do config.yaml e executa mysqldump com flags seguras
    para bancos grandes (--single-transaction, --quick, --routines,
    --triggers, --events), mostrando o tamanho do arquivo gerado e o tempo
    decorrido enquanto a exportação roda em segundo plano. O arquivo gerado
    é compatível com o importador existente (importar.bat / importar.ps1).

.PARAMETER ArquivoSaida
    Caminho do arquivo .sql de saída. Padrão: dados\saidjur_export_AAAAMMDD_HHmmss.sql

.EXAMPLE
    .\exportar.ps1
    .\exportar.ps1 -ArquivoSaida "D:\backups\saidjur.sql"
#>

param(
    [string]$ArquivoSaida,
    [string]$ConfigPath
)

# Configurações de encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ── Funções auxiliares (mesma lógica de importar.ps1, mantidas em cópia aqui
#    para que este script continue funcionando de forma independente) ───────

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

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Exportador SQL - SaidJur (para migração de servidor)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Lê configuração
$config = Ler-Config -ConfigPath $ConfigPath
$dbHost    = $config["banco"]["host"]
$dbPorta   = $config["banco"]["porta"]
$dbUsuario = $config["banco"]["usuario"]
$dbSenha   = $config["banco"]["senha"]
$dbNome    = $config["banco"]["nome"]

if ([string]::IsNullOrWhiteSpace($ArquivoSaida)) {
    $dadosDir = Join-Path $PSScriptRoot "..\dados"
    if (-not (Test-Path $dadosDir)) { New-Item -ItemType Directory -Path $dadosDir | Out-Null }
    $dataHora = Get-Date -Format "yyyyMMdd_HHmmss"
    $ArquivoSaida = Join-Path $dadosDir "saidjur_export_$dataHora.sql"
}

Write-Host "Banco de origem : $dbNome em ${dbHost}:${dbPorta}" -ForegroundColor White
Write-Host "Arquivo de saída : $ArquivoSaida" -ForegroundColor White
Write-Host ""

Write-Host "⚠️  ATENÇÃO" -ForegroundColor Yellow
Write-Host "──────────────────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host "Esta operação pode levar de 1 a 4 horas para um banco de" -ForegroundColor Yellow
Write-Host "~50 GB e exige espaço livre em disco equivalente ao banco." -ForegroundColor Yellow
Write-Host "NÃO use o visualizador durante a exportação." -ForegroundColor Yellow
Write-Host "NÃO feche esta janela durante a exportação." -ForegroundColor Yellow
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
$dataHoraLog = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "exportacao_$dataHoraLog.log"

function Log {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp $msg" | Out-File -FilePath $logFile -Encoding UTF8 -Append
}

Log "Início da exportação"
Log "Banco: $dbNome em ${dbHost}:${dbPorta}"
Log "Arquivo de saída: $ArquivoSaida"

Write-Host ""
Write-Host "Log sendo gravado em: $logFile" -ForegroundColor Gray
Write-Host ""

# Verifica mysqldump no PATH
try {
    $mysqldumpVersion = mysqldump --version 2>&1
    Write-Host "[OK] mysqldump encontrado: $mysqldumpVersion" -ForegroundColor Green
    Log "mysqldump: $mysqldumpVersion"
} catch {
    Write-Host "[ERRO] Comando 'mysqldump' não encontrado no PATH." -ForegroundColor Red
    Write-Host "Consulte INSTALL_WINDOWS.md para adicionar ao PATH." -ForegroundColor Yellow
    Log "ERRO: mysqldump não encontrado no PATH"
    exit 1
}

# Monta argumentos do mysqldump.
# --single-transaction: snapshot consistente de tabelas InnoDB sem travar
#   leituras/escritas durante o dump (evita downtime do banco de origem).
# --quick: busca linha a linha em vez de carregar a tabela inteira em
#   memória antes de escrever (essencial para tabelas com dezenas de
#   milhões de linhas).
# --routines/--triggers/--events: inclui procedures, triggers e eventos,
#   não só as tabelas.
$mysqldumpArgs = @(
    "-h", $dbHost
    "-P", $dbPorta
    "-u", $dbUsuario
)
if ($dbSenha -ne "") { $mysqldumpArgs += "-p$dbSenha" }
$mysqldumpArgs += @(
    "--default-character-set=utf8mb4"
    "--single-transaction"
    "--quick"
    "--routines"
    "--triggers"
    "--events"
    $dbNome
)

Write-Host ""
Write-Host "Iniciando exportação..." -ForegroundColor Cyan
Write-Host "(Isso pode levar de 1 a 4 horas para um banco de ~50 GB)" -ForegroundColor Gray
Write-Host ""

$inicio = Get-Date

$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "mysqldump"
$processInfo.Arguments = $mysqldumpArgs -join " "
$processInfo.UseShellExecute = $false
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true

$processo = New-Object System.Diagnostics.Process
$processo.StartInfo = $processInfo
$processo.Start() | Out-Null

$streamSaida = [System.IO.File]::Create($ArquivoSaida)
$stdoutStream = $processo.StandardOutput.BaseStream
$errosTarefa = $processo.StandardError.ReadToEndAsync()

$bufferSize = 64KB
$buffer = New-Object byte[] $bufferSize
$bytesEscritos = 0
$ultimaAtualizacao = Get-Date

try {
    while ($true) {
        $lido = $stdoutStream.Read($buffer, 0, $bufferSize)
        if ($lido -eq 0) { break }

        $streamSaida.Write($buffer, 0, $lido)
        $bytesEscritos += $lido

        $agora = Get-Date
        if (($agora - $ultimaAtualizacao).TotalSeconds -ge 1) {
            $ultimaAtualizacao = $agora
            $decorrido = $agora - $inicio
            $velocidade = if ($decorrido.TotalSeconds -gt 0) { $bytesEscritos / $decorrido.TotalSeconds } else { 0 }

            $status = "Gravado: $(Formatar-Tamanho $bytesEscritos)" +
                      " | Velocidade: $(Formatar-Tamanho ([long]$velocidade))/s" +
                      " | Decorrido: $(Formatar-Duracao $decorrido)"

            Write-Progress -Activity "Exportando $dbNome" -Status $status
        }
    }
} finally {
    $streamSaida.Close()
}

$processo.WaitForExit()
Write-Progress -Activity "Exportando" -Completed

$fim = Get-Date
$duracao = $fim - $inicio
$erros = $errosTarefa.Result

if ($processo.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "[ERRO] A exportação falhou (código $($processo.ExitCode))." -ForegroundColor Red
    Write-Host "Detalhes: $erros" -ForegroundColor Gray
    Log "ERRO na exportação (código $($processo.ExitCode)): $erros"
    Remove-Item -Path $ArquivoSaida -ErrorAction SilentlyContinue
    exit 1
}

if ($erros -and $erros.Trim() -ne "") {
    Write-Host ""
    Write-Host "[AVISO] Mensagens do mysqldump durante a exportação:" -ForegroundColor Yellow
    Write-Host $erros -ForegroundColor Gray
    Log "Avisos mysqldump: $erros"
}

$tamanhoFinal = (Get-Item $ArquivoSaida).Length

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Exportação concluída com sucesso!" -ForegroundColor Green
Write-Host "  Arquivo : $ArquivoSaida" -ForegroundColor Green
Write-Host "  Tamanho : $(Formatar-Tamanho $tamanhoFinal)" -ForegroundColor Green
Write-Host "  Duração : $(Formatar-Duracao $duracao)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Próximo passo: transfira este arquivo para o computador" -ForegroundColor Cyan
Write-Host "dedicado e importe-o lá com importar.bat." -ForegroundColor Cyan
Write-Host "Consulte MIGRACAO_SERVIDOR_DEDICADO.md para o passo a passo." -ForegroundColor Cyan
Write-Host ""

Log "Exportação concluída com sucesso"
Log "Duração: $(Formatar-Duracao $duracao)"
Log "Total exportado: $(Formatar-Tamanho $tamanhoFinal)"
