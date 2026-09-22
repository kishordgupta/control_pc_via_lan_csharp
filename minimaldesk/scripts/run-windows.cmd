@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run scripts\install-windows.cmd first.
  exit /b 1
)
start "MinimalDesk" ".venv\Scripts\pythonw.exe" -m minimaldesk
