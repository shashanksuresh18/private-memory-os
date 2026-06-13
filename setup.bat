@echo off
setlocal

echo ============================================================
echo   Sovereign Citadel - Client Setup
echo ============================================================
echo.
echo This installs dependencies, builds the UI, and pulls the
echo local AI models. Run it once from the project root.
echo.

echo [1/6] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo [2/6] Installing UI dependencies (npm)...
call npm install
if errorlevel 1 goto :error

echo.
echo [3/6] Building the UI...
call npm run build
if errorlevel 1 goto :error

echo.
echo [4/6] Pulling local Ollama models (this can take a while)...
echo        - nomic-embed-text (retrieval embeddings)
ollama pull nomic-embed-text
echo        - gemma4-citadel (local note structuring + S3 answers)
ollama pull gemma4-citadel

echo.
echo [5/6] Creating local vault folders (your private data lives here)...
if not exist "vault\raw\s1" mkdir "vault\raw\s1"
if not exist "vault\raw\s2" mkdir "vault\raw\s2"
if not exist "vault\raw\s3" mkdir "vault\raw\s3"
if not exist "vault\inbox" mkdir "vault\inbox"
echo        vault\raw\{s1,s2,s3} and vault\inbox ready

echo.
echo Preparing your environment file...
if not exist ".env" (
    copy ".env.example" ".env"
    echo        Created .env from .env.example
) else (
    echo        .env already exists - leaving it untouched
)

echo.
echo [6/6] Done.
echo.
echo ============================================================
echo   Setup complete.
echo.
echo   Edit .env with your API keys before using cloud-enabled
echo   S1/S2 features. S3 stays local and needs no keys.
echo ============================================================
echo.
goto :end

:error
echo.
echo ============================================================
echo   Setup FAILED at the step above.
echo   Read the error, fix it, then run setup.bat again.
echo ============================================================
echo.

:end
pause
