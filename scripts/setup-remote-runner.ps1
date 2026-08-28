# One-line DevBox setup for the UI-automation self-hosted runner (fork-based model).
# Run this ONCE per DevBox in an Administrator PowerShell:
#   irm https://raw.githubusercontent.com/<your-handle>/UI-automation/main/scripts/setup-remote-runner.ps1 | iex

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# --- Admin check ---------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "This script must be run in an Administrator PowerShell."
}

Set-Location $HOME
$RepoPath = Join-Path $HOME 'UI-automation'

# --- Detect GitHub handle ------------------------------------------------
Write-Step "Resolving your GitHub handle..."
$GhHandle = $null

if (Test-Path (Join-Path $RepoPath '.git')) {
    Push-Location $RepoPath
    try {
        $originUrl = (git remote get-url origin 2>$null)
        if ($originUrl -and $originUrl -match 'github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)') {
            $detectedOwner = $Matches.owner
            if ($detectedOwner -eq 'william051200') {
                Write-Warn "Existing clone at $RepoPath points at the UPSTREAM repo (william051200)."
                Write-Host "    Choose:" -ForegroundColor Yellow
                Write-Host "      [F] Fork it now (opens the fork URL, then continue)"
                Write-Host "      [H] I already forked -- enter my handle"
                Write-Host "      [C] Cancel"
                $choice = Read-Host "Choice (F/H/C)"
                switch ($choice.ToUpper()) {
                    'F' {
                        Start-Process 'https://github.com/william051200/UI-automation/fork'
                        Read-Host "Press <Enter> after forking (make sure Actions is enabled on your fork)"
                        $GhHandle = Read-Host "Your GitHub handle (fork owner)"
                    }
                    'H' {
                        $GhHandle = Read-Host "Your GitHub handle (fork owner)"
                    }
                    default { throw "Cancelled by user." }
                }
            } else {
                $GhHandle = $detectedOwner
                Write-Ok "Detected handle from existing clone: $GhHandle"
            }
        }
    } finally {
        Pop-Location
    }
}

if (-not $GhHandle) {
    $GhHandle = Read-Host "Your GitHub handle (fork owner, e.g. octocat)"
    if (-not $GhHandle) { throw "GitHub handle is required." }
}

$Repo = "$GhHandle/UI-automation"
$RepoUrl = "https://github.com/$Repo.git"
Write-Ok "Target fork: $Repo"

# --- Ensure git is available (prerequisite) -----------------------------
Write-Step "Checking git..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "git is not installed and winget is unavailable. Install Git for Windows manually, then re-run."
    }
    Write-Warn "git missing; installing via winget..."
    winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements | Out-Null
    $env:Path = ([Environment]::GetEnvironmentVariable('Path','Machine')) + ';' + ([Environment]::GetEnvironmentVariable('Path','User'))
}
Write-Ok "git: $(git --version)"

# --- Clone or refresh the fork ------------------------------------------
Write-Step "Cloning/refreshing $Repo into $RepoPath..."
if (Test-Path (Join-Path $RepoPath '.git')) {
    Push-Location $RepoPath
    try {
        $currentUrl = (git remote get-url origin 2>$null).Trim()
        if ($currentUrl -ne $RepoUrl) {
            Write-Warn "Repointing origin from '$currentUrl' to '$RepoUrl'"
            git remote set-url origin $RepoUrl
        }
        git fetch origin main | Out-Host
        git checkout main | Out-Host
        git reset --hard origin/main | Out-Host
        Write-Ok "Clone refreshed."
    } finally {
        Pop-Location
    }
} else {
    git clone $RepoUrl $RepoPath | Out-Host
    Write-Ok "Cloned."
}

Set-Location $RepoPath

# --- Install uv + uv sync ------------------------------------------------
Write-Step "Ensuring uv is installed..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    irm https://astral.sh/uv/install.ps1 | iex
}
$env:Path = "$HOME\.local\bin;$env:Path"
Write-Ok "uv: $(uv --version)"

# Match UV_PROJECT_ENVIRONMENT in .github/workflows/run-ui-tests.yml so setup pre-warms the CI venv.
$projectSetup = Join-Path $RepoPath 'setup.ps1'
$projectEnvironment = 'C:\uv-venvs\ui-automation'
Write-Step "Installing Python dependencies (venv: $projectEnvironment)..."
& $projectSetup -EnvironmentPath $projectEnvironment
Write-Ok "Python environment ready."

# --- Compose the DevBox label -------------------------------------------
Write-Step "Composing your DevBox label..."
$today = (Get-Date -Format 'ddMMyyyy')
$suffix = Read-Host "Optional label suffix (leave blank for none, e.g. 'desk' or 'laptop')"

# Auto-increment N by scanning the workflow file for existing labels
# with the same date+suffix stem on this fork.
$workflow = Join-Path $RepoPath '.github/workflows/run-ui-tests.yml'
$stem = if ($suffix) { "$today-$suffix" } else { $today }
$n = 1
if (Test-Path $workflow) {
    $wfContent = Get-Content -Path $workflow -Raw
    $existing = [regex]::Matches($wfContent, "(?m)^\s*-\s+$([regex]::Escape($stem))-(\d+)\b")
    if ($existing.Count -gt 0) {
        $maxN = ($existing | ForEach-Object { [int]$_.Groups[1].Value } | Measure-Object -Maximum).Maximum
        $n = $maxN + 1
    }
}
$Label = "$stem-$n"
Write-Ok "Label: $Label"

# --- Prompt for token ----------------------------------------------------
Write-Step "Runner registration token"
Write-Host "    Open this URL in your BROWSER (on your laptop):" -ForegroundColor Yellow
Write-Host "      https://github.com/$Repo/settings/actions/runners/new?arch=x64&os=win" -ForegroundColor Cyan
Write-Host "    Copy the token shown next to './config.cmd --token ...' and paste it below." -ForegroundColor Yellow
Write-Host "    (Tokens expire in ~1 hour; grab it right before pasting.)" -ForegroundColor Yellow
$Token = Read-Host "Token"
if (-not $Token) { throw "No token provided." }

# --- Delegate to setup-runner.ps1 ---------------------------------------
Write-Step "Invoking scripts\setup-runner.ps1..."
$setupRunner = Join-Path $RepoPath 'scripts\setup-runner.ps1'
& $setupRunner -Label $Label -Repo $Repo -Token $Token -RepoPath $RepoPath
