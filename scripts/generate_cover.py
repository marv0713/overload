#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def generate_cover(
    output: Path,
    column: str,
    ticker: str,
    subtitle: str = "",
    issue: str = "",
    hook: str = "",
) -> None:
    # 900×383 = 2.35:1  ← WeChat feed thumbnail standard ratio, no crop
    width, height = 900, 383
    image = Image.new("RGB", (width, height), "#101113")
    draw = ImageDraw.Draw(image)

    # Gradient background
    for y in range(height):
        shade = int(16 + y / height * 16)
        draw.line([(0, y), (width, y)], fill=(shade, shade, shade + 2))

    gold = "#d4af37"
    muted_gold = "#7b6425"

    # Diagonal decorative lines
    for x in range(80, width, 140):
        draw.line([(x, 40), (x + 70, height - 40)], fill=muted_gold, width=1)
    for y in [90, 190, 300]:
        draw.line([(90, y), (810, y - 15)], fill="#242424", width=2)

    # Border frames
    draw.rectangle((36, 36, width - 36, height - 36), outline=gold, width=3)
    draw.rectangle((50, 50, width - 50, height - 50), outline="#4b3d19", width=1)

    headline_font = _font(56)
    issue_font    = _font(24)
    hook_font     = _font(36)
    subtitle_font = _font(26)

    # Issue number — top left inside border
    if issue:
        draw.text((70, 60), issue, font=issue_font, fill="#9c8a52")

    # Main headline: column：ticker  (centred vertically in upper half)
    _center_text(draw, (0, 100, width, 180), f"{column}：{ticker}", headline_font, gold)

    # Hook line (article title snippet) — middle band
    if hook:
        _center_text(draw, (80, 190, width - 80, 270), hook, hook_font, "#f2f0e8")

    # Subtitle — lower area
    if subtitle:
        _center_text(draw, (0, 285, width, 340), subtitle, subtitle_font, "#c8b46b")

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)



def _center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    min_size: int = 18,
) -> None:
    """Draw text centred inside *box*, auto-shrinking the font until it fits."""
    left, top, right, bottom = box
    max_width = right - left - 16   # 8px padding each side

    # Auto-shrink: reduce size until text fits horizontally
    current_font = font
    while True:
        bbox = draw.textbbox((0, 0), text, font=current_font)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width or current_font.size <= min_size:
            break
        current_font = ImageFont.truetype(current_font.path, size=current_font.size - 2)

    bbox = draw.textbbox((0, 0), text, font=current_font)
    text_width  = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = left + (right - left - text_width) / 2
    y = top  + (bottom - top  - text_height) / 2
    draw.text((x, y), text, font=current_font, fill=fill)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a recurring WeChat cover image.")
    parser.add_argument("--ticker", required=True, help="Ticker or topic shown as the main text")
    parser.add_argument("--subtitle", default="", help="Small subtitle shown below the ticker")
    parser.add_argument("--issue", default="", help="Series issue label, e.g. No.001")
    parser.add_argument("--hook", default="", help="Short hook line based on article content")
    parser.add_argument("--column", default="炼金投研", help="Column label")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()

    generate_cover(
        Path(args.output),
        column=args.column,
        ticker=args.ticker,
        subtitle=args.subtitle,
        issue=args.issue,
        hook=args.hook,
    )
    print(f"Wrote cover to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
