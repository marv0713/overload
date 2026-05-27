#!/usr/bin/env python3
"""CLI entry point for processing a single Xiaoyuzhou podcast episode.

This is the debug/one-off counterpart to ``process_youtube.py``.

Basic usage — process the latest episode from an RSS feed::

    PYTHONPATH=src .venv/bin/python scripts/process_xiaoyuzhou.py \\
        --rss "https://rsshub.app/xiaoyuzhou/podcast/PODCAST_ID"

Process a specific episode by its episode_id (the 16-char hash printed by --list)::

    PYTHONPATH=src .venv/bin/python scripts/process_xiaoyuzhou.py \\
        --rss "https://rsshub.app/xiaoyuzhou/podcast/PODCAST_ID" \\
        --episode-id "abc123def456abcd"

Just list available episodes without downloading::

    PYTHONPATH=src .venv/bin/python scripts/process_xiaoyuzhou.py \\
        --rss "https://rsshub.app/xiaoyuzhou/podcast/PODCAST_ID" \\
        --list

Generate and push a WeChat draft after transcription::

    PYTHONPATH=src .venv/bin/python scripts/process_xiaoyuzhou.py \\
        --rss "..." \\
        --generate-article \\
        --push-draft --cover path/to/cover.png
"""
import argparse
import json
import sys
from pathlib import Path

from youtube_to_wechat.xiaoyuzhou import (
    XiaoyuzhouError,
    download_episode_audio,
    fetch_podcast_episodes,
    select_eligible_episodes,
)


