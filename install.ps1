# install.ps1 — One-line bootstrap for UI-automation.
#
# Usage on a fresh Windows 10/11 machine:
#   irm https://raw.githubusercontent.com/william051200/UI-automation/main/install.ps1 | iex
#
# If your execution policy blocks scripts, use:
#   powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/william051200/UI-automation/main/install.ps1 | iex"

$ErrorActionPreference = "Stop"

# Where to install the repo.
$RepoUrl  = "https://github.com/william051200/UI-automation.git"
$RepoDir  = Join-Path $HOME "UI-automation"
$UvBinDir = Join-Path $HOME ".local\bin"
$UvExe    = Join-Path $UvBinDir "uv.exe"

function Write-Step($msg)  { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "    $msg" -ForegroundColor Yellow }

function Add-ToSessionPath($dir) {
    if (-not ($env:Path -split ';' | Where-Object { $_ -ieq $dir })) {
        $env:Path = "$dir;$env:Path"
    }
}

# 1. uv ------------------------------------------------------------------
Write-Step "Checking for uv..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    if (Test-Path $UvExe) {
        Add-ToSessionPath $UvBinDir
        Write-Ok "Found uv at $UvExe (added to PATH for this session)"
    } else {
        Write-Warn "uv not found. Installing from astral.sh..."
        irm https://astral.sh/uv/install.ps1 | iex
        Add-ToSessionPath $UvBinDir
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            throw "uv installed but not on PATH. Open a new PowerShell and retry."
        }
        Write-Ok "uv installed."
    }
} else {
    Write-Ok "uv already installed: $((uv --version) 2>&1)"
}

# 2. git ------------------------------------------------------------------
Write-Step "Checking for git..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "git not found. Installing via winget..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Neither git nor winget is available. Install Git manually from https://git-scm.com/ and re-run."
    }
    winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements
    # winget puts git in a per-machine path; refresh from registry.
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "git installed but not on PATH. Open a new PowerShell and retry."
    }
    Write-Ok "git installed."
} else {
    Write-Ok "git already installed: $((git --version) 2>&1)"
}

# 3. Repo -----------------------------------------------------------------
Write-Step "Fetching repo into $RepoDir..."
if (Test-Path (Join-Path $RepoDir ".git")) {
    Push-Location $RepoDir
    git pull --ff-only
    Pop-Location
    Write-Ok "Repo updated (git pull)."
} else {
    if (Test-Path $RepoDir) {
        throw "$RepoDir exists but is not a git repo. Move/delete it and re-run."
    }
    git clone $RepoUrl $RepoDir
    Write-Ok "Repo cloned."
}

# 4. Python environment ---------------------------------------------------
Write-Step "Installing Python interpreter + dependencies..."
& (Join-Path $RepoDir 'setup.ps1')
Write-Ok "Environment ready."

# 5. Done -----------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " UI-automation is installed at: $RepoDir" -ForegroundColor Green
Write-Host ""
Write-Host " Run the example scenario:" -ForegroundColor Green
Write-Host "   cd `"$RepoDir`"" -ForegroundColor White
Write-Host "   uv run python run_test.py test_cases\powershell_echo_loop.csv" -ForegroundColor White
Write-Host ""
Write-Host " Note: that test will momentarily take control of your" -ForegroundColor Green
Write-Host " mouse/keyboard to open and drive PowerShell." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
