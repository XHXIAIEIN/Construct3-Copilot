# Asks for the SiliconFlow API key, writes it into .env as SILICONFLOW_API_KEY, then checks it against the
# account endpoint and prints the balance. The key is typed hidden and never printed or logged.
# Run: right-click > Run with PowerShell, or `pwsh -File set-siliconflow-key.ps1`
$ErrorActionPreference = 'Stop'
$envFile = Join-Path (Split-Path $PSScriptRoot) '.env'
$secure = Read-Host 'SiliconFlow API key (sk-...)' -AsSecureString
$key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)).Trim()
if (-not $key.StartsWith('sk-')) { Write-Host 'Not a key (it starts with sk-). Nothing written.'; Read-Host 'Enter to close'; exit 1 }
$lines = @(Get-Content $envFile -Encoding utf8 | Where-Object { $_ -notmatch '^SILICONFLOW_API_KEY=' })
$lines += "SILICONFLOW_API_KEY=$key"
[IO.File]::WriteAllLines($envFile, [string[]]$lines, [Text.UTF8Encoding]::new($false))  # no BOM, also in Windows PowerShell 5.1
try {
    $info = Invoke-RestMethod 'https://api.siliconflow.cn/v1/user/info' -Headers @{ Authorization = "Bearer $key" } -TimeoutSec 20
    Write-Host "Key works. Balance: $($info.data.totalBalance) CNY"
} catch {
    Write-Host "Key written, but the check failed: $($_.Exception.Message)"
}
Read-Host 'Enter to close'
