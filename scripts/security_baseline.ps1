# Sovereign Citadel -- OS-Level Security Baseline
# Boot-gate for the local AI stack. Exit 0 = safe to start. Exit 1 = halt.
#
# Usage:
#   powershell.exe -ExecutionPolicy Bypass -File scripts/security_baseline.ps1
#   powershell.exe -ExecutionPolicy Bypass -File scripts/security_baseline.ps1 -Baseline
#
# Checks:
#   1. BitLocker FullyEncrypted on %SystemDrive%  (requires admin)
#   2. Project root + vault/ + audit/ + backups/ outside every detected
#      OneDrive root (consumer, commercial, generic env vars)
#   3. NotContentIndexed attribute on vault/ + audit/ + backups/ (recursive)
#   4. Supply-chain SHA manifest at config/sha_manifest.json
#      - fail-closed if missing (re-run with -Baseline to seed)
#      - diff added/removed/changed files when present

[CmdletBinding()]
param(
    [switch]$Baseline,
    [string]$ManifestPath = "config/sha_manifest.json",
    [switch]$SkipBitLocker
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

Write-Host "[SEC-SCAN] Sovereign Citadel OS-Level Security Baseline" -ForegroundColor Cyan
Write-Host "[SEC-SCAN] Project root: $ProjectRoot"
Write-Host ""

# ---------- 1. BitLocker ----------
Write-Step "Verifying BitLocker on system drive ..."
if ($SkipBitLocker) {
    Write-Warn2 "Skipped via -SkipBitLocker. DO NOT use in production."
} else {
    $systemDrive = $env:SystemDrive
    try {
        $bitlocker = Get-BitLockerVolume -MountPoint $systemDrive -ErrorAction Stop
        if ($bitlocker.VolumeStatus -ne 'FullyEncrypted') {
            Write-Fatal "$systemDrive volume status is '$($bitlocker.VolumeStatus)', not FullyEncrypted."
        }
        Write-Ok "$systemDrive FullyEncrypted ($($bitlocker.EncryptionMethod), $($bitlocker.EncryptionPercentage)%)."
    }
    catch [System.Management.Automation.CommandNotFoundException] {
        Write-Fatal "Get-BitLockerVolume not found. Requires Windows 10/11 Pro/Enterprise."
    }
    catch {
        $msg = $_.Exception.Message
        if ($msg -match '(?i)access.*denied|requires elevation|administrator' -or
            $_.Exception -is [System.UnauthorizedAccessException] -or
            $_.Exception.HResult -eq -2147024891) {
            Write-Fatal "BitLocker check requires an elevated PowerShell. Re-run as Administrator (or pass -SkipBitLocker for dev only)."
        }
        Write-Fatal "BitLocker check failed: $msg"
    }
}

# ---------- 2. OneDrive / cloud-sync isolation ----------
Write-Step "Verifying OneDrive isolation ..."
$oneDriveCandidates = @($env:OneDrive, $env:OneDriveCommercial, $env:OneDriveConsumer) |
    Where-Object { $_ -and $_.Trim().Length -gt 0 } |
    Select-Object -Unique

if (-not $oneDriveCandidates -or $oneDriveCandidates.Count -eq 0) {
    Write-Info "No OneDrive environment variables detected on this user profile."
} else {
    foreach ($od in $oneDriveCandidates) {
        if ($ProjectRoot.StartsWith($od, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Fatal "Project root '$ProjectRoot' is inside OneDrive ('$od'). MNPI would sync to Microsoft cloud."
        }
    }
    foreach ($sub in @('vault','audit','backups')) {
        $p = Join-Path $ProjectRoot $sub
        if (-not (Test-Path $p)) { continue }
        $resolved = (Resolve-Path $p).Path
        foreach ($od in $oneDriveCandidates) {
            if ($resolved.StartsWith($od, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-Fatal "'$sub' directory '$resolved' is inside OneDrive ('$od')."
            }
        }
    }
    Write-Ok "Project root and sensitive dirs outside $($oneDriveCandidates.Count) detected OneDrive root(s)."
}

# Desktop-redirection guard (Known Folder Move silently re-routes Desktop into OneDrive)
$desktop = Join-Path $env:USERPROFILE 'Desktop'
if ($ProjectRoot.StartsWith($desktop, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Warn2 "Project lives under \$env:USERPROFILE\Desktop. If 'Known Folder Move' is enabled in OneDrive settings, Desktop itself becomes a synced folder and MNPI WILL leak. Verify: Settings -> OneDrive -> Backup -> Manage backup -> Desktop must be OFF."
}

# Documents redirection guard
$documents = Join-Path $env:USERPROFILE 'Documents'
if ($ProjectRoot.StartsWith($documents, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Warn2 "Project lives under Documents. Same Known Folder Move risk as Desktop."
}

# ---------- 3. Disable Windows Search content indexing (recursive) ----------
Write-Step "Setting NotContentIndexed attribute on vault/, audit/, backups/ ..."
$sensitiveDirs = @('vault','audit','backups')
foreach ($d in $sensitiveDirs) {
    $abs = Join-Path $ProjectRoot $d
    if (-not (Test-Path $abs)) { continue }
    try {
        $items = @(Get-Item -LiteralPath $abs)
        $items += Get-ChildItem -LiteralPath $abs -Recurse -Directory -ErrorAction SilentlyContinue
        $touched = 0
        foreach ($it in $items) {
            if (-not ($it.Attributes -band [System.IO.FileAttributes]::NotContentIndexed)) {
                $it.Attributes = ($it.Attributes -bor [System.IO.FileAttributes]::NotContentIndexed)
                $touched++
            }
        }
        Write-Ok "$d`t: NotContentIndexed set on $($items.Count) dir(s) (touched=$touched)."
    }
    catch {
        Write-Warn2 "$d`t: could not set NotContentIndexed -- $($_.Exception.Message)"
    }
}
Write-Info "Belt-and-braces: also add these paths in Settings -> Search -> Searching Windows -> Excluded folders."

# ---------- 4. Supply-chain SHA pinning ----------
Write-Step "Verifying supply-chain SHA manifest at '$ManifestPath' ..."

function Get-PinnedHashes {
    param([string]$Root)
    $roots = @(
        @{ Path = 'src';                Filter = '*.py' },
        @{ Path = 'tools';              Filter = '*.py' },
        @{ Path = 'privacy-filter/opf'; Filter = '*.py' }
    )
    $extras = @('privacy-filter/pyproject.toml', 'privacy-filter/LICENSE')

    $found = @{}
    foreach ($r in $roots) {
        $abs = Join-Path $Root $r.Path
        if (-not (Test-Path $abs)) { continue }
        Get-ChildItem -LiteralPath $abs -Recurse -File -Filter $r.Filter -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\__pycache__\\' -and $_.FullName -notmatch '\\\.venv\\' } |
            ForEach-Object {
                $rel = $_.FullName.Substring($Root.Length + 1) -replace '\\','/'
                $found[$rel] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
    }
    foreach ($e in $extras) {
        $abs = Join-Path $Root $e
        if (Test-Path $abs) {
            $rel = $e -replace '\\','/'
            $found[$rel] = (Get-FileHash -LiteralPath $abs -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    return $found
}

$manifestFull = Join-Path $ProjectRoot $ManifestPath
$current = Get-PinnedHashes -Root $ProjectRoot

if (-not (Test-Path $manifestFull)) {
    if (-not $Baseline) {
        Write-Fatal "No SHA manifest at '$ManifestPath'. Re-run with -Baseline once to seed it after a known-good build."
    }
    $manifestDir = Split-Path $manifestFull
    if (-not (Test-Path $manifestDir)) { New-Item -ItemType Directory -Force -Path $manifestDir | Out-Null }
    $current | ConvertTo-Json -Depth 4 | Out-File -FilePath $manifestFull -Encoding utf8
    Write-Ok "Baseline manifest written with $($current.Count) entries -> $ManifestPath."
} else {
    $rawJson = Get-Content -LiteralPath $manifestFull -Raw -Encoding utf8
    $pinned = $rawJson | ConvertFrom-Json
    $pinnedMap = @{}
    $pinned.PSObject.Properties | ForEach-Object { $pinnedMap[$_.Name] = "$($_.Value)".ToLowerInvariant() }

    $added   = @($current.Keys   | Where-Object { -not $pinnedMap.ContainsKey($_) })
    $removed = @($pinnedMap.Keys | Where-Object { -not $current.ContainsKey($_) })
    $changed = @($current.Keys   | Where-Object { $pinnedMap.ContainsKey($_) -and $pinnedMap[$_] -ne $current[$_] })

    if ($added.Count -or $removed.Count -or $changed.Count) {
        foreach ($f in $added)   { Write-Host "       +ADD     $f" -ForegroundColor Yellow }
        foreach ($f in $removed) { Write-Host "       -REMOVE  $f" -ForegroundColor Yellow }
        foreach ($f in $changed) { Write-Host "       ~CHANGE  $f" -ForegroundColor Yellow }

        if ($Baseline) {
            $current | ConvertTo-Json -Depth 4 | Out-File -FilePath $manifestFull -Encoding utf8
            Write-Warn2 "Manifest re-baselined under -Baseline: added=$($added.Count) removed=$($removed.Count) changed=$($changed.Count)."
        } else {
            Write-Fatal "SHA drift: added=$($added.Count) removed=$($removed.Count) changed=$($changed.Count). After intentional update, re-run with -Baseline."
        }
    } else {
        Write-Ok "$($pinnedMap.Count) files verified -- no drift."
    }
}

Write-Host ""
Write-Host "[SUCCESS] Sovereign Citadel OS Security Baseline PASSED." -ForegroundColor Green
exit 0
