@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   Importador de Arquivo SQL - SaidJur
echo ============================================================
echo.

REM Verifica se o ambiente virtual existe
if not exist "venv\" (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo Execute primeiro o instalar.bat
    echo.
    pause
    exit /b 1
)

REM Verifica se mysql está no PATH
mysql --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] O comando "mysql" nao foi encontrado.
    echo.
    echo Para corrigir, adicione o MySQL ao PATH do Windows:
    echo   1. Abra "Editar variaveis de ambiente do sistema"
    echo   2. Clique em "Variaveis de Ambiente..."
    echo   3. Em "Variaveis do sistema", selecione "Path"
    echo   4. Clique em "Editar" e depois "Novo"
    echo   5. Adicione: C:\Program Files\MySQL\MySQL Server 8.0\bin
    echo   6. Clique OK em todas as janelas
    echo   7. Feche e reabra este cmd
    echo.
    echo Consulte o arquivo INSTALL_WINDOWS.md para mais detalhes.
    echo.
    pause
    exit /b 1
)

REM Verifica se o argumento foi passado
if "%~1"=="" (
    echo Uso: importar.bat caminho\do\arquivo.sql
    echo.
    echo Ou coloque o arquivo .sql na pasta "dados\" e execute:
    echo   importar.bat dados\seu_arquivo.sql
    echo.
    set /p ARQUIVO_SQL="Digite o caminho do arquivo .sql: "
) else (
    set ARQUIVO_SQL=%~1
)

if "%ARQUIVO_SQL%"=="" (
    echo [ERRO] Nenhum arquivo informado.
    pause
    exit /b 1
)

if not exist "%ARQUIVO_SQL%" (
    echo [ERRO] Arquivo nao encontrado: %ARQUIVO_SQL%
    pause
    exit /b 1
)

echo.
echo Iniciando importacao via PowerShell...
echo (Isso pode levar varias horas para arquivos grandes)
echo.

PowerShell -ExecutionPolicy Bypass -File scripts\importar.ps1 -ArquivoSQL "%ARQUIVO_SQL%"

if errorlevel 1 (
    echo.
    echo [ERRO] A importacao falhou. Verifique o arquivo de log em logs\
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Importacao concluida! Agora execute iniciar.bat
echo ============================================================
echo.
pause
