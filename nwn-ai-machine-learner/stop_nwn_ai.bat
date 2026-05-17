@echo off
setlocal

set "PORT=5000"

echo ============================================================
echo  Stop NWN-AI Machine Learner
echo ============================================================
echo.
echo Looking for a local NWN-AI server on port %PORT%...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if (-not $conns) { Write-Host 'No NWN-AI server is listening on port %PORT%.'; exit 0 }; foreach ($c in $conns) { $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue; if ($proc) { Write-Host ('Stopping PID ' + $c.OwningProcess + ' (' + $proc.ProcessName + ')...'); Stop-Process -Id $c.OwningProcess -Force } }"

if errorlevel 1 (
    echo.
    echo ERROR: Stop command failed.
    pause
    exit /b 1
)

echo.
echo Done.
pause
