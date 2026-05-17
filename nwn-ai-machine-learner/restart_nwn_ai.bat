@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  Restart NWN-AI Machine Learner
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue; foreach ($c in $conns) { $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue; if ($proc) { Write-Host ('Stopping PID ' + $c.OwningProcess + ' (' + $proc.ProcessName + ')...'); Stop-Process -Id $c.OwningProcess -Force } }"

echo.
echo Starting NWN-AI again...
call "%~dp0start_nwn_ai.bat"
