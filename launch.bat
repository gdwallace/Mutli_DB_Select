@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0scripts\launch.bat" %*
exit /b %ERRORLEVEL%
