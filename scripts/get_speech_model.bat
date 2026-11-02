@echo off
setlocal
cd /d "%~dp0.."
echo Downloading Klicky's local speech model (about 145 MB, one time only).
.venv\Scripts\python.exe scripts\get_speech_model.py %*
pause
