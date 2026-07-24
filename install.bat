@echo off
title SkynetClaw - Installer
color 0A

:: Set compatibility flag BEFORE anything else (fixes Python 3.14 + PyO3 issue)
set PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1

echo.
echo  ==========================================
echo   SkynetClaw - Installation
echo  ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from python.org
    pause & exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% found

:: Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install packages (flexible versions, works on Python 3.10-3.14)
echo [INFO] Installing dependencies...
pip install --upgrade ^
    "fastapi>=0.115.0" ^
    "uvicorn>=0.30.6" ^
    "httpx>=0.27.2" ^
    "pydantic>=2.10.0" ^
    "python-multipart>=0.0.9"

if %errorlevel% neq 0 (
    echo [ERROR] Installation failed.
    echo         Try: Run as Administrator, or open CMD and run manually:
    echo         set PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
    echo         pip install fastapi uvicorn httpx "pydantic>=2.10.0" python-multipart
    pause & exit /b 1
)

echo.
echo [OK] All packages installed successfully!
echo.

:: Check Ollama
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama not found.
    echo           1. Download: https://ollama.com/download
    echo           2. Install and restart this computer if needed
    echo           3. Then open CMD and run:
    echo              ollama pull qwen2.5:7b
    echo              ollama pull nomic-embed-text
) else (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do set OV=%%v
    echo [OK] Ollama found: %OV%
    echo.
    echo [TIP] If you don't have models yet, run these in CMD:
    echo        ollama pull qwen2.5:7b         ^<-- best for tool calling
    echo        ollama pull llama3.2:3b        ^<-- lightweight option
    echo        ollama pull nomic-embed-text   ^<-- for Obsidian search
)

echo.
echo  ==========================================
echo   Done! Double-click start.bat to launch.
echo  ==========================================
echo.
pause
