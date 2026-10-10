@echo off
chcp 65001 >nul
title Agent OS
cd /d "%~dp0"

echo.
echo  ========================================
echo    Agent OS v3
echo  ========================================
echo.

:: تشغيل Ollama تلقائياً لو مش شغال
ollama list >nul 2>&1
if errorlevel 1 (
    echo  تشغيل Ollama...
    start /B ollama serve
    timeout /t 3 /nobreak >nul
)

set PYTHONUTF8=1
python desktop_app.py

pause
