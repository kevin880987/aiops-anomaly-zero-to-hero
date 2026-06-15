#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
AIOPS_ROOT = SCRIPT_DIR.parent.parent
REPO_ROOT = AIOPS_ROOT.parent.parent


def required_value(parser: argparse.ArgumentParser, value: str | None, label: str, env_name: str) -> str:
    if value:
        return value
    parser.error(f"{label} is required. Provide the option or set {env_name}.")


def jupyter_executable(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "jupyter.exe"
    return venv_dir / "bin" / "jupyter"


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch JupyterLab for the AIOps notebooks.")
    parser.add_argument("--venv-dir", default=os.environ.get("AIOPS_VENV_DIR"), help="Python virtual environment directory.")
    parser.add_argument("--cache-dir", default=os.environ.get("AIOPS_CACHE_DIR"), help="Matplotlib/Fontconfig cache directory.")
    parser.add_argument("--jupyter-dir", default=os.environ.get("AIOPS_JUPYTER_DIR"), help="Directory opened by JupyterLab.")
    args = parser.parse_args()

    venv_dir = Path(required_value(parser, args.venv_dir, "Virtual environment directory", "AIOPS_VENV_DIR")).expanduser().resolve()
    cache_dir = Path(required_value(parser, args.cache_dir, "Cache directory", "AIOPS_CACHE_DIR")).expanduser().resolve()
    jupyter_dir = Path(required_value(parser, args.jupyter_dir, "Jupyter directory", "AIOPS_JUPYTER_DIR")).expanduser()
    if not jupyter_dir.is_absolute():
        jupyter_dir = (AIOPS_ROOT / jupyter_dir).resolve()
    else:
        jupyter_dir = jupyter_dir.resolve()

    jupyter = jupyter_executable(venv_dir)
    if not jupyter.exists():
        raise SystemExit(f"JupyterLab is not installed in {venv_dir}. Run getting-started/scripts/setup.py first.")
    if not jupyter_dir.exists():
        raise SystemExit(f"Jupyter directory does not exist: {jupyter_dir}")

    cache_dir.joinpath("matplotlib").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MPLCONFIGDIR"] = str(cache_dir / "matplotlib")
    env["XDG_CACHE_HOME"] = str(cache_dir)

    subprocess.check_call([str(jupyter), "lab", str(jupyter_dir)], cwd=REPO_ROOT, env=env)


if __name__ == "__main__":
    main()
