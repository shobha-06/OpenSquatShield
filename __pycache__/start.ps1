$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

$port = 8000
$existing = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique

if ($existing) {
    Write-Host "Port $port is in use — stopping old server (PID: $($existing -join ', '))..."
    $existing | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

Write-Host "Starting openSquat Web at http://127.0.0.1:$port"
python server.py
