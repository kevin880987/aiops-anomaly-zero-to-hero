#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NO_INSTALL=0
SETUP_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-install)
      NO_INSTALL=1
      shift
      ;;
    *)
      SETUP_ARGS+=("$1")
      shift
      ;;
  esac
done

python_ok() {
  command -v python3 >/dev/null 2>&1 && python3 - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

if ! python_ok; then
  if [ "$NO_INSTALL" -eq 1 ]; then
    echo "Python 3.10 or newer is required but was not found."
    echo "Install Python manually, or re-run without --no-install."
    exit 1
  fi

  if [ "$(uname -s)" != "Darwin" ]; then
    echo "This bootstrap script only installs Python automatically on macOS."
    echo "On Linux, install Python 3.10+ with your system package manager, then run:"
    echo "  python3 getting-started/scripts/setup.py ..."
    exit 1
  fi

  if ! command -v brew >/dev/null 2>&1; then
    echo "Python 3.10+ was not found, and Homebrew is not installed."
    echo "Install Homebrew first: https://brew.sh/"
    exit 1
  fi

  echo "Installing Python with Homebrew..."
  brew install python
fi

exec python3 "$SCRIPT_DIR/setup.py" "${SETUP_ARGS[@]}"
