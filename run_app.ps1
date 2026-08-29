param(
    [ValidateSet("start", "restart", "stop")]
    [string]$Action = "start",
    [int]$Port = 8000
)

function Stop-AppOnPort {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        if ($connection.OwningProcess -gt 0) {
            Stop-Process -Id $connection.OwningProcess -Force
            Write-Host "Stopped process $($connection.OwningProcess) on port $Port."
        }
    }
}

if ($Action -eq "stop" -or $Action -eq "restart") {
    Stop-AppOnPort
}

if ($Action -ne "stop") {
    python -m uvicorn app.main:app --host 0.0.0.0 --port $Port
}
