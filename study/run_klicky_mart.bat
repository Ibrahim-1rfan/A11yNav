@echo off
rem Start the Klicky Mart study shop on this PC and open it in the browser. Close this window to stop it.
cd /d "%~dp0.."
.venv\Scripts\python.exe study\server.py
