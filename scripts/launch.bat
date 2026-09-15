@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python 3 from https://www.python.org and reopen this window.
  pause
  exit /b 1
)

python scripts\launch.py %*
exit /b %ERRORLEVEL%
