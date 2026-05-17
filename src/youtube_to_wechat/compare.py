"""Compare evaluation renderer for dual-path opinion extraction.

Compare evaluation is an experimental workflow, separate from the default
publishing path.  The first evaluation compares the caption transcript path
against the audio transcription path, including extracted opinions and a
summary table.

Usage::

    from youtube_to_wechat.compare import render_comparison_md

    md = render_comparison_md(
        meta=meta,
        subtitle_transcript=subtitle_text,
        audio_transcript=audio_text,
        subtitle_opinions=opinions_a,
        audio_opinions=opinions_b,
    )
    Path("comparison.md").write_text(md)
"""
from datetime import datetime
from typing import Optional

from youtube_to_wechat.extractor import OpinionResult

DEFAULT_COMPARE_EVALUATION = "caption-vs-audio"

# Number of characters to preview from each transcript artifact in the report.
_PREVIEW_CHARS = 600


def _transcript_preview(text: str, n: int = _PREVIEW_CHARS) -> str:
    """Return an italicised preview of *text*, truncated to *n* characters."""
    if not text or not text.strip():
        return "_（无 transcript）_"
    preview = text[:n].replace("\n", " ").strip()
    suffix = " …" if len(text) > n else ""
    return f"_{preview}{suffix}_"


def _render_opinions(result: Optional[OpinionResult], error: Optional[str]) -> str:
    """Render one extraction result block as Markdown."""
    if error:
        return f"> ⚠️ 错误：{error}\n"
    if result is None:
        return "_（未运行）_\n"

    parts: list[str] = []

    if result.summary:
        parts.append(f"**摘要**：{result.summary}\n")

    if result.opinions:
        parts.append("**核心观点**\n")
        parts.extend(f"{i}. {op}" for i, op in enumerate(result.opinions, 1))
        parts.append("")

    if result.key_points:
        parts.append("**要点**\n")
        parts.extend(f"- {kp}" for kp in result.key_points)
        parts.append("")

    if result.review_notes:
        parts.append("**人工核查点**\n")
        parts.extend(f"- ⚠️ {note}" for note in result.review_notes)
        parts.append("")

    return "\n".join(parts) if parts else "_（无内容）_\n"


def render_comparison_md(
    meta: dict,
    subtitle_transcript: str,
    audio_transcript: str,
    subtitle_opinions: Optional[OpinionResult] = None,
    audio_opinions: Optional[OpinionResult] = None,
    subtitle_error: Optional[str] = None,
    audio_error: Optional[str] = None,
) -> str:
    """Render the caption-vs-audio compare evaluation as Markdown.

    Args:
        meta: Source metadata dict (must contain at least ``"title"``).
        subtitle_transcript: Cleaned transcript text from the caption path.
        audio_transcript: Transcript text from the audio transcription path.
        subtitle_opinions: :class:`~youtube_to_wechat.extractor.OpinionResult`
            from the caption path, or ``None`` if not run / skipped.
        audio_opinions: :class:`~youtube_to_wechat.extractor.OpinionResult`
            from the audio path, or ``None`` if not run / skipped.
        subtitle_error: Error message if the caption path failed.
        audio_error: Error message if the audio path failed.

    Returns:
        A Markdown-formatted comparison report as a string.
    """
    title = meta.get("title") or "未知标题"
    url = meta.get("webpage_url") or meta.get("url") or ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    sub_word_count = len(subtitle_transcript.split()) if subtitle_transcript else 0
    audio_word_count = len(audio_transcript.split()) if audio_transcript else 0
    sub_opinion_count = len(subtitle_opinions.opinions) if subtitle_opinions else 0
    audio_opinion_count = len(audio_opinions.opinions) if audio_opinions else 0

    sub_status = "✅ 成功" if not subtitle_error else "❌ 失败"
    audio_status = "✅ 成功" if not audio_error else "❌ 失败"

    lines = [
        f"# Compare Evaluation（{DEFAULT_COMPARE_EVALUATION}）：{title}",
        "",
        f"> 视频：{url}  ",
        f"> 生成时间：{timestamp}",
        "",
        "---",
        "",
        "## 路径 A：字幕（Subtitle → yt-dlp）",
        "",
        "### Transcript 片段",
        "",
        _transcript_preview(subtitle_transcript),
        "",
        "### 提取结果",
        "",
        _render_opinions(subtitle_opinions, subtitle_error),
        "---",
        "",
        "## 路径 B：音频转写（Audio → Whisper）",
        "",
        "### Transcript 片段",
        "",
        _transcript_preview(audio_transcript),
        "",
        "### 提取结果",
        "",
        _render_opinions(audio_opinions, audio_error),
        "---",
        "",
        "## 对比速览",
        "",
        "| 维度 | 路径 A 字幕 | 路径 B 音频 |",
        "|------|:----------:|:----------:|",
        f"| 状态 | {sub_status} | {audio_status} |",
        f"| Transcript 词数 | {sub_word_count} | {audio_word_count} |",
        f"| 提取观点数 | {sub_opinion_count} | {audio_opinion_count} |",
        "",
    ]

    return "\n".join(lines)
