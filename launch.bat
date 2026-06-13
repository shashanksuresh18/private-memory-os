@echo off
setlocal enabledelayedexpansion
title Sovereign Citadel
cd /d "%~dp0"

echo ==============================================
echo    SOVEREIGN CITADEL - starting everything
echo ==============================================
echo.

REM --- Document drop folders (tier by folder) -----------------------------
REM s1 = public, s2 = sensitive, s3 = confidential. Anything dropped in
REM vault\raw\ root is treated as confidential (S3). Created on first run.
if not exist "vault\raw\s1" mkdir "vault\raw\s1"
if not exist "vault\raw\s2" mkdir "vault\raw\s2"
if not exist "vault\raw\s3" mkdir "vault\raw\s3"

REM --- 1/4 Ollama (local AI models) ---------------------------------------
curl -s -o nul --max-time 2 http://127.0.0.1:11434/api/version
if errorlevel 1 (
    echo [1/4] Ollama not running - starting it now...
    start "Ollama" /MIN cmd /c "ollama serve"
) else (
    echo [1/4] Ollama is already running.
)

set /a tries=0
:wait_ollama
curl -s -o nul --max-time 2 http://127.0.0.1:11434/api/version
if not errorlevel 1 goto ollama_ok
set /a tries+=1
if !tries! geq 30 (
    echo.
    echo [PROBLEM] Ollama did not start after 30 seconds.
    echo           Install it from https://ollama.com/download
    echo           then double-click launch.bat again.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_ollama
:ollama_ok

REM --- 2/4 API server (port 7734) ------------------------------------------
curl -s -o nul --max-time 2 http://127.0.0.1:7734/health
if errorlevel 1 (
    echo [2/4] Starting the brain ^(API server, port 7734^)...
    start "Citadel API - port 7734 - do not close" /MIN cmd /c "python -m uvicorn src.api.server:app --host 127.0.0.1 --port 7734"
) else (
    echo [2/4] API server is already running.
)

set /a tries=0
:wait_api
curl -s -o nul --max-time 2 http://127.0.0.1:7734/health
if not errorlevel 1 goto api_ok
set /a tries+=1
if !tries! geq 60 (
    echo.
    echo [PROBLEM] The API server did not start after 60 seconds.
    echo           Look at the minimized window named "Citadel API"
    echo           on your taskbar for the error message.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_api
:api_ok

REM --- 3/4 UI server (port 3003) --------------------------------------------
curl -s -o nul --max-time 2 http://127.0.0.1:3003/
if errorlevel 1 (
    echo [3/4] Starting the screen ^(UI server, port 3003^)...
    start "Citadel UI - port 3003 - do not close" /MIN cmd /c "python -m http.server 3003 --bind 127.0.0.1 --directory src\ui\dist"
) else (
    echo [3/4] UI server is already running.
)

set /a tries=0
:wait_ui
curl -s -o nul --max-time 2 http://127.0.0.1:3003/
if not errorlevel 1 goto ui_ok
set /a tries+=1
if !tries! geq 30 (
    echo.
    echo [PROBLEM] The UI server did not start after 30 seconds.
    echo           Another program may be using port 3003.
    echo           See docs\CLIENT_SETUP.md - Troubleshooting.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_ui
:ui_ok

REM --- 4/4 Open the browser ---------------------------------------------------
echo [4/4] Opening your browser...
start "" http://127.0.0.1:3003

echo.
echo ==============================================
echo    ALL RUNNING
echo      App     : http://127.0.0.1:3003
echo      Brain   : http://127.0.0.1:7734/health
echo      Add docs: drop files into  vault\raw\
echo                s1=public  s2=sensitive  s3=secret
echo                (unsure - use s3; indexed within
echo                 about 10 minutes)
echo ==============================================
echo.
echo  You can close THIS window. The two minimized
echo  "Citadel" windows on the taskbar must stay open.
echo.
pause
