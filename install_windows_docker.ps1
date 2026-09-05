#Requires -Version 5.1
<#
.SYNOPSIS
  MetrixSense full installer for Windows: WSL2 + Docker Desktop + deploy.

.DESCRIPTION
  Runs in phases, each phase is idempotent (safe to re-run):
    1/3 WSL2 (silent; one reboot may be required - the installer continues
        automatically after reboot via a RunOnce task)
    2/3 Docker Desktop (silent install) and waiting for the engine
    3/3 Project download and "docker compose up -d --build"

  Requires administrator rights - the script requests them itself (UAC).

.EXAMPLE
  irm https://raw.githubusercontent.com/USElessOFF/metrixsense-ozon-toolkit/main/install_windows_docker.ps1 | iex
#>

param(
    [string]$RepoZipUrl = "https://github.com/USElessOFF/metrixsense-ozon-toolkit/archive/refs/heads/main.zip",
    [string]$InstallDir = "$env:USERPROFILE\MetrixSense",
    [string]$ScriptUrl  = "https://raw.githubusercontent.com/USElessOFF/metrixsense-ozon-toolkit/main/install_windows_docker.ps1"
)

$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}

function Write-Step { param($m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    [OK] $m" -ForegroundColor Green }
function Write-Warn2{ param($m) Write-Host "    [!] $m" -ForegroundColor Yellow }

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  MetrixSense - Full Installer (WSL2 + Docker)"     -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Notes:"
Write-Host " - Administrator rights (UAC prompt) and ONE reboot at the WSL2 step are required."
Write-Host " - Docker Desktop is free for personal use and small businesses (<250 employees)."
Write-Host " - Total download is about 1 GB, the whole process takes 10-20 minutes."

# --- self-elevation ------------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "==> Requesting administrator rights (confirm the UAC prompt)..." -ForegroundColor Cyan
    $cmd = "irm '$ScriptUrl' | iex"
    if ($PSCommandPath -and (Test-Path $PSCommandPath)) { $cmd = "& '$PSCommandPath'" }
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-Command",$cmd
    exit
}

# --- helper: virtualization check ----------------------------------------------
$hypervisor = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
if (-not $hypervisor) {
    Write-Warn2 "Virtualization looks disabled. If the WSL2 step fails, enable VT-x/AMD-V in BIOS/UEFI."
}

# --- helper: port check ----------------------------------------------------------
function Test-PortBusy { param([int]$p)
    return ($null -ne (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue))
}

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

# --- Phase 1/3: WSL2 -------------------------------------------------------------
Write-Step "Phase 1/3: WSL2"
function Test-WslAvailable {
    try { $null = wsl.exe --status 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

if (Test-WslAvailable) {
    Write-Ok "WSL2 is already installed"
} else {
    Write-Host "    Installing WSL2 (silent)..."
    $wslOk = $false
    try {
        wsl.exe --install --no-distribution --web-download 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $wslOk = $true }
    } catch { }
    if (-not $wslOk) {
        Write-Host "    Falling back to DISM features (older Windows builds)..."
        try { dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null } catch { }
        try { dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null } catch { }
    }
    try { wsl.exe --update --web-download 2>&1 | Out-Null } catch { }

    if (-not (Test-WslAvailable)) {
        # A reboot is required; schedule automatic continuation and ask the user.
        $runOnce = "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
        $again = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `"irm '$ScriptUrl' | iex`""
        Set-ItemProperty -Path $runOnce -Name "MetrixSenseInstall" -Value $again
        Write-Host ""
        Write-Warn2 "A REBOOT is required to finish WSL2 setup."
        Write-Host "    After reboot this installer will continue automatically (RunOnce)."
        $ans = Read-Host "    Reboot now? (Y/N)"
        if ($ans -match '^[Yy]') { Restart-Computer -Force }
        else { Write-Host "    Reboot manually - the installer will start on the next logon." }
        exit
    }
    Write-Ok "WSL2 installed"
}

# --- Phase 2/3: Docker Desktop ---------------------------------------------------
Write-Step "Phase 2/3: Docker Desktop"
$dockerCmd = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $dockerCmd) {
    $installed = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            winget install --id Docker.DockerDesktop -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
            $installed = $true
        } catch { Write-Warn2 "winget install failed: $($_.Exception.Message)" }
    }
    if (-not $installed) {
        Write-Host "    Downloading Docker Desktop installer (~500 MB)..."
        $exe = "$env:TEMP\DockerDesktopInstaller.exe"
        Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -OutFile $exe -UseBasicParsing
        Start-Process -Wait -FilePath $exe -ArgumentList "install","--quiet","--accept-license","--backend=wsl-2"
        Remove-Item $exe -Force -ErrorAction SilentlyContinue
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
    $dockerCmd = (Get-Command docker -ErrorAction SilentlyContinue).Source
}
if (-not $dockerCmd) {
    Write-Host "    Docker was installed but is not visible in this session." -ForegroundColor Red
    Write-Host "    Close this window, open a NEW PowerShell and run the installer again." -ForegroundColor Red
    exit 1
}

