@echo off
title SkynetClaw - Force Kill + Restart
color 0B
echo.
echo  ========================================
echo   Force Kill Ports 8765 + 8766 + Restart
echo  ========================================
echo.

echo [1] Force killing processes on ports 8765 and 8766...
powershell -NoProfile -Command ^
  "$ports = @(8765, 8766);" ^
  "foreach ($p in $ports) {" ^
  "  $procs = netstat -ano | Select-String (':' + $p + '\s') |" ^
  "    ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique;" ^
  "  foreach ($pid in $procs) {" ^
  "    if ($pid -match '^\d+$' -and $pid -ne '0') {" ^
  "      Write-Host ('   Port ' + $p + ' -> killing PID ' + $pid);" ^
  "      try { Stop-Process -Id ([int]$pid) -Force -ErrorAction Stop } catch { }" ^
  "    }" ^
  "  }" ^
  "  if (-not $procs) { Write-Host ('   Port ' + $p + ': free') }" ^
  "}"
echo.

echo [2] Waiting 3 seconds for ports to release...
timeout /t 3 /nobreak >nul
echo.

echo [3] Starting SkynetClaw Backend (Masterpiece + OpenClaw Tier 1+2)...
echo.
cd /d "%~dp0backend"
python main.py

echo.
echo  ====== Backend stopped ======
pause
