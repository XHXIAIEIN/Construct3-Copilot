# Start or stop this checkout's QQ channel and grader.
param([switch]$Stop, [switch]$Ollama, [switch]$Grader)

$botRoot = Split-Path -Parent $PSScriptRoot  # channels/: .env and var/
$repo = Split-Path -Parent $botRoot  # the Copilot checkout: .venv/
$botPython = Join-Path $repo '.venv\Scripts\python.exe'
$env:PYTHONPATH = $repo
# the data folder as the channel itself resolves it (channels/settings.py)
$botData = & $botPython -c 'from channels import settings as s; print(s.data_dir(s.load()))'
if ($LASTEXITCODE -ne 0 -or -not $botData) { throw 'The data folder could not be read. Check .venv and channels/.env.' }

# Identify this checkout's launchers before stopping their Python children.
$processes = @(Get-CimInstance Win32_Process)
$launchers = @($processes | Where-Object {
    $_.ExecutablePath -eq $botPython -and $_.CommandLine -notmatch '--cli' -and
    $_.CommandLine -match '-m\s+channels\.(qq|grader)\b'
})
$ownedIds = @($launchers | ForEach-Object { $_.ProcessId })
$processes | Where-Object { $_.ParentProcessId -in $ownedIds -and $_.Name -eq 'python.exe' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$launchers | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if ($Stop) { return }

if ($Ollama) {
    Push-Location $repo
    try {
        & $botPython -m channels.panel --start-ollama
        if ($LASTEXITCODE -ne 0) { throw 'Ollama could not start. Open the model panel to check its settings.' }
    } finally { Pop-Location }
}
$services = @('qq')
if ($Grader) { $services += 'grader' }
foreach ($serviceName in $services) {
    $logName = if ($serviceName -eq "qq") { "bot" } else { "grader" }
    $logDirectory = Join-Path $botData "logs\$logName"
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    Start-Process -FilePath $botPython -ArgumentList '-u', '-m', "channels.$serviceName" -WorkingDirectory $repo -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDirectory 'service.stdout.log') `
        -RedirectStandardError (Join-Path $logDirectory 'service.stderr.log')
}