$null = & $dockerCmd info 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Starting Docker Desktop (the first start can take a few minutes)..."
    $dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dd) { Start-Process $dd } else { Write-Warn2 "Docker Desktop.exe not found at $dd" }
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 5
        $null = & $dockerCmd info 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        if ($i % 6 -eq 5) { Write-Host "      ...waiting for the Docker engine ($([int](($i + 1) * 5)) s)" }
    }
    if (-not $ready) {
        Write-Host "    The Docker engine did not start in time." -ForegroundColor Red
        Write-Host "    Start Docker Desktop manually and run this installer again." -ForegroundColor Red
        exit 1
    }
}
Write-Ok "Docker engine is ready"

# --- Phase 3/3: Project + docker compose ----------------------------------------
Write-Step "Phase 3/3: MetrixSense deployment"
Install-Project -ZipUrl $RepoZipUrl -DestDir $InstallDir
Set-Location $InstallDir
New-Item -ItemType Directory -Force -Path "backend\data","backend\files","backend\logs" | Out-Null

if (Test-PortBusy 8080) { Write-Warn2 "Port 8080 is already in use - the web UI may not open. Edit docker-compose.yml if needed." }
if (Test-PortBusy 8000) { Write-Warn2 "Port 8000 is already in use - stop the other application first." }

Write-Host "    Building images (5-10 minutes on first run)..."
$hasComposeV2 = $false
try { docker compose version *> $null; $hasComposeV2 = ($LASTEXITCODE -eq 0) } catch { }
if ($hasComposeV2) { docker compose up -d --build } else { docker-compose up -d --build }
if ($LASTEXITCODE -ne 0) {
    Write-Host "    'docker compose up' failed. Run it manually to see the full error:" -ForegroundColor Red
    Write-Host "      cd $InstallDir; docker compose up -d --build" -ForegroundColor Red
    exit 1
}

Write-Host "    Waiting for backend health..."
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 3
    try { Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; $ready = $true; break } catch { }
}
if ($ready) { Write-Ok "Backend is healthy" } else { Write-Warn2 "Backend hasn't reported healthy yet - check: docker compose logs -f" }

Start-Process "http://127.0.0.1:8080"

Write-Host ""
Write-Host "=== Installation complete! ===" -ForegroundColor Green
Write-Host "Web UI:      http://127.0.0.1:8080" -ForegroundColor Green
Write-Host "API docs:    http://127.0.0.1:8080/docs" -ForegroundColor Green
Write-Host "Project dir: $InstallDir"
Write-Host "Logs:        docker compose logs -f"
Write-Host ""
Write-Host "Known issues:" -ForegroundColor Yellow
Write-Host " - Ports busy -> edit docker-compose.yml (ports section)"
Write-Host " - Default password is public -> change DEFAULT_PASSWORD in backend\.env"
Write-Host ""
Read-Host "Installation finished. Press Enter to close this window"

