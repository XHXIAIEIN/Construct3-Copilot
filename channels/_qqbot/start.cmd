@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
if not exist ".venv\Scripts\python.exe" (
  echo Please create .venv and install the dependencies listed in README.md.
  pause
  exit /b 1
)
powershell.exe -NoProfile -WindowStyle Hidden -File "%~dp0scripts\open-panel.ps1"
