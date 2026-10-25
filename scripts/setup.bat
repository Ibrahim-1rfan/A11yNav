@echo off
setlocal
cd /d "%~dp0.."
echo Setting up Klicky. This downloads application packages, not AI model weights.
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto fail
echo Setup complete. Double-click scripts\run.bat to open Klicky.
pause
exit /b 0
:fail
echo Setup failed. Install Python 3.10 or later from python.org and check your internet connection.
pause
exit /b 1
