#!/usr/bin/env bash
# Bootstrap for aiops-anomaly-zero-to-hero - macOS
# Creates or verifies the conda environment, then launches JupyterLab.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_NAME="aiops-anomaly-zero-to-hero"
ENV_FILE="$REPO_ROOT/environment.yml"
LAB_DIR="$REPO_ROOT/labs"
MIN_PYTHON="3.12"

NO_INSTALL=0
FORCE_UPDATE=0
NO_LAUNCH=0

usage() {
  cat <<EOF
Usage: bash labs/getting-started/scripts/bootstrap_macos.sh [options]

Options:
  --no-install    Do not install Miniconda if conda is missing.
  --update        Force conda env update from environment.yml.
  --no-launch     Prepare the environment but do not start JupyterLab.
  -h, --help      Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-install) NO_INSTALL=1 ;;
    --update) FORCE_UPDATE=1 ;;
    --no-launch) NO_LAUNCH=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
  shift
done

info() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

fail() {
  echo ""
  echo "Setup stopped: $*" >&2
  exit 1
}

find_conda() {
  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return 0
  fi

  for candidate in \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/miniforge3/bin/conda" \
    "$HOME/mambaforge/bin/conda" \
    "/opt/homebrew/Caskroom/miniconda/base/bin/conda" \
    "/usr/local/Caskroom/miniconda/base/bin/conda"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

env_exists() {
  "$CONDA" env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"
}

env_is_ready() {
  "$CONDA" run -n "$ENV_NAME" python - <<PY >/dev/null 2>&1
from importlib import metadata
import importlib.util
import sys

if sys.version_info < tuple(map(int, "$MIN_PYTHON".split("."))):
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
PY
}

install_miniconda() {
  [ "$NO_INSTALL" -eq 0 ] || fail "conda was not found. Install Miniconda, then run this script again."
  command -v curl >/dev/null 2>&1 || fail "curl is required to download Miniconda."

  case "$(uname -s)" in
    Darwin) ;;
    *) fail "This script is for macOS. Use the Linux or Windows setup guide on those platforms." ;;
  esac

  local tmp arch pkg target
  tmp="$(mktemp -d)"
  arch="$(uname -m)"
  target="$HOME/miniconda3"

  if [ "$arch" = "arm64" ]; then
    pkg="Miniconda3-latest-MacOSX-arm64.sh"
  elif [ "$arch" = "x86_64" ]; then
    pkg="Miniconda3-latest-MacOSX-x86_64.sh"
  else
    rm -rf "$tmp"
    fail "Unsupported macOS CPU architecture: $arch"
  fi

  if [ -e "$target" ]; then
    rm -rf "$tmp"
    fail "$target already exists but conda was not found. Fix PATH or remove the broken directory."
  fi

  info "Downloading Miniconda for macOS $arch..."
  curl -fsSL "https://repo.anaconda.com/miniconda/$pkg" -o "$tmp/miniconda.sh" \
    || { rm -rf "$tmp"; fail "Could not download Miniconda. Check your network and try again."; }

  info "Installing Miniconda to $target..."
  bash "$tmp/miniconda.sh" -b -p "$target" \
    || { rm -rf "$tmp"; fail "Miniconda installer failed."; }
  rm -rf "$tmp"

  CONDA="$target/bin/conda"
  "$CONDA" init zsh >/dev/null 2>&1 || true
  "$CONDA" init bash >/dev/null 2>&1 || true
}

[ -f "$ENV_FILE" ] || fail "environment.yml not found at $ENV_FILE. Run this script from the project checkout."
[ -d "$LAB_DIR" ] || fail "Lab directory not found at $LAB_DIR."

case "$(uname -s)" in
  Darwin) ;;
  *) fail "This script is for macOS. Use the Linux or Windows setup guide on those platforms." ;;
esac

if CONDA="$(find_conda)"; then
  info "Using conda: $CONDA"
else
  info "conda not found."
  install_miniconda
fi

"$CONDA" --version >/dev/null || fail "conda exists but is not runnable: $CONDA"

if env_exists; then
  if [ "$FORCE_UPDATE" -eq 1 ]; then
    info "Environment '$ENV_NAME' exists; updating because --update was requested."
    "$CONDA" env update -n "$ENV_NAME" -f "$ENV_FILE" --prune \
      || fail "conda env update failed."
  elif env_is_ready; then
    info "Environment '$ENV_NAME' already satisfies the course requirements; skipping update."
  else
    info "Environment '$ENV_NAME' exists but is missing required packages or Python >= $MIN_PYTHON; updating."
    "$CONDA" env update -n "$ENV_NAME" -f "$ENV_FILE" --prune \
      || fail "conda env update failed."
  fi
else
  info "Creating environment '$ENV_NAME' from environment.yml."
  "$CONDA" env create -f "$ENV_FILE" \
    || fail "conda env create failed. Check the error above, then rerun with --update if the environment was partially created."
fi

env_is_ready || fail "Environment was created but validation failed. Run: $CONDA env update -n $ENV_NAME -f $ENV_FILE --prune"

info "Running repository setup validation..."
"$CONDA" run -n "$ENV_NAME" python "$REPO_ROOT/labs/getting-started/scripts/validate_setup.py" \
  || fail "Repository validation failed. Fix the issue above, then rerun this script."

echo ""
echo "Environment ready."
echo ""
echo "To open labs, run:"
echo "  conda activate $ENV_NAME"
echo "  jupyter lab \"$LAB_DIR\""
echo ""

if [ "$NO_LAUNCH" -eq 1 ]; then
  echo "Launch skipped because --no-launch was used."
  exit 0
fi

echo "Launching now..."
"$CONDA" run -n "$ENV_NAME" --no-capture-output jupyter lab "$LAB_DIR" \
  || fail "JupyterLab failed to start. Try: conda run -n $ENV_NAME jupyter lab \"$LAB_DIR\""
