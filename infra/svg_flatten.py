"""Flatten a draw.io SVG export so each label exists exactly once.

Build step, not an editing tool. Run through infra/build_diagrams.py; never
run it against a hand-edited SVG, and never hand-edit its output.

A draw.io SVG export stores every label twice: once as HTML inside a
<foreignObject>, and once as a base64 PNG inside a sibling <image> that acts as
the fallback for renderers without foreignObject support. Editing the text edits
only the first copy. The raster keeps whatever the diagram said when it was
exported, so the two disagree, and which one a reader sees depends on their
renderer.

Native <text> removes the split. One copy, renders everywhere, and the files
lose the raster payload that made up most of their size.
"""
from __future__ import annotations

import html
import pathlib
import re
import sys

SWITCH = re.compile(r"<switch>(.*?)</switch>", re.S)
NOT_SVG_NOTICE = re.compile(
    r"<switch><g requiredFeatures=[^>]*/>.*?Text is not SVG.*?</switch>", re.S)
IMAGE = re.compile(r'<image\s+x="([\-\d.]+)"\s+y="([\-\d.]+)"\s+width="([\d.]+)"\s+height="([\d.]+)"')
INNER = re.compile(r'<div style="display: inline-block;[^"]*">(.*?)</div>\s*</div>\s*</div>', re.S)
FONTSZ = re.compile(r"font-size:\s*(\d+)px")
FONTFAM = re.compile(r"font-family:\s*([^;]+);")
JUSTIFY = re.compile(r"justify-content:\s*\w*\s*(\w+)")
INNER_ALIGN = re.compile(r'box-sizing: border-box;[^"]*text-align:\s*(\w+)')
COLOR = re.compile(r"color:\s*light-dark\(([^,]+),")


def lines_from(fragment: str) -> list[str]:
    """Split the label on <br>, strip markup, unescape entities."""
    parts = re.split(r"<br\s*/?>", fragment)
    out = []
    for part in parts:
        text = re.sub(r"<[^>]+>", "", part)
        text = html.unescape(text).strip()
        if text:
            out.append(text)
    return out


def text_width(s: str, size: int) -> float:
    """Approximate rendered width. CJK is full-width, Latin averages 0.6 em in Georgia."""
    total = 0.0
    for ch in s:
        cp = ord(ch)
        wide = 0x2E80 <= cp <= 0x9FFF or 0xAC00 <= cp <= 0xD7AF or 0xFF00 <= cp <= 0xFF60
        total += size * (1.0 if wide else 0.6)
    return total


def wrap(lines: list[str], width: float, size: int) -> list[str]:
    """Soft-wrap to the label box.

    draw.io's foreignObject wraps long text against the shape width; native SVG
    text does not, so a sentence that used to occupy three lines would run off
    the diagram. Wrapping here restores the original layout.
    """
    if width <= 0:
        return lines
    out: list[str] = []
    for line in lines:
        if text_width(line, size) <= width:
            out.append(line)
            continue
        current = ""
        for word in line.split(" "):
            candidate = f"{current} {word}".strip()
            if current and text_width(candidate, size) > width:
                out.append(current)
                current = word
            else:
                current = candidate
        if current:
            out.append(current)
    return out


RECT = re.compile(r'<rect\s+x="([\-\d.]+)"\s+y="([\-\d.]+)"\s+width="([\d.]+)"\s+height="([\d.]+)"[^>]*fill="(?!none)')


def filled_boxes(svg: str) -> list[tuple[float, float, float, float]]:
    """Bounding boxes of every filled shape, used to tell a shape label from an edge label."""
    return [tuple(float(g) for g in m.groups()[:4]) for m in RECT.finditer(svg)]


def inside_a_shape(cx: float, cy: float, boxes) -> bool:
    return any(bx <= cx <= bx + bw and by <= cy <= by + bh for bx, by, bw, bh in boxes)


def convert(svg: str) -> tuple[str, int]:
    converted = 0
    boxes = filled_boxes(svg)

    def replace(match: re.Match) -> str:
        nonlocal converted
        block = match.group(1)
        image = IMAGE.search(block)
        inner = INNER.search(block)
        if not (image and inner):
            return match.group(0)

        x, y, w, h = (float(g) for g in image.groups())
        lines = lines_from(inner.group(1))
        if not lines:
            return match.group(0)

        size = int((FONTSZ.search(block[block.find("inline-block"):]) or ["", "14"])[1])

        # The raster's height records how many lines draw.io actually laid out.
        # More lines than there are <br> tags means it soft-wrapped, and only
        # then should this converter wrap too. Guessing from an estimated glyph
        # width alone over-wraps short labels.
        expected = max(1, round(h / (size * 1.2)))
        if expected > len(lines):
            lines = wrap(lines, w - size * 0.6, size)
        family = (FONTFAM.search(block) or ["", "Georgia"])[1].strip()
        colour = (COLOR.search(block) or ["", "#000000"])[1].strip()
        centred = (JUSTIFY.search(block) or ["", "center"])[1] == "center"
        align = (INNER_ALIGN.search(block) or ["", "center"])[1]

        anchor = "middle" if (centred and align == "center") else "start"
        text_x = x + w / 2 if anchor == "middle" else x
        leading = size * 1.2
        first = y + h / 2 - leading * (len(lines) - 1) / 2 + size * 0.35

        spans = "".join(
            f'<tspan x="{text_x:.2f}" y="{first + i * leading:.2f}">{html.escape(line)}</tspan>'
            for i, line in enumerate(lines)
        )
        converted += 1
        # draw.io baked an opaque backing into the raster so a connector would not
        # be drawn through an edge label. Native text has no backing, so a
        # painted-under white stroke does the same job. Only edge labels need it;
        # putting a halo on a label that sits inside a filled shape would show as
        # a visible outline against the fill.
        halo = ""
        if not inside_a_shape(x + w / 2, y + h / 2, boxes):
            halo = ' stroke="#ffffff" stroke-width="3" paint-order="stroke" stroke-linejoin="round"'
        return (
            f'<text text-anchor="{anchor}" font-family="{family}" font-size="{size}px" '
            f'fill="{colour}"{halo} style="pointer-events:none">{spans}</text>'
        )

    svg = SWITCH.sub(replace, svg)

    # draw.io appends a "Text is not SVG - cannot display" notice for renderers
    # without foreignObject support. Every label is native text now, so the
    # notice is false and would appear on exactly the renderers this step fixed.
    svg = NOT_SVG_NOTICE.sub("", svg)
    return svg, converted


def main(paths: list[str]) -> int:
    for name in paths:
        p = pathlib.Path(name)
        original = p.read_text()
        new, n = convert(original)
        remaining = new.count("<switch>")
        before, after = len(original) / 1024, len(new) / 1024
        p.write_text(new)
        print(f"{p.name:<40} {n:>3} labels  {before:>7.0f} KB -> {after:>5.0f} KB"
              f"  ({100 * (1 - after / before):.0f}% smaller)"
              + (f"  UNCONVERTED: {remaining}" if remaining else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
