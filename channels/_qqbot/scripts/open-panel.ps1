# Open this checkout's panel and capture background startup errors.
$ErrorActionPreference = 'Stop'
$panelHome = Split-Path -Parent $PSScriptRoot
$panelPython = Join-Path $panelHome '.venv\Scripts\python.exe'
$panelLogs = Join-Path $panelHome 'var\logs\models'
New-Item -ItemType Directory -Path $panelLogs -Force | Out-Null
$panelUrl = 'http://127.0.0.1:8767'
try {
    $existingPanel = Invoke-RestMethod -Uri "$panelUrl/api/health" -TimeoutSec 2
    if ($existingPanel.app -eq 'qqbot-model-manager' -and $existingPanel.home -eq $panelHome) {
        Start-Process -FilePath $panelUrl
        return
    }
} catch { }
$env:PYTHONPATH = Join-Path $panelHome 'src'
$env:PYTHONUTF8 = '1'
Start-Process -FilePath $panelPython -ArgumentList '-u', '-m', 'qqbot.model_manager', '--open' `
    -WorkingDirectory $panelHome -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $panelLogs 'panel.stdout.log') `
    -RedirectStandardError (Join-Path $panelLogs 'panel.stderr.log')
