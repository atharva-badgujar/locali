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

setlocal EnableDelayedExpansion
set "MODEL_FILE="
for /f "tokens=2 delims=:," %%a in ('findstr /i "\"model\"" config.json') do set "MODEL_FILE=%%a"
set "MODEL_FILE=!MODEL_FILE:"=!"
set "MODEL_FILE=!MODEL_FILE: =!"
if not defined MODEL_FILE set "MODEL_FILE=gemma-3-1b-it-q4_k_m.gguf"

set "PORT=8080"
for /f "tokens=2 delims=:," %%a in ('findstr /i "\"port\"" config.json') do set "PORT=%%a"
set "PORT=!PORT: =!"
if not defined PORT set "PORT=8080"

bin\windows\llama-server.exe ^
    --model models\!MODEL_FILE! ^
    --host 127.0.0.1 ^
    --port !PORT! ^
    --ctx-size 2048 ^
    --threads 4 ^
    --log-disable
endlocal

:end
pause
