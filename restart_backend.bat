@echo off
title SkynetClaw — Start Backend (port 8766)
color 0B
echo.
echo  ========================================
echo   SkynetClaw Backend — port 8766
echo  ========================================
echo.
cd /d "%~dp0backend"
python main.py
echo.
echo  ====== Backend stopped ======
pause
