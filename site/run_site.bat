@echo off
title Agent OS - Control Center
cd /d "%~dp0"

echo ============================================================
echo   Starting Agent OS Control Center ...
echo ============================================================

set "PY=rem_python"

rem ---- Locate Python launcher ----
if exist "%LOCALAPPDATA%\Programs\Python" (
  for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do set "PY=%%d\python.exe"
)
if "%PY%"=="rem_python" where py >nul 2>nul && set "PY=py"
if "%PY%"=="rem_python" where python >nul 2>nul && set "PY=python"

if "%PY%"=="rem_python" (
  echo [ERROR] Python not found. Install Python 3.11+ from python.org
  pause
  exit /b 1
)

rem ---- If bridge already running, just open the browser ----
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8787);$c.Close();'UP'}catch{'DOWN'}"`) do set "STATUS=%%i"
if /i "%STATUS%"=="UP" (
  echo Bridge is already running. Opening your dashboard...
  start "" http://127.0.0.1:8787
  echo.
  echo You can close this window.
  timeout /t 2 >nul
  exit /b 0
)

rem ---- Open the browser after 2 seconds (give server time to boot) ----
start "" /b cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8787"

rem ---- Run the bridge (keep this window open) ----
%PY% agent_bridge.py

pause