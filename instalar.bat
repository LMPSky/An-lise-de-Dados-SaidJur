@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   Instalador do Visualizador de Dados SaidJur
echo ============================================================
echo.

REM Verifica se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Por favor, instale o Python 3.11 ou superior em:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Durante a instalacao, marque a opcao
    echo "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.

REM Cria ambiente virtual se não existir
if not exist "venv\" (
    echo Criando ambiente virtual Python...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
) else (
    echo [OK] Ambiente virtual ja existe.
)

echo.
echo Instalando dependencias Python...
call venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

echo.
REM Copia config.example.yaml para config.yaml se não existir
if not exist "config.yaml" (
    copy config.example.yaml config.yaml >nul
    echo [OK] Arquivo de configuracao criado: config.yaml
    echo.
    echo IMPORTANTE: Abra o arquivo config.yaml com o Bloco de
    echo Notas e coloque a senha do seu MySQL no campo "senha:".
) else (
    echo [OK] config.yaml ja existe.
)

echo.
echo ============================================================
echo   Instalacao concluida com sucesso!
echo ============================================================
echo.
echo Proximos passos:
echo   1. Edite o arquivo config.yaml com a senha do seu MySQL
echo   2. Copie o arquivo .sql para a pasta "dados\"
echo   3. Clique duas vezes em importar.bat
echo   4. Apos a importacao, clique em iniciar.bat
echo.
pause
