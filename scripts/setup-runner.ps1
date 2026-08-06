<#
.SYNOPSIS
    Register the current DevBox as a self-hosted GitHub Actions runner
    for the UI-automation repository.

.DESCRIPTION
    One-time bootstrap. Run this ON YOUR DEVBOX (RDP'd, unlocked) once,
    then never again for that DevBox. After it completes, your DevBox
    is a runner reachable from the Actions tab, and any tester can
    trigger a workflow against it from a browser.

    What it does:
      1. Prompts for (or accepts) your DevBox label.
      2. Verifies uv, python, git are present (installs via winget if not).
      3. Downloads the latest actions/runner release.
      4. Configures it against the repo with your chosen label.
      5. Installs and starts it as a Windows service that survives reboots.

    You will need a runner registration token from the repo's
    Settings -> Actions -> Runners -> New self-hosted runner page.
    (Or pass -Token to skip the interactive prompt.)

.PARAMETER Label
    The label to register this runner under. Must follow the convention:
      <INITIALS>-<DDMMYYYY>-<N>
    e.g. ZY-24072026-1

.PARAMETER TesterName
    Your name (shown as a YAML comment next to the label in the workflow file).
    e.g. "Zun Yang"

.PARAMETER Repo
    The GitHub repo to register the runner against. In the fork-based
    model each tester runs this against their own fork
    (e.g. yourhandle/UI-automation). If omitted, the script auto-detects
    from `git remote get-url origin` on -RepoPath.

.PARAMETER Token
    Registration token from GitHub. If omitted, you'll be prompted with
    the URL to fetch it from.

.PARAMETER InstallRoot
    Directory to install the runner into. Default: C:\actions-runner

.PARAMETER RepoPath
    Local clone of the repo where the workflow file lives. The script
    edits .github/workflows/run-ui-tests.yml here to add your label.
    Default: $HOME\UI-automation

.PARAMETER OpenPR
    If set, the script will push the workflow edit and open a PR via `gh`.
    Requires `gh auth login` on this DevBox. Without this switch, the
    script edits the file locally and prints the git commands for you
    to run manually.

.EXAMPLE
    .\scripts\setup-runner.ps1 -Label ZY-24072026-1 -TesterName "Zun Yang"

.EXAMPLE
    .\scripts\setup-runner.ps1 -Label WN-24072026-1 -TesterName "William Ng" -OpenPR

.NOTES
    Must be run in an Administrator PowerShell (installing a Windows
    service requires elevation).
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Z]{2}-\d{8}-\d+$')]
    [string]$Label,

    [Parameter(Mandatory = $true)]
    [string]$TesterName,

    [string]$Repo,

    [string]$Token,

    [string]$InstallRoot = 'C:\actions-runner',

    # Path to the local clone of the repo (where the workflow file lives).
    [string]$RepoPath = (Join-Path $HOME 'UI-automation'),

    # If set, the script will push the workflow edit and open a PR via `gh`.
    # Requires `gh auth login` to be complete on this DevBox.
    [switch]$OpenPR
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# --- Admin check ----------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "This script must be run in an Administrator PowerShell."
}

# --- Resolve target repo (auto-detect from local clone if not given) -----
if (-not $Repo) {
    if (-not (Test-Path $RepoPath)) {
        throw "-Repo was not passed and -RepoPath '$RepoPath' does not exist. Clone your fork first, or pass -Repo <owner/name>."
    }
    Push-Location $RepoPath
    try {
        $originUrl = (git remote get-url origin 2>$null).Trim()
    } finally {
        Pop-Location
    }
    if (-not $originUrl) {
        throw "Could not read 'origin' remote in $RepoPath. Pass -Repo <owner/name> explicitly."
    }
    # Match https://github.com/<owner>/<repo>(.git)? or git@github.com:<owner>/<repo>(.git)?
    if ($originUrl -match 'github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)') {
        $Repo = "$($Matches.owner)/$($Matches.repo)"
    } else {
        throw "Could not parse GitHub owner/repo from origin URL '$originUrl'. Pass -Repo <owner/name> explicitly."
    }
    Write-Ok "Detected repo from origin: $Repo"
    if ($Repo -match '^william051200/') {
        Write-Warn "Origin points at the UPSTREAM repo. In the fork-based model you should register runners on YOUR fork, not upstream."
        Write-Warn "If this is intentional (e.g. you have admin on upstream), continue. Otherwise Ctrl+C, fork the repo, re-clone, and re-run."
    }
}

# --- Prereqs: uv, git, python --------------------------------------------
Write-Step "Checking prerequisites (uv, git, python)..."

function Ensure-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is not available. Install App Installer from the Microsoft Store, then re-run."
    }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Ensure-Winget
    Write-Warn "git missing; installing via winget..."
    winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements | Out-Null
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path','User')
}
Write-Ok "git: $(git --version)"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Warn "uv missing; installing from astral.sh..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$HOME\.local\bin;$env:Path"
}
Write-Ok "uv: $(uv --version)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    # uv will fetch python on first `uv sync`; nothing to install here.
    Write-Warn "python not on PATH — uv will provision one on first sync."
} else {
    Write-Ok "python: $(python --version)"
}

# --- Token ---------------------------------------------------------------
if (-not $Token) {
    Write-Host ""
    Write-Host "A runner registration token is required." -ForegroundColor Yellow
    Write-Host "Get one from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/$Repo/settings/actions/runners/new?arch=x64&os=win" -ForegroundColor Cyan
    Write-Host "Copy the token shown next to './config.cmd --token ...' and paste it here:"
    $Token = Read-Host -Prompt "Token" -AsSecureString |
        ForEach-Object { [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($_)) }
}
if (-not $Token) { throw "No token provided." }

