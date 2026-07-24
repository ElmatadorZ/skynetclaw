@echo off
setlocal EnableDelayedExpansion
title Money Atlas GM — Ollama Setup
color 0A

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║        MONEY ATLAS GM — Ollama AI Setup             ║
echo  ║     Local AI  ^|  No API Key  ^|  Free Forever        ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ─── Detect RAM ──────────────────────────────────────────────
set RAM_GB=8
for /f "skip=1 tokens=1" %%a in ('wmic os get TotalVisibleMemorySize 2^>nul') do (
    if "%%a" neq "" if "%%a" neq "TotalVisibleMemorySize" (
        set /a RAM_GB=%%a / 1048576 + 1 2>nul
        goto :RAM_DONE
    )
)
:RAM_DONE
echo  RAM: ~!RAM_GB! GB

:: ─── Detect GPU ──────────────────────────────────────────────
set GPU_NAME=No GPU
set VRAM_GB=0
where nvidia-smi >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%g in ('nvidia-smi --query-gpu^=name --format^=csv,noheader 2^>nul') do (
        if "!GPU_NAME!"=="No GPU" set GPU_NAME=%%g
    )
    for /f "tokens=1 delims= " %%v in ('nvidia-smi --query-gpu^=memory.total --format^=csv,noheader,nounits 2^>nul') do (
        if "!VRAM_GB!"=="0" set /a VRAM_GB=%%v / 1024
    )
    echo  GPU: !GPU_NAME! ^(!VRAM_GB! GB VRAM^)
) else (
    echo  GPU: None detected ^(CPU only mode^)
)
echo.

