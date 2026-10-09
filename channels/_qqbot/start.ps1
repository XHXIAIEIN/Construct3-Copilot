# Restart the QQ bot and the silent grader as detached processes, logs in logs/bot/ and logs/grader/.
#   .\start.ps1            restart both
#   .\start.ps1 -Stop      stop both, start nothing
#   .\start.ps1 -Ollama    also start the Ollama server (logs in logs/ollama/) when it is not running;
#                          the bot answers nothing without it while .env points at the local model
# A session's background task dies at its time limit, so both run outside any session.
param([switch]$Stop, [switch]$Ollama)

$here = $PSScriptRoot
$logs = Join-Path $here 'logs'
'bot', 'grader' | ForEach-Object { New-Item -ItemType Directory -Force (Join-Path $logs $_) | Out-Null }

# The cmd launchers and their python children; `bot.py --cli` runs (tests) are left alone.
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match '(bot|grader)\.py' -and $_.CommandLine -notmatch '--cli' -and $_.Name -match '^(python|cmd)\.exe$' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if ($Stop) { return }

if ($Ollama -and -not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    $ol = Join-Path $logs 'ollama'
    New-Item -ItemType Directory -Force $ol | Out-Null
    # Start-Process cannot append, so the previous run's output is kept under the time it was replaced
    foreach ($f in 'ollama.out.log', 'ollama.err.log') {
        $old = Join-Path $ol $f
        if (Test-Path $old) { Move-Item $old (Join-Path $ol ("{0}.{1:yyyyMMdd-HHmm}" -f $f, (Get-Item $old).LastWriteTime)) }
    }
    Start-Process (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe') -ArgumentList 'serve' -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $ol 'ollama.out.log') -RedirectStandardError (Join-Path $ol 'ollama.err.log')
}
Start-Sleep -Seconds 2

foreach ($name in 'bot', 'grader') {
    Start-Process cmd -ArgumentList "/c .venv\Scripts\python.exe -u $name.py >> logs\$name\$name.log 2>&1" `
        -WorkingDirectory $here -WindowStyle Hidden
}
Start-Sleep -Seconds 8
Get-Content (Join-Path $logs 'bot\bot.log') -Tail 3
Get-Content (Join-Path $logs 'grader\grader.log') -Tail 2
