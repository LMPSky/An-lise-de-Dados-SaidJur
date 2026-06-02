@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   Iniciando Visualizador de Dados SaidJur
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

REM Verifica se config.yaml existe
if not exist "config.yaml" (
    echo [ERRO] Arquivo config.yaml nao encontrado.
    echo Execute primeiro o instalar.bat e configure suas credenciais.
    echo.
    pause
    exit /b 1
)

echo Ativando ambiente Python...
call venv\Scripts\activate.bat

echo Iniciando servidor...
echo.
echo O visualizador sera aberto no seu navegador em instantes.
echo Para encerrar, feche esta janela ou pressione Ctrl+C.
echo.

REM Abre o navegador após 2 segundos
start /b cmd /c "timeout /t 2 >nul && start http://127.0.0.1:8000"

REM Inicia o servidor
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000

pause
