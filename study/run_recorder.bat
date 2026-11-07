@echo off
rem The study recorder: F8 starts and ends each task. Files go to study\recordings.
cd /d "%~dp0.."
start "" .venv\Scripts\pythonw.exe study\recorder.py
