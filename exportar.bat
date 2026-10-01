@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   Exportador de Banco de Dados - SaidJur (migracao)
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

REM Verifica se mysqldump esta no PATH
mysqldump --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] O comando "mysqldump" nao foi encontrado.
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

echo.
echo Iniciando exportacao via PowerShell...
echo (Isso pode levar varias horas para bancos grandes)
echo.

if "%~1"=="" (
    PowerShell -ExecutionPolicy Bypass -File scripts\exportar.ps1
) else (
    PowerShell -ExecutionPolicy Bypass -File scripts\exportar.ps1 -ArquivoSaida "%~1"
)

if errorlevel 1 (
    echo.
    echo [ERRO] A exportacao falhou. Verifique o arquivo de log em logs\
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Exportacao concluida! Consulte MIGRACAO_SERVIDOR_DEDICADO.md
echo   para transferir e importar no computador dedicado.
echo ============================================================
echo.
pause
