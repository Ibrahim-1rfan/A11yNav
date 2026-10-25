@echo off
setlocal
cd /d "%~dp0.."
.venv\Scripts\python.exe -m PyInstaller --noconfirm Klicky.spec
if errorlevel 1 exit /b 1
echo Built dist\Klicky\Klicky.exe. Keep the whole Klicky folder together.
