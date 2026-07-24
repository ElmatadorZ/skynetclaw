@echo off
title SkynetClaw
color 0B

echo.
echo  ==========================================
echo   SkynetClaw v1.0 - Starting...
echo  ==========================================
echo.

:: Start Ollama in background (if not already running)
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %errorlevel% neq 0 (
    echo [INFO] Starting Ollama...
    start /min "" ollama serve
    timeout /t 3 /nobreak >nul
)

:: Start ElmatadorZ GPU execution runtime (llama.cpp) if not already running
tasklist /FI "IMAGENAME eq llama-server.exe" 2>NUL | find /I "llama-server.exe" >NUL
if %errorlevel% neq 0 (
    echo [INFO] Starting ElmatadorZ GPU runtime ^(Qwen2.5-14B^)...
    start /min "ElmatadorZ" powershell -ExecutionPolicy Bypass -File "%~dp0launch_execution_runtime.ps1"
    echo [INFO] Waiting for GPU model to load...
    timeout /t 30 /nobreak >nul
)

:: Start Stealth Browser bridge (external, isolated Python 3.13 venv) if installed.
:: Runs the undetectable-Chrome MCP tools behind a localhost shim on :8781 so the
:: House can reach them without pulling nodriver/Chrome into its own environment.
:: Degrades cleanly: if not installed, the stealth_* tools simply report offline.
if not exist "%~dp0..\stealth-browser-mcp-master\start_bridge.bat" goto stealth_done
netstat -ano | find ":8781" >NUL
if %errorlevel% equ 0 (
    echo [INFO] Stealth Browser bridge already running ^(:8781^)
    goto stealth_done
)
echo [INFO] Starting Stealth Browser bridge ^(:8781^)...
start "Stealth Bridge" /min cmd /c ""%~dp0..\stealth-browser-mcp-master\start_bridge.bat""
:stealth_done

:: Start backend
echo [INFO] Starting backend on http://localhost:8766 ...
start "SkynetClaw Backend" /min cmd /c "cd /d "%~dp0backend" && python main.py"

:: Start execution watchdog — keeps the GPU model (:8080) alive + warm (it has
:: died repeatedly; the watchdog auto-relaunches it and warms the first call)
echo [INFO] Starting execution watchdog...
start "Exec Watchdog" /min cmd /c "cd /d "%~dp0" && python execution_watchdog.py"

:: Wait for backend to start
echo [INFO] Waiting for backend...
timeout /t 3 /nobreak >nul

:: Open the UI
echo [INFO] Opening SkynetClaw UI...
start "" "%~dp0index.html"

echo.
echo  [OK] SkynetClaw is running!
echo  Backend : http://localhost:8766
echo  UI      : index.html (opened in browser)
echo.
echo  Press any key to stop the backend...
pause >nul

:: Cleanup
taskkill /FI "WINDOWTITLE eq SkynetClaw Backend" /F >nul 2>&1
echo [INFO] Backend stopped.
