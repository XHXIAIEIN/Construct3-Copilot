@echo off
chcp 65001 >nul
cd /d "%~dp0"

set LLM_PROVIDER=ollama
set LLM_MODEL=qwen3.5:9b

echo ============================================
echo   Construct 3 Copilot Core  :8767
echo   LLM: %LLM_PROVIDER% / %LLM_MODEL%
echo   Ctrl+C to stop
echo ============================================
echo.

python -c "import uvicorn; from src.api import app; uvicorn.run(app, host='0.0.0.0', port=8767)"

pause
