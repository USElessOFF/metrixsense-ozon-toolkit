#Requires -Version 5.1
<#
.SYNOPSIS
  MetrixSense native installer for Windows (no WSL2, no Docker).

.DESCRIPTION
  Downloads the project, installs Python 3.11+ if needed, creates a virtual
  environment and runs the app as a single process on http://127.0.0.1:8000.

.EXAMPLE
  irm https://raw.githubusercontent.com/USElessOFF/metrixsense-ozon-toolkit/main/install_windows.ps1 | iex
#>

param(
    [string]$RepoZipUrl = "https://github.com/USElessOFF/metrixsense-ozon-toolkit/archive/refs/heads/main.zip",
    [string]$InstallDir = "$env:USERPROFILE\MetrixSense",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}

function Write-Step { param($m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    [OK] $m" -ForegroundColor Green }
function Write-Warn2{ param($m) Write-Host "    [!] $m" -ForegroundColor Yellow }

$origCwd = Get-Location

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  MetrixSense - Windows Installer (native)"     -ForegroundColor Cyan
Write-Host "  No WSL2 / Docker required"                     -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# --- 1. Python ----------------------------------------------------------------
function Find-Python {
    $candidates = New-Object System.Collections.Generic.List[string]
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates.Add("py -3.13"); $candidates.Add("py -3.12"); $candidates.Add("py -3.11")
    }
    $candidates.Add("python"); $candidates.Add("python3")
    foreach ($cand in $candidates) {
        $parts = $cand.Split(' ')
        if (-not (Get-Command $parts[0] -ErrorAction SilentlyContinue)) { continue }
        $preArgs = @(); if ($parts.Count -gt 1) { $preArgs = $parts[1..($parts.Count - 1)] }
        try {
            $out = & $parts[0] @preArgs -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and "$out" -match '^\s*(\d+)\.(\d+)\s*$') {
                $maj = [int]$Matches[1]; $min = [int]$Matches[2]
                if ($maj -eq 3 -and $min -ge 11) {
                    return @{ Exe = $parts[0]; PreArgs = $preArgs; Version = "$maj.$min" }
                }
            }
        } catch { }
    }
    return $null
}

Write-Step "Step 1/5: Python 3.11+"
$python = Find-Python
if (-not $python) {
    Write-Host "    Python 3.11+ not found. Installing..."
    $installed = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
            $installed = $true
        } catch { Write-Warn2 "winget install failed: $($_.Exception.Message)" }
    } else {
        Write-Warn2 "winget is not available - using direct download from python.org"
    }
    if (-not $installed) {
        $pyExe = "$env:TEMP\python-3.11.9-amd64.exe"
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $pyExe -UseBasicParsing
        Start-Process -Wait -FilePath $pyExe -ArgumentList "/quiet","InstallAllUsers=0","PrependPath=1","Include_test=0"
        Remove-Item $pyExe -Force -ErrorAction SilentlyContinue
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
    $python = Find-Python
    if (-not $python) {
        Write-Host "    Python was installed but is not visible in this session." -ForegroundColor Red
        Write-Host "    Close this window, open a NEW PowerShell and run the installer again." -ForegroundColor Red
        exit 1
    }
    Write-Ok "Python $($python.Version) installed"
} else {
    Write-Ok "Found Python $($python.Version)"
}
$py = $python.Exe
$preArgs = @($python.PreArgs)

# --- 2. Project ---------------------------------------------------------------
function Install-Project {
    param([string]$ZipUrl, [string]$DestDir)
    if (Test-Path (Join-Path $DestDir "backend\requirements.txt")) {
        Write-Warn2 "$DestDir already contains MetrixSense - reusing it (delete the folder for a fresh copy)"
        return
    }
    Write-Host "    Downloading project ZIP..."
    $zip = Join-Path $env:TEMP "metrixsense_repo.zip"
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zip -UseBasicParsing
    $tmp = Join-Path $env:TEMP "metrixsense_repo"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $inner = (Get-ChildItem $tmp | Select-Object -First 1).FullName
    if (Test-Path $DestDir) { Remove-Item -Recurse -Force $DestDir }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    Get-ChildItem $inner | Move-Item -Destination $DestDir -Force
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Step "Step 2/5: Project files"
Install-Project -ZipUrl $RepoZipUrl -DestDir $InstallDir
Set-Location $InstallDir
Write-Ok "Project: $InstallDir"

# --- 3. Virtual environment + dependencies ------------------------------------
Write-Step "Step 3/5: Virtual environment and dependencies (a few minutes on first run)"
$venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $py @preArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "    Failed to create the virtual environment." -ForegroundColor Red; exit 1 }
}
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "    Dependency installation failed." -ForegroundColor Red; exit 1 }
Write-Ok "Dependencies ready"

# --- 4. Environment -------------------------------------------------------------
Write-Step "Step 4/5: Environment"
if (-not (Test-Path "backend\.env")) {
    $envContent = @"
HOST=127.0.0.1
PORT=$Port
DEBUG=false
DEFAULT_USERNAME=metrixsense
DEFAULT_PASSWORD=metrixsense
"@
    # UTF-8 without BOM so python-dotenv reads the first key correctly
    [System.IO.File]::WriteAllText((Join-Path $InstallDir "backend\.env"), $envContent)
    Write-Ok "backend\.env created (default admin: metrixsense / metrixsense)"
} else {
    Write-Ok "backend\.env already exists"
}

# --- 5. Start --------------------------------------------------------------------
Write-Step "Step 5/5: Starting MetrixSense"
$batContent = @"
@echo off
title MetrixSense
cd /d "%~dp0"
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
if errorlevel 1 pause
"@
[System.IO.File]::WriteAllText((Join-Path $InstallDir "start_metrixsense.bat"), $batContent)

$health = "http://127.0.0.1:$Port/health"
$alreadyRunning = $false
try { Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2 | Out-Null; $alreadyRunning = $true } catch { }

if ($alreadyRunning) {
    Write-Warn2 "MetrixSense is already running on port $Port"
} else {
    Start-Process -FilePath (Join-Path $InstallDir "start_metrixsense.bat") -WindowStyle Minimized
    Write-Host "    Waiting for the app to start..."
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        try { Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2 | Out-Null; $ready = $true; break } catch { }
    }
    if ($ready) { Write-Ok "MetrixSense is running" }
    else {
        Write-Warn2 "The app has not responded yet (the first start may take longer)."
        Write-Warn2 "Check the MetrixSense console window, then open http://127.0.0.1:$Port"
    }
}

Start-Process "http://127.0.0.1:$Port"
Set-Location $origCwd

Write-Host ""
Write-Host "=== Installation complete! ===" -ForegroundColor Green
Write-Host "Web UI:   http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "API docs: http://127.0.0.1:$Port/docs" -ForegroundColor Green
Write-Host "Start later with: $InstallDir\start_metrixsense.bat"
Write-Host "Data:     $InstallDir\backend\data\metrixsense.db"
Write-Host ""
Write-Host "Known issues:" -ForegroundColor Yellow
Write-Host " - Windows SmartScreen warning -> choose 'Run anyway'"
Write-Host " - Port busy -> edit backend\.env (PORT=...) and run start_metrixsense.bat again"
Write-Host " - Default password is public -> change DEFAULT_PASSWORD in backend\.env"

