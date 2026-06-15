param(
    [string]$Name = $env:AIOPS_PROJECT_NAME,
    [string]$VenvDir = $env:AIOPS_VENV_DIR,
    [string]$CacheDir = $env:AIOPS_CACHE_DIR,
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-CommandOrNull {
    param([string]$CommandName)
    Get-Command $CommandName -ErrorAction SilentlyContinue
}

function Test-PythonVersion {
    param([string]$PythonCommand)
    & $PythonCommand -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" | Out-Null
    return $LASTEXITCODE -eq 0
}

function Get-PythonCommand {
    foreach ($candidate in @("py", "python", "python3")) {
        if ((Get-CommandOrNull $candidate) -and (Test-PythonVersion $candidate)) {
            return $candidate
        }
    }
    return $null
}

$PythonCommand = Get-PythonCommand
if (-not $PythonCommand) {
    if ($NoInstall) {
        throw "Python 3.10 or newer is required but was not found. Install Python manually, or re-run without -NoInstall."
    }

    if (Get-CommandOrNull "winget") {
        Write-Host "Installing Python 3 with winget..."
        winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
        $PythonCommand = Get-PythonCommand
    } else {
        throw "Python 3.10+ was not found, and winget is not available. Install Python from https://www.python.org/downloads/windows/ and re-run this script."
    }
}

if (-not $PythonCommand) {
    throw "Python installation completed, but Python is not on PATH. Restart PowerShell and re-run this script."
}

$SetupArgs = @()
if (-not [string]::IsNullOrWhiteSpace($Name)) {
    $SetupArgs += @("--name", $Name)
}
if (-not [string]::IsNullOrWhiteSpace($VenvDir)) {
    $SetupArgs += @("--venv-dir", $VenvDir)
}
if (-not [string]::IsNullOrWhiteSpace($CacheDir)) {
    $SetupArgs += @("--cache-dir", $CacheDir)
}

& $PythonCommand (Join-Path $ScriptDir "setup.py") @SetupArgs
