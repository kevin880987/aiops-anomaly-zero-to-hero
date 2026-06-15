#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


MIN_PYTHON = (3, 10)
SCRIPT_DIR = Path(__file__).resolve().parent
AIOPS_ROOT = SCRIPT_DIR.parent.parent
REPO_ROOT = AIOPS_ROOT.parent.parent


def require_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        version = ".".join(map(str, MIN_PYTHON))
        raise SystemExit(f"Python {version} or newer is required.")


def required_value(parser: argparse.ArgumentParser, value: str | None, label: str, env_name: str) -> str:
    if value:
        return value
    parser.error(f"{label} is required. Provide the option or set {env_name}.")


def kernel_name(project_name: str) -> str:
    name = re.sub(r"[^a-z0-9_.-]", "", re.sub(r"\s+", "-", project_name.lower()))
    if not name:
        raise SystemExit("Project name must contain at least one letter, number, dot, underscore, or hyphen.")
    return name


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(command: list[str | os.PathLike[str]]) -> None:
    subprocess.check_call([str(part) for part in command], cwd=REPO_ROOT)


def parse_version(version: str) -> tuple[int | str, ...]:
    parts: list[int | str] = []
    for piece in re.split(r"[.+_-]", version):
        match = re.match(r"^(\d+)", piece)
        if match:
            parts.append(int(match.group(1)))
        elif piece:
            parts.append(piece)
    return tuple(parts)


def version_meets(installed: str, required: str) -> bool:
    installed_parts = parse_version(installed)
    required_parts = parse_version(required)
    length = max(len(installed_parts), len(required_parts))
    installed_padded = installed_parts + (0,) * (length - len(installed_parts))
    required_padded = required_parts + (0,) * (length - len(required_parts))
    return installed_padded >= required_padded


def read_minimum_requirements(requirements: Path) -> list[tuple[str, str, str]]:
    parsed: list[tuple[str, str, str]] = []
    for line_number, raw_line in enumerate(requirements.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*>=\s*([A-Za-z0-9_.!+*-]+)", line)
        if not match:
            raise SystemExit(
                f"Unsupported requirement format at {requirements}:{line_number}: {raw_line!r}. "
                "This setup script supports pinned minimums such as package>=1.2."
            )
        package, minimum = match.groups()
        parsed.append((package, minimum, line))
    return parsed


def installed_version(python: Path, package: str) -> str | None:
    code = (
        "import importlib.metadata as m\n"
        "import sys\n"
        "try:\n"
        f"    print(m.version({package!r}))\n"
        "except m.PackageNotFoundError:\n"
        "    sys.exit(1)\n"
    )
    result = subprocess.run([str(python), "-c", code], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def install_missing_or_old_requirements(python: Path, requirements: Path) -> None:
    to_install: list[str] = []
    for package, minimum, requirement in read_minimum_requirements(requirements):
        current = installed_version(python, package)
        if current is None:
            print(f"{package}: not installed; will install {requirement}")
            to_install.append(requirement)
        elif version_meets(current, minimum):
            print(f"{package}: {current} meets >= {minimum}; skipping")
        else:
            print(f"{package}: {current} is below {minimum}; will update")
            to_install.append(requirement)

    if to_install:
        run([python, "-m", "pip", "install", *to_install])
    else:
        print("All Python package requirements already meet minimum versions; skipping pip install.")


def main() -> None:
    require_python_version()

    parser = argparse.ArgumentParser(description="Create the Python environment and Jupyter kernel.")
    parser.add_argument("--name", default=os.environ.get("AIOPS_PROJECT_NAME"), help="Project/kernel name.")
    parser.add_argument("--venv-dir", default=os.environ.get("AIOPS_VENV_DIR"), help="Python virtual environment directory.")
    parser.add_argument("--cache-dir", default=os.environ.get("AIOPS_CACHE_DIR"), help="Matplotlib/Fontconfig cache directory.")
    args = parser.parse_args()

    project_name = required_value(parser, args.name, "Project/kernel name", "AIOPS_PROJECT_NAME")
    venv_dir = Path(required_value(parser, args.venv_dir, "Virtual environment directory", "AIOPS_VENV_DIR")).expanduser().resolve()
    cache_dir = Path(required_value(parser, args.cache_dir, "Cache directory", "AIOPS_CACHE_DIR")).expanduser().resolve()

    requirements = REPO_ROOT / "requirements.txt"
    if not requirements.exists():
        raise SystemExit(f"Cannot find requirements file: {requirements}")

    print(f"AIOps root: {AIOPS_ROOT}")
    print(f"Repository root: {REPO_ROOT}")
    print(f"Project name: {project_name}")
    print(f"Virtual environment: {venv_dir}")
    print(f"Cache directory: {cache_dir}")

    try:
        conda = subprocess.check_output(["conda", "--version"], text=True).strip()
        print(f"Conda detected: {conda}")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Conda not detected; continuing with Python venv.")

    if not venv_dir.exists():
        print(f"Creating virtual environment: {venv_dir}")
        venv_dir.parent.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "-m", "venv", venv_dir])
    else:
        print(f"Virtual environment already exists: {venv_dir}")

    cache_dir.joinpath("matplotlib").mkdir(parents=True, exist_ok=True)
    cache_dir.joinpath("fontconfig").mkdir(parents=True, exist_ok=True)

    python = venv_python(venv_dir)
    install_missing_or_old_requirements(python, requirements)
    run([
        python,
        "-m",
        "ipykernel",
        "install",
        "--user",
        "--name",
        kernel_name(project_name),
        "--display-name",
        f"Python ({project_name})",
    ])

    print()
    print("Setup complete.")
    print("Next step:")
    launcher = "py" if os.name == "nt" else "python3"
    print(
        f"  {launcher} getting-started/scripts/start_jupyter.py "
        f"--venv-dir \"{venv_dir}\" "
        f"--cache-dir \"{cache_dir}\" "
        "--jupyter-dir \"notebooks\""
    )


if __name__ == "__main__":
    main()
