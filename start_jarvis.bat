@echo off
chcp 65001 >nul
title JARVIS — موظف الليل
cd /d "%~dp0"

echo.
echo  ========================================
echo    JARVIS — موظف الليل v3
echo  ========================================
echo.

:: تشغيل Ollama تلقائياً لو مش شغال
ollama list >nul 2>&1
if errorlevel 1 (
    echo  تشغيل Ollama...
    start /B ollama serve
    timeout /t 3 /nobreak >nul
)

:: تشغيل JARVIS
set PYTHONUTF8=1
python jarvis.py

pause
