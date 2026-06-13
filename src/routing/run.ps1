# Launch Sovereign Router (Tri-Tier S1/S2/S3 proxy) on 127.0.0.1:8770
# PowerShell — Windows host

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "creating venv at .venv ..."
    py -3.12 -m venv .venv
}

& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r src\routing\requirements.txt

if (-not $env:SOVEREIGN_ROUTER_TOKEN) {
    $tokenFile = "src\routing\.token"
    if (-not (Test-Path $tokenFile)) {
        $token = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
        Set-Content -Path $tokenFile -Value $token -NoNewline -Encoding ascii
        Write-Host "generated router shared-secret token at $tokenFile"
    }
    $env:SOVEREIGN_ROUTER_TOKEN = (Get-Content $tokenFile -Raw).Trim()
}

# Required for S1 + S2 cloud egress
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Warning "ANTHROPIC_API_KEY is not set — S1 and S2 calls will fail at the upstream"
}

# Optional overrides
# $env:SOVEREIGN_LOCAL_MODEL = "qwen2.5:32b-instruct-q4_K_M"
# $env:OLLAMA_BASE_URL       = "http://127.0.0.1:11434"

Write-Host "starting Sovereign Router on 127.0.0.1:8770 ..."
& .venv\Scripts\python.exe -m src.routing.sovereign_router
