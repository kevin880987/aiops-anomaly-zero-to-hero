# Bootstrap for aiops-anomaly-zero-to-hero — Windows
# Creates or verifies the conda environment, then launches JupyterLab.
# Usage: powershell -ExecutionPolicy Bypass -File bootstrap_windows.ps1
param(
    [switch]$NoInstall,
    [switch]$Update,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$EnvName  = "aiops-anomaly-zero-to-hero"
$EnvFile  = Join-Path $RepoRoot "environment.yml"
$LabDir = Join-Path $RepoRoot "labs"
$MinPython = [Version]"3.12"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "[$(Get-Date -Format HH:mm:ss)] $Message"
}

function Stop-Setup {
    param([string]$Message)
    throw "Setup stopped: $Message"
}

if (-not (Test-Path $EnvFile)) {
    Stop-Setup "environment.yml not found at $EnvFile. Run this script from the project checkout."
}
if (-not (Test-Path $LabDir)) {
    Stop-Setup "Lab directory not found at $LabDir."
}

function Find-Conda {
    $cmd = Get-Command "conda" -ErrorAction SilentlyContinue
    if ($cmd) { return "conda" }

    $candidates = @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\miniconda3\condabin\conda.bat",
        "$env:USERPROFILE\miniforge3\Scripts\conda.exe",
        "$env:USERPROFILE\miniforge3\condabin\conda.bat",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\condabin\conda.bat",
        "$env:LOCALAPPDATA\miniforge3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniforge3\condabin\conda.bat",
        "$env:ProgramData\miniconda3\Scripts\conda.exe",
        "$env:ProgramData\miniconda3\condabin\conda.bat",
        "$env:ProgramData\miniforge3\Scripts\conda.exe",
        "$env:ProgramData\miniforge3\condabin\conda.bat"
    )

    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

function Test-CondaEnvExists {
    param([string]$CondaPath, [string]$Name)
    $json = & $CondaPath env list --json
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "Could not list conda environments."
    }
    $envs = ($json | ConvertFrom-Json).envs
    foreach ($envPath in $envs) {
        if ((Split-Path $envPath -Leaf) -eq $Name) { return $true }
    }
    return $false
}

function Test-EnvReady {
    param([string]$CondaPath, [string]$Name)

    $code = @"
from importlib import metadata
import importlib.util
import sys

if sys.version_info < (3, 12):
    raise SystemExit(1)

required_modules = ["numpy", "pandas", "sklearn", "matplotlib", "jupyterlab", "ipykernel", "prometheus_client"]
missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit(1)

minimum_versions = {
    "numpy": "1.26",
    "pandas": "2.0",
    "scikit-learn": "1.4",
    "matplotlib": "3.9",
    "jupyterlab": "4.3",
    "ipykernel": "6.29",
    "prometheus-client": "0.20",
}

def version_tuple(value):
    parts = []
    for part in value.replace("-", ".").split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            digits = "".join(ch for ch in part if ch.isdigit())
            if digits:
                parts.append(int(digits))
            break
    return tuple(parts)

for package, minimum in minimum_versions.items():
    if version_tuple(metadata.version(package)) < version_tuple(minimum):
        raise SystemExit(1)
"@

    & $CondaPath run -n $Name python -c $code *> $null
    return ($LASTEXITCODE -eq 0)
}

$Conda = Find-Conda
if (-not $Conda) {
    if ($NoInstall) {
        Stop-Setup "conda not found. Install Miniconda from https://docs.conda.io/en/latest/miniconda.html and re-run."
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Stop-Setup "conda not found and winget is unavailable. Install Miniconda manually: https://docs.conda.io/en/latest/miniconda.html"
    }
    Write-Step "Installing Miniconda via winget..."
    winget install --exact --id Anaconda.Miniconda3 --source winget `
        --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "winget failed to install Miniconda. Install it manually, then rerun this script."
    }

    $Conda = Find-Conda
    if (-not $Conda) {
        Stop-Setup "Miniconda installed but conda is not visible yet. Restart PowerShell and re-run."
    }
}

& $Conda --version *> $null
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "conda exists but is not runnable: $Conda"
}

Write-Step "Using conda: $Conda"

if (Test-CondaEnvExists -CondaPath $Conda -Name $EnvName) {
    if ($Update) {
        Write-Step "Environment '$EnvName' exists; updating because -Update was requested."
        & $Conda env update -n $EnvName -f $EnvFile --prune
        if ($LASTEXITCODE -ne 0) { Stop-Setup "conda env update failed." }
    } elseif (Test-EnvReady -CondaPath $Conda -Name $EnvName) {
        Write-Step "Environment '$EnvName' already satisfies the course requirements; skipping update."
    } else {
        Write-Step "Environment '$EnvName' exists but is missing required packages or Python >= $MinPython; updating."
        & $Conda env update -n $EnvName -f $EnvFile --prune
        if ($LASTEXITCODE -ne 0) { Stop-Setup "conda env update failed." }
    }
} else {
    Write-Step "Creating environment '$EnvName' from environment.yml."
    & $Conda env create -f $EnvFile
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "conda env create failed. Check the error above, then rerun with -Update if the environment was partially created."
    }
}

if (-not (Test-EnvReady -CondaPath $Conda -Name $EnvName)) {
    Stop-Setup "Environment was created but validation failed. Run: conda env update -n $EnvName -f `"$EnvFile`" --prune"
}

Write-Step "Running repository setup validation..."
& $Conda run -n $EnvName python (Join-Path $PSScriptRoot "validate_setup.py")
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "Repository validation failed. Fix the issue above, then rerun this script."
}

Write-Host ""
Write-Host "Environment ready."
Write-Host ""
Write-Host "To open labs, run:"
Write-Host "  conda activate $EnvName"
Write-Host "  jupyter lab `"$LabDir`""
Write-Host ""

if ($NoLaunch) {
    Write-Host "Launch skipped because -NoLaunch was used."
    exit 0
}

Write-Host "Launching now..."
& $Conda run -n $EnvName --no-capture-output jupyter lab "$LabDir"
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "JupyterLab failed to start. Try: conda run -n $EnvName jupyter lab `"$LabDir`""
}
