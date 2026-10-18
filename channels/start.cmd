@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%"
if not exist ".venv\Scripts\python.exe" (
  echo Please create .venv in the Copilot checkout and install channels\requirements.txt, see channels\README.md.
  pause
  exit /b 1
)
powershell.exe -NoProfile -WindowStyle Hidden -File "%~dp0scripts\open-panel.ps1"
