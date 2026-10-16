@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Please create .venv and install the dependencies listed in README.md.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m qqbot.model_manager --open
