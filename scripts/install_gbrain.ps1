# Sovereign Citadel -- gbrain bootstrap for Windows 11
#
# Steps:
#   1. Install Bun (if missing) via the official PowerShell installer.
#   2. Install gbrain globally from the local fork at repos-audit/garrytan__gbrain.
#      (Using local fork avoids the upstream-pin moving target. Switch to
#       'bun install -g github:garrytan/gbrain' once you've forked + pinned.)
#   3. Run `gbrain init --pglite` so the brain is local-only (zero Supabase deps).
#   4. Register vault/ as the canonical source.
#   5. First sync to ingest the seed templates.
#   6. Run doctor to verify the install.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/install_gbrain.ps1
#
# Reentrant: skips steps that already completed.

[CmdletBinding()]
param(
    [switch]$SkipBunInstall,
    [switch]$ForceReinit
)

$ErrorActionPreference = "Stop"

function Write-Step($msg)  { Write-Host "  -> $msg" }
function Write-Ok($msg)    { Write-Host "     [OK]    $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "     [WARN]  $msg" -ForegroundColor Yellow }
function Write-Info($msg)  { Write-Host "     [INFO]  $msg" -ForegroundColor Cyan }
function Write-Fatal($msg) {
    Write-Host "[FATAL] $msg" -ForegroundColor Red
    exit 1
}

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $ProjectRoot

Write-Host "[gbrain] Sovereign Citadel knowledge-brain bootstrap" -ForegroundColor Cyan
Write-Host "[gbrain] Project root: $ProjectRoot"
Write-Host ""

# ---------- 1. Bun ----------
Write-Step "Checking Bun ..."
$bunExe = Get-Command bun -ErrorAction SilentlyContinue
if ($bunExe) {
    $ver = & bun --version 2>$null
    Write-Ok "Bun present (v$ver, $($bunExe.Path))"
} elseif ($SkipBunInstall) {
    Write-Fatal "Bun missing and -SkipBunInstall was passed. Install Bun then re-run."
} else {
    Write-Step "Installing Bun via official Windows installer ..."
    Invoke-WebRequest -UseBasicParsing https://bun.sh/install.ps1 |
        Select-Object -ExpandProperty Content |
        Invoke-Expression
    # Refresh PATH for this session so subsequent calls see bun.exe.
    $env:Path = "$env:USERPROFILE\.bun\bin;$env:Path"
    $bunExe = Get-Command bun -ErrorAction SilentlyContinue
    if (-not $bunExe) {
        Write-Fatal "Bun install reported success but bun.exe not on PATH. Open a fresh PowerShell and re-run."
    }
    Write-Ok "Bun installed ($(& bun --version))"
}

# ---------- 2. gbrain ----------
Write-Step "Checking gbrain ..."
$gbrainExe = Get-Command gbrain -ErrorAction SilentlyContinue
if ($gbrainExe) {
    $ver = & gbrain --version 2>$null
    Write-Ok "gbrain present ($ver, $($gbrainExe.Path))"
} else {
    Write-Step "Installing gbrain from local fork at repos-audit/garrytan__gbrain ..."
    $forkPath = Join-Path $ProjectRoot "repos-audit\garrytan__gbrain"
    if (-not (Test-Path $forkPath)) {
        Write-Fatal "Local fork not found at $forkPath. Re-clone via scripts/clone_all.sh first."
    }
    Push-Location $forkPath
    try {
        & bun install
        if ($LASTEXITCODE -ne 0) { Write-Fatal "bun install failed in fork (see output above)" }
        & bun link
        if ($LASTEXITCODE -ne 0) { Write-Fatal "bun link failed in fork" }
    } finally {
        Pop-Location
    }
    & bun link gbrain
    if ($LASTEXITCODE -ne 0) { Write-Fatal "bun link gbrain failed (project root)" }
    Write-Ok "gbrain linked from local fork ($(& gbrain --version))"
    Write-Info "Switch to a pinned-SHA install once you fork upstream:"
    Write-Info "  bun install -g github:YOUR_ORG/gbrain#<sha>"
}

# ---------- 3. gbrain init ----------
Write-Step "Initializing brain (PGLite, local-only) ..."
$gbrainHome = Join-Path $env:USERPROFILE ".gbrain"
$brainAlreadyInited = (Test-Path (Join-Path $gbrainHome "config.json"))
if ($brainAlreadyInited -and -not $ForceReinit) {
    Write-Ok "$gbrainHome already initialized (pass -ForceReinit to redo)"
} else {
    if ($ForceReinit -and $brainAlreadyInited) {
        Write-Warn2 "-ForceReinit set; tearing down existing brain at $gbrainHome"
        Remove-Item -Recurse -Force $gbrainHome
    }
    & gbrain init --pglite --yes
    if ($LASTEXITCODE -ne 0) { Write-Fatal "gbrain init failed" }
    Write-Ok "Brain initialized (PGLite at $gbrainHome)"
}

# ---------- 4. Source registration ----------
Write-Step "Registering vault/ as the 'citadel' source ..."
$vaultPath = (Join-Path $ProjectRoot "vault")
if (-not (Test-Path $vaultPath)) {
    Write-Fatal "vault/ not found at $vaultPath"
}
# Idempotent: 'gbrain sources add' refuses to re-add by name; we swallow that.
$sourceOutput = & gbrain sources add citadel --path $vaultPath --name "Sovereign Citadel Vault" 2>&1
if ($LASTEXITCODE -ne 0) {
    if ($sourceOutput -match 'already exists') {
        Write-Ok "Source 'citadel' already registered"
    } else {
        Write-Fatal "gbrain sources add failed: $sourceOutput"
    }
} else {
    Write-Ok "Source 'citadel' added"
}

# ---------- 5. First sync ----------
Write-Step "Syncing vault/ into brain ..."
& gbrain sync --source citadel --no-embed
if ($LASTEXITCODE -ne 0) { Write-Fatal "gbrain sync failed" }
Write-Ok "Sync complete (--no-embed: skipped embedding for first pass)"
Write-Info "Run 'gbrain embed --stale' later to embed for vector search."

# ---------- 6. Doctor ----------
Write-Step "Running gbrain doctor ..."
& gbrain doctor
$doctorExit = $LASTEXITCODE

Write-Host ""
if ($doctorExit -eq 0) {
    Write-Host "[SUCCESS] gbrain bootstrap complete." -ForegroundColor Green
    Write-Host ""
    Write-Host "Try:" -ForegroundColor Cyan
    Write-Host '  gbrain search "Alice"'
    Write-Host '  gbrain query "who works at Wonderland Capital"'
    Write-Host '  gbrain get_page people/alice-liddell'
    Write-Host '  gbrain extract all --source citadel'
} else {
    Write-Host "[WARN] gbrain doctor returned exit $doctorExit -- review the warnings above." -ForegroundColor Yellow
}
exit $doctorExit
