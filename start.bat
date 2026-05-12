@echo off
:: Locali — Windows Quick Launcher
:: Double-click this file from the USB drive to start

title Locali — Local AI
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   🧠  Locali — Starting...       ║
echo  ╚══════════════════════════════════════╝
echo.

:: Try Python launcher first (best experience)
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    python launcher\launch.py
    goto :end
)

where python3 >nul 2>&1
if %ERRORLEVEL% == 0 (
    python3 launcher\launch.py
    goto :end
)

:: Fallback: run binary directly with config defaults
echo  Python not found. Starting in fallback mode...
echo.

for /f "tokens=2 delims=:" %%a in ('findstr "model" config.json') do (
    set MODEL_LINE=%%a
)
set MODEL_FILE=gemma-3-1b-it-q4_k_m.gguf

bin\windows\llama-server.exe ^
    --model models\%MODEL_FILE% ^
    --host 127.0.0.1 ^
    --port 8080 ^
    --ctx-size 2048 ^
    --threads 4 ^
    --log-disable

:end
pause
