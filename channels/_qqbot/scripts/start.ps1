# Start or stop this checkout's QQ bot and grader.
param([switch]$Stop, [switch]$Ollama, [switch]$Grader)

$botRoot = Split-Path -Parent $PSScriptRoot
$botPython = Join-Path $botRoot '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $botRoot 'src'
$botData = Join-Path $botRoot 'var'
$dataLine = Select-String -Path (Join-Path $botRoot '.env') -Pattern '^C3BOT_DATA=(.+)$' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($dataLine) { $botData = $dataLine.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'") }

# Identify this checkout's launchers before stopping their Python children.
$processes = @(Get-CimInstance Win32_Process)
$launchers = @($processes | Where-Object {
    $_.ExecutablePath -eq $botPython -and $_.CommandLine -notmatch '--cli' -and
    $_.CommandLine -match '(-m\s+qqbot\.(qq|grader)\b|\s(bot|grader)\.py\b)'
})
$ownedIds = @($launchers | ForEach-Object { $_.ProcessId })
$processes | Where-Object { $_.ParentProcessId -in $ownedIds -and $_.Name -eq 'python.exe' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$launchers | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if ($Stop) { return }

if ($Ollama) {
    Push-Location $botRoot
    try {
        & $botPython -m qqbot.model_manager --start-ollama
        if ($LASTEXITCODE -ne 0) { throw 'Ollama could not start. Open the model panel to check its settings.' }
    } finally { Pop-Location }
}
$services = @('qq')
if ($Grader) { $services += 'grader' }
foreach ($serviceName in $services) {
    $logName = if ($serviceName -eq "qq") { "bot" } else { "grader" }
    $logDirectory = Join-Path $botData "logs\$logName"
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    Start-Process -FilePath $botPython -ArgumentList '-u', '-m', "qqbot.$serviceName" -WorkingDirectory $botRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDirectory 'service.stdout.log') `
        -RedirectStandardError (Join-Path $logDirectory 'service.stderr.log')
}