_OUTPUT_BASE = Path("outputs/xiaoyuzhou")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process a single Xiaoyuzhou podcast episode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--rss", required=True, help="RSS feed URL for the podcast")
    parser.add_argument(
        "--episode-id",
        default="",
        help="Specific episode_id to process (omit to use latest eligible)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available episodes from the feed without downloading",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_OUTPUT_BASE),
        help="Base output directory (default: outputs/xiaoyuzhou)",
    )
    parser.add_argument(
        "--model-size",
        default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size for transcription (default: base)",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="Language hint for Whisper (default: zh)",
    )
    parser.add_argument(
        "--min-duration",
        type=int,
        default=300,
        help="Minimum episode duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--generate-article",
        action="store_true",
        help="Generate a WeChat article draft using Gemini after transcription",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-2.5-flash",
        help="Gemini model name for article generation (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--no-check-certificates",
        action="store_true",
        help="Skip SSL certificate verification (useful behind a proxy)",
    )
    parser.add_argument(
        "--push-draft",
        action="store_true",
        help="Push generated article to WeChat draft box after generation",
    )
    parser.add_argument(
        "--cover",
        default="",
        help="Path to cover image for WeChat draft push",
    )
    parser.add_argument(
        "--env",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    args = parser.parse_args()

    # ── Fetch episodes ────────────────────────────────────────────────────────
    try:
        print(f"Fetching RSS feed: {args.rss}")
        episodes = fetch_podcast_episodes(
            args.rss,
            limit=20,
            no_check_certificates=args.no_check_certificates,
        )
    except XiaoyuzhouError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not episodes:
        print("No episodes found in feed.", file=sys.stderr)
        return 1

    # ── List mode ─────────────────────────────────────────────────────────────
    if args.list:
        print(f"Found {len(episodes)} episodes:\n")
        for ep in episodes:
            mins = ep.duration_seconds // 60
            print(f"  [{ep.episode_id}] {ep.published_at} | {mins}min | {ep.title}")
        return 0

    # ── Select episode ────────────────────────────────────────────────────────
    if args.episode_id:
        selected = next((ep for ep in episodes if ep.episode_id == args.episode_id), None)
        if selected is None:
            print(f"error: episode_id '{args.episode_id}' not found in feed", file=sys.stderr)
            return 1
    else:
        eligible = select_eligible_episodes(
            episodes,
            min_duration_seconds=args.min_duration,
            processed_episode_ids=set(),
            source_seen_before=False,
        )
        if not eligible:
            print("No eligible episodes found (check --min-duration).", file=sys.stderr)
            return 1
        selected = eligible[0]

    print(f"Selected: [{selected.episode_id}] {selected.title}")

    # ── Set up output directory ───────────────────────────────────────────────
    output_base = Path(args.output_dir)
    podcast_slug = _slugify(selected.podcast_name or "podcast")
    output_dir = output_base / podcast_slug / selected.episode_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Write meta.json ───────────────────────────────────────────────────────
    meta = {
        "episode_id": selected.episode_id,
        "title": selected.title,
        "podcast_name": selected.podcast_name,
        "episode_url": selected.episode_url,
        "audio_url": selected.audio_url,
        "duration_seconds": selected.duration_seconds,
        "published_at": selected.published_at,
        "description": selected.description,
        "source": "podcast_rss",
        "rss_url": args.rss,
    }
    (output_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote meta.json → {output_dir}/meta.json")

    # ── Download audio ────────────────────────────────────────────────────────
    audio_dir = output_dir / "audio"
    print(f"Downloading audio: {selected.audio_url[:80]}...")
    try:
        audio_path = download_episode_audio(
            selected.audio_url,
            audio_dir,
            no_check_certificates=args.no_check_certificates,
        )
        audio_size = audio_path.stat().st_size
        print(f"Audio saved → {audio_path}  ({audio_size / 1024 / 1024:.1f} MB)")
    except XiaoyuzhouError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # ── Transcribe ────────────────────────────────────────────────────────────
    print(f"Transcribing with faster-whisper ({args.model_size}, lang={args.language})...")
    from youtube_to_wechat.transcriber import FasterWhisperTranscriber, TranscriberError

    transcriber = FasterWhisperTranscriber(model_size=args.model_size, language=args.language)
    try:
        transcript = transcriber.transcribe(audio_path)
    except TranscriberError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    transcript_path = output_dir / "transcript.txt"
    transcript_path.write_text(transcript + "\n", encoding="utf-8")
    print(f"Transcript saved → {transcript_path}  ({len(transcript)} chars)")

    # ── Generate article (optional) ───────────────────────────────────────────
    if args.generate_article:
        print("Generating article draft with Gemini...")
        from youtube_to_wechat.writer import GeminiWriter, WriterError

        writer = GeminiWriter(model=args.gemini_model)
        try:
            article = writer.write(transcript, meta)
        except WriterError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        (output_dir / "article.md").write_text(article.markdown + "\n", encoding="utf-8")
        print(f"Article saved → {output_dir}/article.md")
        print(f"Title suggestion: {article.title}")

        # ── Push WeChat draft (optional) ──────────────────────────────────────
        if args.push_draft:
            cover_path = Path(args.cover) if args.cover else output_dir / "cover.png"
            if not cover_path.exists():
                print(f"warning: cover image not found at {cover_path}, skipping push", file=sys.stderr)
            else:
                print("Pushing to WeChat draft box...")
                _push_draft(output_dir / "article.md", cover_path, Path(args.env))

    print(f"\nDone. Outputs in: {output_dir}")
    return 0


def _push_draft(article_path: Path, cover_path: Path, env_path: Path) -> None:
    from youtube_to_wechat.wechat import (
        WechatError,
        add_draft,
        build_draft_article,
        get_access_token,
        load_env,
        require_env,
        upload_permanent_thumb,
        _markdown_to_html,
    )

    env = load_env(env_path)
    required = require_env(env, ["WECHAT_APPID", "WECHAT_APPSECRET", "WECHAT_AUTHOR"])
    text = article_path.read_text(encoding="utf-8")

    import re
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else article_path.parent.name

    digest_match = re.search(r"^> 摘要：(.+)$", text, re.MULTILINE)
    digest = digest_match.group(1).strip() if digest_match else text[:110].replace("\n", " ")

    content = _markdown_to_html(text)

    try:
        token = get_access_token(required["WECHAT_APPID"], required["WECHAT_APPSECRET"])
        thumb_media_id = upload_permanent_thumb(token, cover_path)
        article_payload = build_draft_article(
            title=title,
            author=required["WECHAT_AUTHOR"],
            digest=digest,
            content=content,
            thumb_media_id=thumb_media_id,
            column="炼金投研",
        )
        media_id = add_draft(token, article_payload)
        print(f"WeChat draft created: {media_id}")
    except WechatError as exc:
        print(f"error: WeChat push failed: {exc}", file=sys.stderr)


def _slugify(text: str) -> str:
    import re
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower()).strip("-")
    return slug or "podcast"


if __name__ == "__main__":
    raise SystemExit(main())
