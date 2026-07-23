#!/usr/bin/env python3
"""Build the lab diagrams from their draw.io sources.

    python infra/build_diagrams.py            # rebuild every diagram
    python infra/build_diagrams.py --check    # fail if any export is out of date

`diagram/*.drawio` is the only source. The SVG files the notebooks display are
generated artifacts: editing one is a change that the next build silently
discards, which is how the exports drifted away from their sources in the first
place. Every label had ended up stated twice, once in the source and once in an
export nobody could regenerate.

The build has two stages. draw.io renders the SVG, then `svg_flatten` rewrites
each label as native SVG text.

That second stage exists because draw.io writes an HTML label into a
`<foreignObject>` and pairs it with a base64 PNG of the same label as a fallback
for renderers that cannot do foreignObject. The label therefore ships twice in
every export, and only one of the two is the text. JupyterLab and VS Code read
the foreignObject; GitHub's notebook viewer strips it and falls through to the
raster. Flattening leaves one copy that every renderer reads, and drops roughly
97% of the file size with it.

Requires the draw.io desktop application:

    brew install --cask drawio          # macOS
    https://github.com/jgraph/drawio-desktop/releases
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import svg_flatten  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO / "diagram"

# Which lab displays which diagram. Explicit rather than inferred, so that moving
# a diagram between labs is a visible edit here instead of a silent rename.
DESTINATIONS = {
    "lab00_observability_stack_arch": "labs/workshop/diagrams",
    "lab02_detection_methods": "labs/workshop/diagrams",
    "lab08_agentic_vs_llm": "labs/workshop/diagrams",
    "lab08_end_to_end_pipeline": "labs/workshop/diagrams",
    "aiops_pipeline_overview": "labs/self-study/diagrams",
    "lab01_feature_pipeline": "labs/self-study/diagrams",
    "lab02_pipeline_position": "labs/self-study/diagrams",
    "lab03_pipeline_position": "labs/self-study/diagrams",
    "lab04_pipeline_position": "labs/self-study/diagrams",
    "lab05_pipeline_position": "labs/self-study/diagrams",
    "lab06_pipeline_position": "labs/self-study/diagrams",
    "lab07_pipeline_position": "labs/self-study/diagrams",
    "lab08_pipeline_position": "labs/self-study/diagrams",
}


def drawio_binary() -> str | None:
    found = shutil.which("drawio")
    if found:
        return found
    mac = Path("/Applications/draw.io.app/Contents/MacOS/draw.io")
    return str(mac) if mac.exists() else None


def export(binary: str, source: Path, target: Path) -> bool:
    """Render one source to SVG, then flatten its labels."""
    with tempfile.TemporaryDirectory() as work:
        raw = Path(work) / f"{source.stem}.svg"
        result = subprocess.run(
            [binary, "-x", "-f", "svg", "-o", str(raw), str(source)],
            capture_output=True, text=True, timeout=300,
        )
        if not raw.exists():
            print(f"  {source.name}: draw.io export failed")
            for line in (result.stderr or result.stdout or "").splitlines()[-3:]:
                print(f"      {line}")
            return False

        flattened, labels = svg_flatten.convert(raw.read_text())
        before = len(raw.read_text()) / 1024
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(flattened)
        after = len(flattened) / 1024
        leftover = flattened.count("<switch>")
        print(f"  {source.name:<42} {labels:>3} labels  {before:>6.0f} KB -> {after:>5.0f} KB"
              + (f"   UNFLATTENED: {leftover}" if leftover else ""))
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="report drift without writing; exit non-zero if any export is stale")
    parser.add_argument("--only", help="build a single diagram by stem name")
    args = parser.parse_args()

    binary = drawio_binary()
    if not binary and not args.check:
        print("draw.io was not found. Install it, or edit the sources and ask")
        print("someone with it installed to run this script.")
        print("  brew install --cask drawio")
        return 1

    sources = sorted(SOURCE_DIR.glob("*.drawio"))
    if args.only:
        sources = [s for s in sources if s.stem == args.only]
    if not sources:
        print(f"no .drawio sources found in {SOURCE_DIR.relative_to(REPO)}")
        return 1

    stale, failed = [], []
    for source in sources:
        destination = DESTINATIONS.get(source.stem)
        if destination is None:
            print(f"  {source.name}: no destination registered in DESTINATIONS, skipped")
            continue
        target = REPO / destination / f"{source.stem}.svg"

        if args.check:
            if not target.exists():
                stale.append(f"{target.relative_to(REPO)} is missing")
            elif target.stat().st_mtime < source.stat().st_mtime:
                stale.append(f"{target.relative_to(REPO)} is older than its source")
            continue

        if not export(binary, source, target):
            failed.append(source.name)

    if args.check:
        for item in stale:
            print(f"  stale: {item}")
        print(f"{len(stale)} of {len(sources)} exports are out of date"
              if stale else f"all {len(sources)} exports are current")
        return 1 if stale else 0

    print()
    print(f"built {len(sources) - len(failed)} of {len(sources)} diagrams")
    if failed:
        print(f"failed: {', '.join(failed)}")
        return 1
    print("Validate sources with the check-drawio-layout skill before committing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