:: ─── Install Ollama ──────────────────────────────────────────
where ollama >nul 2>&1
if %errorlevel%==0 (
    echo  [OK] Ollama: 
    ollama --version
) else (
    echo  [SETUP] Installing Ollama...
    winget install Ollama.Ollama --silent --accept-source-agreements --accept-package-agreements >nul 2>&1
    if !errorlevel!==0 ( echo  [OK] Installed via winget ) else (
        echo  Downloading from ollama.com...
        powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe'" 2>nul
        if exist "%TEMP%\OllamaSetup.exe" ( "%TEMP%\OllamaSetup.exe" /silent & timeout /t 10 /nobreak >nul & echo  [OK] Installed )
        else ( echo  [ERROR] Please install manually: https://ollama.com/download & pause )
    )
)

echo.
echo  Starting Ollama service...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if %errorlevel% neq 0 ( start /B "" ollama serve >nul 2>&1 & timeout /t 4 /nobreak >nul )
echo  [OK] Running
echo.

:: ─── Tier Selection ──────────────────────────────────────────
echo  ╔══════════════════════════════════════════════════════╗
echo  ║            เลือก Spec เครื่องของคุณ                 ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo    [1]  HIGH   — RAM 24GB+  ^|  GPU 12GB VRAM+
echo    [2]  MID    — RAM 8-16GB ^|  GPU 4-8GB VRAM
echo    [3]  LOW    — RAM 2-8GB  ^|  CPU only (ไม่มี GPU)
echo.
choice /C 123 /M "Select spec (1-3):"
set TIER=%errorlevel%
echo.

:: ─── HIGH SPEC ───────────────────────────────────────────────
if %TIER%==1 (
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║  HIGH SPEC — RAM 24GB+  GPU 12GB+                              ║
echo  ╠══════════════════════════════════════════════════════════════════╣
echo  ║  №  Model            Size     Speed           Quality           ║
echo  ║  ─────────────────────────────────────────────────────────────  ║
echo  ║  1  gemma4:27b       16 GB    15-25 tok/s     ★★★★★ BEST      ║
echo  ║  2  gemma3:27b       16 GB    15-25 tok/s     ★★★★★ Stable    ║
echo  ║  3  qwen2.5:14b       9 GB    20-30 tok/s     ★★★★☆ Thai++    ║
echo  ║  4  gemma4:12b        7 GB    25-40 tok/s     ★★★★☆ Fast      ║
echo  ║  5  llama3.3:70b     40 GB    5-10 tok/s      ★★★★★ Max       ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
echo  แนะนำ: [1] gemma4:27b
echo.
choice /C 12345 /M "เลือก model (1-5):"
if %errorlevel%==1 ( set MDL=gemma4:27b   & set INFO=Gemma 4 27B ^| 16GB ^| ★★★★★ )
if %errorlevel%==2 ( set MDL=gemma3:27b   & set INFO=Gemma 3 27B ^| 16GB ^| ★★★★★ )
if %errorlevel%==3 ( set MDL=qwen2.5:14b  & set INFO=Qwen 2.5 14B ^| 9GB ^| ★★★★☆ )
if %errorlevel%==4 ( set MDL=gemma4:12b   & set INFO=Gemma 4 12B ^| 7GB ^| ★★★★☆ )
if %errorlevel%==5 ( set MDL=llama3.3:70b & set INFO=Llama 3.3 70B ^| 40GB ^| ★★★★★ )
)

:: ─── MID SPEC ────────────────────────────────────────────────
if %TIER%==2 (
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║  MID SPEC — RAM 8-16GB  GPU 4-8GB                              ║
echo  ╠══════════════════════════════════════════════════════════════════╣
echo  ║  №  Model            Size     Speed           Quality           ║
echo  ║  ─────────────────────────────────────────────────────────────  ║
echo  ║  1  gemma4:12b        7 GB    15-25 tok/s     ★★★★★ BEST      ║
echo  ║  2  gemma3:12b        7 GB    15-25 tok/s     ★★★★☆ Stable    ║
echo  ║  3  qwen2.5:7b        4.7GB   20-35 tok/s     ★★★★☆ Thai++    ║
echo  ║  4  gemma4:4b         2.5GB   30-50 tok/s     ★★★☆☆ Light     ║
echo  ║  5  llama3.1:8b       4.7GB   20-30 tok/s     ★★★☆☆ Meta      ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
echo  แนะนำ: [1] gemma4:12b
echo.
choice /C 12345 /M "เลือก model (1-5):"
if %errorlevel%==1 ( set MDL=gemma4:12b   & set INFO=Gemma 4 12B ^| 7GB ^| ★★★★★ )
if %errorlevel%==2 ( set MDL=gemma3:12b   & set INFO=Gemma 3 12B ^| 7GB ^| ★★★★☆ )
if %errorlevel%==3 ( set MDL=qwen2.5:7b   & set INFO=Qwen 2.5 7B ^| 4.7GB ^| ★★★★☆ )
if %errorlevel%==4 ( set MDL=gemma4:4b    & set INFO=Gemma 4 4B ^| 2.5GB ^| ★★★☆☆ )
if %errorlevel%==5 ( set MDL=llama3.1:8b  & set INFO=Llama 3.1 8B ^| 4.7GB ^| ★★★☆☆ )
)

:: ─── LOW SPEC ────────────────────────────────────────────────
if %TIER%==3 (
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║  LOW SPEC — RAM 2-8GB  CPU Only                                ║
echo  ╠══════════════════════════════════════════════════════════════════╣
echo  ║  №  Model            Size     Speed           Quality           ║
echo  ║  ─────────────────────────────────────────────────────────────  ║
echo  ║  1  gemma4:4b         2.5GB   3-8 tok/s       ★★★★☆ BEST      ║
echo  ║  2  phi3.5            2.2GB   3-6 tok/s       ★★★★☆ Microsoft  ║
echo  ║  3  gemma3:4b         2.5GB   3-8 tok/s       ★★★☆☆ Stable    ║
echo  ║  4  qwen2.5:1.5b      986MB   5-10 tok/s      ★★★☆☆ Thai OK   ║
echo  ║  5  gemma4:1b         800MB   8-15 tok/s      ★★☆☆☆ Tiny      ║
echo  ║  6  tinyllama          637MB  10-20 tok/s      ★☆☆☆☆ Minimal   ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
echo  แนะนำ: [1] gemma4:4b  หรือ [2] phi3.5
echo  Note: CPU mode = ช้า 15-60 วินาทีต่อ response (ปกติ)
echo.
choice /C 123456 /M "เลือก model (1-6):"
if %errorlevel%==1 ( set MDL=gemma4:4b     & set INFO=Gemma 4 4B ^| 2.5GB ^| ★★★★☆ )
if %errorlevel%==2 ( set MDL=phi3.5        & set INFO=Phi 3.5 Mini ^| 2.2GB ^| ★★★★☆ )
if %errorlevel%==3 ( set MDL=gemma3:4b     & set INFO=Gemma 3 4B ^| 2.5GB ^| ★★★☆☆ )
if %errorlevel%==4 ( set MDL=qwen2.5:1.5b  & set INFO=Qwen 2.5 1.5B ^| 986MB ^| ★★★☆☆ )
if %errorlevel%==5 ( set MDL=gemma4:1b     & set INFO=Gemma 4 1B ^| 800MB ^| ★★☆☆☆ )
if %errorlevel%==6 ( set MDL=tinyllama     & set INFO=TinyLlama 1.1B ^| 637MB ^| ★☆☆☆☆ )
)

:: ─── Download ────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  Downloading: !MDL!
echo  ║  !INFO!
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  Ctrl+C to cancel — can resume later: ollama pull !MDL!
echo.

ollama pull !MDL!

if %errorlevel%==0 (
    echo.
    echo  [OK] Download complete
) else (
    echo.
    echo  [WARN] Download interrupted. Resume: ollama pull !MDL!
)

:: ─── Save Config ─────────────────────────────────────────────
echo.
echo  Saving ai_config.json...
(
echo {
echo   "provider": "ollama",
echo   "claude":  {"key": "", "model": "claude-sonnet-4-5"},
echo   "openai":  {"key": "", "model": "gpt-4o"},
echo   "gemini":  {"key": "", "model": "gemini-1.5-flash"},
echo   "groq":    {"key": "", "model": "llama-3.3-70b-versatile"},
echo   "ollama":  {"url": "http://localhost:11434", "model": "!MDL!"}
echo }
) > ai_config.json
echo  [OK] Saved

:: ─── Quick Test ──────────────────────────────────────────────
echo.
echo  Quick test (type 'exit' to quit test)...
ollama run !MDL! "Say READY in 1 word only" 2>nul

:: ─── Done ────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║                 SETUP COMPLETE!                     ║
echo  ╠══════════════════════════════════════════════════════╣
echo  ║  Model :  !MDL!
echo  ║  Spec  :  !INFO!
echo  ║  RAM   :  ~!RAM_GB! GB
echo  ║  GPU   :  !GPU_NAME!
echo  ╠══════════════════════════════════════════════════════╣
echo  ║  NEXT STEPS:                                        ║
echo  ║  1. Run BUILD_AND_RUN.bat                           ║
echo  ║  2. Open MoneyAtlasGM.exe                           ║
echo  ║  3. Open MT5 ^& enable AutoTrading                   ║
echo  ║  4. Click START                                     ║
echo  ║                                                     ║
echo  ║  Change model anytime: click Ollama MODELS in app  ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  Installed models:
ollama list
echo.
pause
