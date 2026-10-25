@echo off
setlocal
cd /d "%~dp0.."
if exist "dist\Klicky\Klicky.exe" (
    start "" "dist\Klicky\Klicky.exe" %*
    exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
    echo Please run scripts\setup.bat first.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "launch.pyw" %*
