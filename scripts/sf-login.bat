@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo.
echo Salesforce org login
echo   Username: gregory_wallace@trimble.com
echo   Org:      https://crmtransportation.lightning.force.com/
echo.

where sf >nul 2>&1
if errorlevel 1 (
  where npm.cmd >nul 2>&1
  if errorlevel 1 (
    echo Salesforce CLI and npm.cmd were not found.
    echo Open Command Prompt, not PowerShell, then install with:
    echo   npm.cmd install --global @salesforce/cli
    pause
    exit /b 1
  )
  echo Installing Salesforce CLI with npm.cmd ...
  npm.cmd install --global @salesforce/cli
  if errorlevel 1 (
    echo CLI install failed.
    pause
    exit /b 1
  )
)

echo Authentication is required.
echo A browser window will open. Sign in as gregory_wallace@trimble.com
echo and allow access, then return to this window.
echo.

sf org login web --instance-url https://crmtransportation.my.salesforce.com --alias crmtransportation --set-default
if errorlevel 1 (
  echo Login failed or was cancelled.
  pause
  exit /b 1
)

sf config set target-org crmtransportation
echo.
echo Authorized orgs:
sf org list
echo.
echo Salesforce DX MCP can now use alias crmtransportation.
pause
exit /b 0
