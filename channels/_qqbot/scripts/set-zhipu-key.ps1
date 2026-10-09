# Asks for the Zhipu (BigModel) API key, writes it into .env as ZHIPU_API_KEY, then checks it with one call to
# the free model glm-4.7-flash. The key is typed hidden and never printed or logged.
# Run: right-click > Run with PowerShell, or `pwsh -File set-zhipu-key.ps1`
$ErrorActionPreference = 'Stop'
$envFile = Join-Path (Split-Path $PSScriptRoot) '.env'
$secure = Read-Host 'Zhipu API key (from bigmodel.cn, API Keys page)' -AsSecureString
$key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)).Trim()
if ($key.Length -lt 20) { Write-Host 'Too short to be a key. Nothing written.'; Read-Host 'Enter to close'; exit 1 }
$lines = @(Get-Content $envFile -Encoding utf8 | Where-Object { $_ -notmatch '^ZHIPU_API_KEY=' })
$lines += "ZHIPU_API_KEY=$key"
[IO.File]::WriteAllLines($envFile, [string[]]$lines, [Text.UTF8Encoding]::new($false))  # no BOM, also in Windows PowerShell 5.1
$body = @{ model = 'glm-4.7-flash'; messages = @(@{ role = 'user'; content = 'Reply with OK.' });
           thinking = @{ type = 'disabled' }; max_tokens = 10 } | ConvertTo-Json -Depth 5
try {
    $r = Invoke-RestMethod 'https://open.bigmodel.cn/api/paas/v4/chat/completions' -Method Post -Body $body `
        -ContentType 'application/json; charset=utf-8' -Headers @{ Authorization = "Bearer $key" } -TimeoutSec 30
    Write-Host "Key works. glm-4.7-flash replied: $($r.choices[0].message.content)"
} catch {
    Write-Host "Key written, but the check failed: $($_.Exception.Message)"
}
Read-Host 'Enter to close'
