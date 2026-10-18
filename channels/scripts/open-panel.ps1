# Open the channels panel and capture background startup errors.
$ErrorActionPreference = 'Stop'
$panelHome = Split-Path -Parent $PSScriptRoot  # channels/
$repo = Split-Path -Parent $panelHome
$panelPython = Join-Path $repo '.venv\Scripts\python.exe'
$panelLogs = Join-Path $panelHome 'var\logs\models'
New-Item -ItemType Directory -Path $panelLogs -Force | Out-Null
$panelUrl = 'http://127.0.0.1:8767'
try {
    $existingPanel = Invoke-RestMethod -Uri "$panelUrl/api/health" -TimeoutSec 2
    if ($existingPanel.app -eq 'channels-panel' -and $existingPanel.home -eq $panelHome) {
        Start-Process -FilePath $panelUrl
        return
    }
} catch { }
$env:PYTHONPATH = $repo
$env:PYTHONUTF8 = '1'
Start-Process -FilePath $panelPython -ArgumentList '-u', '-m', 'channels.panel', '--open' `
    -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $panelLogs 'panel.stdout.log') `
    -RedirectStandardError (Join-Path $panelLogs 'panel.stderr.log')
