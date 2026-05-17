import html
import json
import re
from pathlib import Path
from typing import Any, Optional


def write_comparison(base_dir: Path, video_id: str, content: str) -> Path:
    """Write *content* as ``comparison.md`` inside the video output directory.

    Args:
        base_dir: Root output directory (e.g. ``outputs/youtube``).
        video_id: YouTube video ID used as the sub-directory name.
        content:  Markdown string produced by
            :func:`~youtube_to_wechat.compare.render_comparison_md`.

    Returns:
        Path to the written ``comparison.md`` file.
    """
    output_dir = base_dir / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "comparison.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_article(base_dir: Path, video_id: str, article_markdown: str) -> Path:
    """Write the LLM-generated article as ``article.md`` and ``article.html``.

    Args:
        base_dir:         Root output directory.
        video_id:         YouTube video ID.
        article_markdown: Markdown string from :class:`~youtube_to_wechat.writer.GeminiWriter`.

    Returns:
        Path to ``article.md``.
    """
    output_dir = base_dir / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "article.md").write_text(article_markdown + "\n", encoding="utf-8")

    # Minimal Markdown → HTML conversion for WeChat draft preview.
    article_html = _markdown_to_html(article_markdown)
    (output_dir / "article.html").write_text(article_html, encoding="utf-8")

    return output_dir / "article.md"


def _markdown_to_html(md: str) -> str:
    """Convert a subset of Markdown to HTML suitable for WeChat article preview."""
    lines = []
    for line in md.splitlines():
        # Headings
        if line.startswith("### "):
            line = f"<h3>{html.escape(line[4:])}</h3>"
        elif line.startswith("## "):
            line = f"<h2>{html.escape(line[3:])}</h2>"
        elif line.startswith("# "):
            line = f"<h1>{html.escape(line[2:])}</h1>"
        # Blockquotes
        elif line.startswith("> "):
            line = f"<blockquote><p>{html.escape(line[2:])}</p></blockquote>"
        # Unordered list items
        elif line.startswith("- "):
            line = f"<li>{html.escape(line[2:])}</li>"
        # Horizontal rule
        elif line.strip() == "---":
            line = "<hr>"
        # Empty line → paragraph break
        elif line.strip() == "":
            line = ""
        else:
            line = f"<p>{html.escape(line)}</p>"

        # Inline bold **text** → <strong>
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        lines.append(line)

    return "\n".join(lines)


def write_outputs(
    base_dir: Path,
    video_id: str,
    meta: dict[str, Any],
    transcript: str,
    run: Optional[dict[str, Any]] = None,
) -> Path:
    output_dir = base_dir / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    title = meta.get("title") or video_id
    source_url = meta.get("webpage_url") or meta.get("url") or f"https://www.youtube.com/watch?v={video_id}"

    # Placeholder article — will be overwritten by write_article() if writer runs.
    placeholder_md = (
        f"# {title}\n\n"
        f"来源：{source_url}\n\n"
        "## 待生成文章\n\n"
        "运行 `--compare` 后将自动生成公众号文章草稿。\n"
    )
    placeholder_html = (
        f"<h1>{html.escape(title)}</h1>\n"
        f'<p>来源：<a href="{html.escape(source_url)}">{html.escape(source_url)}</a></p>\n'
        "<h2>待生成文章</h2>\n"
        "<p>运行 <code>--compare</code> 后将自动生成公众号文章草稿。</p>\n"
    )

    (output_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    (output_dir / "transcript.txt").write_text(transcript.rstrip() + "\n")
    (output_dir / "article.md").write_text(placeholder_md)
    (output_dir / "article.html").write_text(placeholder_html)
    (output_dir / "run.json").write_text(
        json.dumps(run or {"status": "ok"}, ensure_ascii=False, indent=2) + "\n"
    )

    return output_dir
