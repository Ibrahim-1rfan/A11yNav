@echo off
rem Checks the Klicky install and keys. Keys are never shown.
cd /d "%~dp0.."
.venv\Scripts\python.exe scripts\check_setup.py
pause
