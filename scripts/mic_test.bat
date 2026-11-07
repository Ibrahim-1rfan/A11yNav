@echo off
rem Checks the microphone and the speech models for Klicky voice questions. Nothing is saved.
cd /d "%~dp0.."
.venv\Scripts\python.exe scripts\mic_test.py
pause