# --- Download runner ------------------------------------------------------
Write-Step "Downloading latest actions/runner..."
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Set-Location $InstallRoot

$latest = Invoke-RestMethod https://api.github.com/repos/actions/runner/releases/latest
$asset  = $latest.assets | Where-Object { $_.name -like 'actions-runner-win-x64-*.zip' } | Select-Object -First 1
if (-not $asset) { throw "Could not find a Windows x64 runner asset in the latest release." }

$zip = Join-Path $InstallRoot $asset.name
if (-not (Test-Path $zip)) {
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip
}

if (-not (Test-Path (Join-Path $InstallRoot 'config.cmd'))) {
    Write-Step "Extracting runner..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $InstallRoot)
}

# --- Configure -----------------------------------------------------------
Write-Step "Configuring runner as '$Label' against $Repo..."
$runnerUrl = "https://github.com/$Repo"
& .\config.cmd `
    --url $runnerUrl `
    --token $Token `
    --name $Label `
    --labels $Label `
    --work "_work" `
    --unattended `
    --replace
if ($LASTEXITCODE -ne 0) { throw "config.cmd failed with exit code $LASTEXITCODE" }

# --- Install as Windows service ------------------------------------------
Write-Step "Installing runner as a Windows service..."
& .\svc.cmd install
& .\svc.cmd start
if ($LASTEXITCODE -ne 0) { throw "svc.cmd start failed with exit code $LASTEXITCODE" }

Write-Ok "Runner '$Label' installed and started as a Windows service."

# --- Update workflow YAML to expose this label in the dropdown ------------
Write-Step "Adding '$Label' to .github/workflows/run-ui-tests.yml..."

$workflow = Join-Path $RepoPath '.github/workflows/run-ui-tests.yml'
if (-not (Test-Path $workflow)) {
    Write-Warn "Workflow file not found at $workflow; skipping YAML edit."
    Write-Warn "Add '- $Label   # $TesterName' manually under target_devbox.options."
} else {
    $content = Get-Content -Path $workflow -Raw
    if ($content -match [regex]::Escape("- $Label")) {
        Write-Ok "Label '$Label' is already present in the workflow — nothing to do."
    } else {
        # Insert a new entry as the LAST line inside target_devbox.options.
        # Pattern: find the target_devbox: options: block, then the last
        # existing '          - XX-...' line before the next input (`quiet:`).
        $newLine = "          - $Label # $TesterName"
        $pattern = '(?ms)(target_devbox:.*?options:\s*\n(?:.*?\n)*?)((?:\s{10}- [A-Z]{2}-\d{8}-\d+.*\n)+)'
        $match = [regex]::Match($content, $pattern)
        if (-not $match.Success) {
            Write-Warn "Could not locate target_devbox.options block in $workflow."
            Write-Warn "Add '$newLine' manually under target_devbox.options."
        } else {
            $existingBlock = $match.Groups[2].Value
            $newBlock = $existingBlock.TrimEnd("`n") + "`n$newLine`n"
            $updated = $content.Substring(0, $match.Groups[2].Index) +
                       $newBlock +
                       $content.Substring($match.Groups[2].Index + $match.Groups[2].Length)
            Set-Content -Path $workflow -Value $updated -NoNewline
            Write-Ok "Added '$Label # $TesterName' to workflow."

            if ($OpenPR) {
                Write-Step "Committing, pushing, and opening a PR (via gh)..."
                Push-Location $RepoPath
                try {
                    $branch = "register-$($Label.ToLower())"
                    git checkout -b $branch 2>&1 | Out-Host
                    git add .github/workflows/run-ui-tests.yml
                    git commit -m "Register DevBox runner: $Label ($TesterName)" | Out-Host
                    git push -u origin $branch | Out-Host
                    gh pr create --fill --title "Register DevBox runner: $Label" `
                                 --body "Registers DevBox runner ``$Label`` for $TesterName. Automatically generated by scripts/setup-runner.ps1." | Out-Host
                    Write-Ok "PR opened. Merge it to expose '$Label' in the workflow dropdown."
                } catch {
                    Write-Warn "Auto-PR failed: $_"
                    Write-Warn "Push manually: git push origin $branch  &&  gh pr create --fill"
                } finally {
                    Pop-Location
                }
            } else {
                Write-Host ""
                Write-Warn "Workflow edited locally. To publish, run:"
                Write-Host "    cd $RepoPath" -ForegroundColor Yellow
                Write-Host "    git checkout -b register-$($Label.ToLower())" -ForegroundColor Yellow
                Write-Host "    git add .github/workflows/run-ui-tests.yml" -ForegroundColor Yellow
                Write-Host "    git commit -m ""Register DevBox runner: $Label ($TesterName)""" -ForegroundColor Yellow
                Write-Host "    git push -u origin register-$($Label.ToLower())" -ForegroundColor Yellow
                Write-Host "    gh pr create --fill" -ForegroundColor Yellow
                Write-Host "  (or re-run this script with -OpenPR to do all of that automatically)"
            }
        }
    }
}

Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Verify at: https://github.com/$Repo/settings/actions/runners"
Write-Host "     Your runner '$Label' should show status = Idle."
Write-Host "  2. If not yet done, merge the workflow PR to expose your label."
Write-Host "  3. Trigger a run from the Actions tab: pick a CSV + your label."
Write-Host ""