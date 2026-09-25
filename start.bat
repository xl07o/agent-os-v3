@echo off
REM موظف الليل - القائمة الرئيسية v3.0
REM SelfRunner Launcher - v2.0
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title SelfRunner
cls
echo ============================================
echo    SelfRunner v2.0 - Night Worker
echo    Multi-Mind Autonomous System
echo ============================================
echo.
echo 1.  Run Task
echo 2.  Interactive Agent Mode
echo 3.  Orchestrator (big task split)
echo 4.  Chat CLI (live conversation)
echo 5.  Show Brain Status
echo 6.  Dashboard
echo 7.  Nightly Schedule
echo 8.  Mastery Mission (3 hours)
echo 9.  Morning Summary
echo 10. System Check
echo 11. Mastery Engine (learn while you are away)
echo 12. Exit
echo.
set /p choice="Choose a number: "

if "%choice%"=="1" (
  set /p task="Enter your task: "
  set "task=!task:"=!"
  python selfrunner.py "!task!"
  pause
) else if "%choice%"=="2" (
  python selfrunner.py
) else if "%choice%"=="3" (
  set /p task="Enter the big task: "
  set "task=!task:"=!"
  python orchestrator.py "!task!"
  pause
) else if "%choice%"=="4" (
  python chat_cli.py
) else if "%choice%"=="5" (
  python selfrunner.py --status
  pause
) else if "%choice%"=="6" (
  python dashboard.py
  pause
) else if "%choice%"=="7" (
  set /p atime="Run time (HH:MM e.g. 02:00): "
  python schedule.py --time %atime%
  pause
) else if "%choice%"=="8" (
  python run_mission.py
  pause
) else if "%choice%"=="9" (
  python daily_summary.py
  pause
) else if "%choice%"=="10" (
  echo.
  echo [1/3] Checking Python...
  python --version
  echo.
  echo [2/3] Checking Ollama...
  python -c "import ollama_manager; print(ollama_manager.status_report())" 2>nul || echo   Ollama is not running - install from ollama.com
  echo.
  echo [3/3] Checking providers...
  python selfrunner.py --status
  pause
) else if "%choice%"=="11" (
  echo.
  echo 1- Run / 2- Status / 3- Report / 4- Stop / 5- Resume
  set /p mact="Choose: "
  if "!mact!"=="1" (
    python mastery.py run
  ) else if "!mact!"=="2" (
    python mastery.py status
  ) else if "!mact!"=="3" (
    python mastery.py report
  ) else if "!mact!"=="4" (
    python mastery.py stop
  ) else if "!mact!"=="5" (
    python mastery.py resume
  ) else (
    echo Invalid choice
  )
  pause
) else (
  exit
)