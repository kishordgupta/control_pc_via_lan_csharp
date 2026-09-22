@echo off
setlocal
cd /d "%~dp0\.."
py -3 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --no-deps -e .
if errorlevel 1 exit /b 1
echo Installed. Run scripts\run-windows.cmd to start MinimalDesk.
