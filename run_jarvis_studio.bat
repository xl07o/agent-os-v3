@echo off
title JARVIS Studio
cd /d "%~dp0"
echo Starting JARVIS Studio - a real executor, not marketing talk.
set PYTHONIOENCODING=utf-8
python -m jarvis_v2.app.server %*
if errorlevel 1 pause