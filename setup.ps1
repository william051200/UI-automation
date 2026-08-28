# setup.ps1 - Install project dependencies into a uv-managed environment.
#
# Defaults to the bundled wheelhouse because files.pythonhosted.org may be
# unavailable. Use -DependencyMode Online when direct package access is usable.
[CmdletBinding()]
param(
    [ValidateSet('Online', 'Wheelhouse')]
    [string]$DependencyMode = 'Wheelhouse',

    [string]$EnvironmentPath = (Join-Path $PSScriptRoot '.venv'),

    [string]$WheelhouseZip = (Join-Path $PSScriptRoot 'ui-auto-wheelhouse.zip'),

    [string]$WheelhouseSha256 = '3E637739F4001B8B79C88CC73511597987B0515B0A6E06BE06468D8B82E8973A'
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv not found on PATH. Run install.ps1 instead, or: irm https://astral.sh/uv/install.ps1 | iex'
}

switch ($DependencyMode) {
    'Online' {
        $previousProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT
        try {
            $env:UV_PROJECT_ENVIRONMENT = $EnvironmentPath
            Write-Host "Installing dependencies from the online package index into $EnvironmentPath..."
            uv sync
            if ($LASTEXITCODE -ne 0) {
                throw "uv sync failed with exit code $LASTEXITCODE."
            }
        } finally {
            if ($null -eq $previousProjectEnvironment) {
                Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
            } else {
                $env:UV_PROJECT_ENVIRONMENT = $previousProjectEnvironment
            }
        }
    }

    'Wheelhouse' {
        if (-not (Test-Path -LiteralPath $WheelhouseZip -PathType Leaf)) {
            throw "Wheelhouse archive not found: $WheelhouseZip"
        }

        $actualHash = (Get-FileHash -LiteralPath $WheelhouseZip -Algorithm SHA256).Hash
        if ($actualHash -ne $WheelhouseSha256) {
            throw "Wheelhouse SHA-256 mismatch. Expected $WheelhouseSha256, got $actualHash."
        }

        uv python find 3.12 --no-python-downloads *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Python 3.12 is not installed; installing it with uv...'
            uv python install 3.12
            if ($LASTEXITCODE -ne 0) {
                throw "uv could not install Python 3.12 (exit code $LASTEXITCODE)."
            }
        }

        $temporaryWheelhouse = Join-Path ([IO.Path]::GetTempPath()) "ui-auto-wheelhouse-$([guid]::NewGuid())"
        try {
            Write-Host "Extracting verified wheelhouse archive..."
            Expand-Archive -LiteralPath $WheelhouseZip -DestinationPath $temporaryWheelhouse

            Write-Host "Creating Python 3.12 environment at $EnvironmentPath..."
            uv venv $EnvironmentPath --python 3.12 --no-python-downloads --clear
            if ($LASTEXITCODE -ne 0) {
                throw "uv venv failed with exit code $LASTEXITCODE."
            }

            Write-Host 'Installing dependencies from the offline wheelhouse...'
            uv pip sync `
                --python (Join-Path $EnvironmentPath 'Scripts\python.exe') `
                --no-index `
                --find-links $temporaryWheelhouse `
                (Join-Path $PSScriptRoot 'requirements.lock.txt')
            if ($LASTEXITCODE -ne 0) {
                throw "uv pip sync failed with exit code $LASTEXITCODE."
            }
        } finally {
            if (Test-Path -LiteralPath $temporaryWheelhouse) {
                Remove-Item -LiteralPath $temporaryWheelhouse -Recurse -Force
            }
        }
    }
}

Write-Host "Environment ready: $EnvironmentPath"
Write-Host 'Run: uv run python run_test.py test_cases\powershell_echo_loop.csv'
