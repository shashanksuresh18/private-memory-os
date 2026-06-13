# Launch Sovereign Citadel OPF Tier S2 DLP service on 127.0.0.1
# PowerShell — Windows host

$ErrorActionPreference = "Stop"

# 1. Resolve project root (this script is two levels under repo root)
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..\..").Path
Set-Location $ProjectRoot

# 2. Create / reuse local venv at .venv (kept out of git via .gitignore patterns)
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "creating venv at .venv ..."
    py -3.12 -m venv .venv
}

# 3. Install dependencies (idempotent)
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r src\firewall\opf\requirements.txt
& .venv\Scripts\python.exe -m pip install -e privacy-filter

# 4. Generate shared secret on first run (never overwrite)
if (-not $env:SOVEREIGN_OPF_TOKEN) {
    $tokenFile = "src\firewall\opf\.token"
    if (-not (Test-Path $tokenFile)) {
        $token = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
        Set-Content -Path $tokenFile -Value $token -NoNewline -Encoding ascii
        Write-Host "generated shared-secret token at $tokenFile"
    }
    $env:SOVEREIGN_OPF_TOKEN = (Get-Content $tokenFile -Raw).Trim()
}

# 5. Optional: pre-pin OPF checkpoint path (uncomment after first download to go air-gapped)
# $env:OPF_CHECKPOINT = "$HOME\.opf\privacy_filter"

# 6. Optional: switch to cuda when GPU available
# $env:SOVEREIGN_OPF_DEVICE = "cuda"

Write-Host "starting OPF DLP on 127.0.0.1:8765 ..."
& .venv\Scripts\python.exe -m src.firewall.opf.main
