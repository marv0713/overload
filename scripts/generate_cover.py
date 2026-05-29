#!/usr/bin/env python3
"""Generate a WeChat article cover image.

WeChat displays cover images in two contexts:
  - Article list thumbnail : square crop from the horizontal center
  - Subscription feed      : 2.35:1 crop (centre 383 px of the 500 px height)

Canvas is 900×500 (WeChat recommended).  All important content is kept
within the vertical safe zone y=70…430 so neither crop cuts off text.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def _find_font_path() -> str | None:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _font(size: int, font_path: str | None = None) -> ImageFont.FreeTypeFont:
    path = font_path or _find_font_path()
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple,
    text: str,
    size: int,
    fill: str,
    font_path: str | None = None,
    min_size: int = 18,
) -> None:
    """Draw text centred in *box*, auto-shrinking the font until it fits."""
    left, top, right, bottom = box
    max_width = right - left - 20  # 10 px padding each side

    current_size = size
    f = _font(current_size, font_path)
    while current_size > min_size:
        f = _font(current_size, font_path)
        bbox = draw.textbbox((0, 0), text, font=f)
        if bbox[2] - bbox[0] <= max_width:
            break
        current_size -= 2

    bbox = draw.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = left + (right - left - tw) / 2
    y = top + (bottom - top - th) / 2
    draw.text((x, y), text, font=f, fill=fill)


def generate_cover(
    output: Path,
    column: str,
    ticker: str,
    subtitle: str = "",
    issue: str = "",
    hook: str = "",
) -> None:
    # 900×500 — WeChat recommended size.
    # Safe text zone: y = 70 … 430  (survives both square-crop & 2.35:1 crop)
    width, height = 900, 500
    font_path = _find_font_path()

    image = Image.new("RGB", (width, height), "#101113")
    draw = ImageDraw.Draw(image)

    # Gradient background
    for y in range(height):
        shade = int(14 + y / height * 18)
        draw.line([(0, y), (width, y)], fill=(shade, shade, shade + 2))

    gold = "#d4af37"
    muted_gold = "#7b6425"

    # Diagonal decorative lines (stay within safe zone)
    for x in range(80, width, 140):
        draw.line([(x, 70), (x + 80, 430)], fill=muted_gold, width=1)
    for y_pos in [140, 260, 380]:
        draw.line([(90, y_pos), (810, y_pos - 18)], fill="#242424", width=2)

    # Outer gold border  (full canvas — visible in article page view)
    draw.rectangle((36, 36, width - 36, height - 36), outline=gold, width=3)
    draw.rectangle((50, 50, width - 50, height - 50), outline="#4b3d19", width=1)

    # Issue number — top-left of safe zone
    if issue:
        draw.text((70, 80), issue, font=_font(26, font_path), fill="#9c8a52")

    # Main headline (auto-shrinks to fit) — upper safe zone
    _center_text(draw, (0, 120, width, 220),
                 f"{column}：{ticker}", size=58, fill=gold, font_path=font_path)

    # Hook line — middle safe zone
    if hook:
        _center_text(draw, (80, 240, width - 80, 330),
                     hook, size=38, fill="#f2f0e8", font_path=font_path)

    # Subtitle — lower safe zone
    if subtitle:
        _center_text(draw, (0, 355, width, 415),
                     subtitle, size=28, fill="#c8b46b", font_path=font_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a recurring WeChat cover image.")
    parser.add_argument("--ticker",   required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--issue",    default="")
    parser.add_argument("--hook",     default="")
    parser.add_argument("--column",   default="炼金投研")
    parser.add_argument("--output",   required=True)
    args = parser.parse_args()

    generate_cover(
        Path(args.output),
        column=args.column, ticker=args.ticker,
        subtitle=args.subtitle, issue=args.issue, hook=args.hook,
    )
    print(f"Wrote cover to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
