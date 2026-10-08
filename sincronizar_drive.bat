@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   Sincronizar arquitetura do projeto com o Google Drive
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sincronizar_arquitetura_drive.ps1"

echo.
pause
