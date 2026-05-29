#!/usr/bin/env python3
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
    """Return the first available font path, or None."""
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
    """Draw text centred in *box*, auto-shrinking until it fits horizontally."""
    left, top, right, bottom = box
    max_width = right - left - 20  # 10px padding each side

    current_size = size
    while current_size >= min_size:
        f = _font(current_size, font_path)
        bbox = draw.textbbox((0, 0), text, font=f)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= max_width:
            break
        current_size -= 2
    else:
        f = _font(min_size, font_path)
        bbox = draw.textbbox((0, 0), text, font=f)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

    x = left + (right - left - text_w) / 2
    y = top + (bottom - top - text_h) / 2
    draw.text((x, y), text, font=f, fill=fill)


def generate_cover(
    output: Path,
    column: str,
    ticker: str,
    subtitle: str = "",
    issue: str = "",
    hook: str = "",
) -> None:
    # 900×383 = 2.35:1  ← WeChat feed thumbnail standard ratio
    width, height = 900, 383
    font_path = _find_font_path()

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
    for y_pos in [90, 190, 300]:
        draw.line([(90, y_pos), (810, y_pos - 15)], fill="#242424", width=2)

    # Border frames
    draw.rectangle((36, 36, width - 36, height - 36), outline=gold, width=3)
    draw.rectangle((50, 50, width - 50, height - 50), outline="#4b3d19", width=1)

    # Issue number — top left
    if issue:
        issue_font = _font(24, font_path)
        draw.text((70, 60), issue, font=issue_font, fill="#9c8a52")

    # Main headline (auto-shrinks to fit)
    _center_text(draw, (0, 95, width, 180), f"{column}：{ticker}",
                 size=56, fill=gold, font_path=font_path)

    # Hook line
    if hook:
        _center_text(draw, (80, 190, width - 80, 275), hook,
                     size=36, fill="#f2f0e8", font_path=font_path)

    # Subtitle
    if subtitle:
        _center_text(draw, (0, 285, width, 340), subtitle,
                     size=26, fill="#c8b46b", font_path=font_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


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
