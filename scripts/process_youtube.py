#!/usr/bin/env python3
"""CLI entry point for the YouTube source adapter MVP.

Basic mode (existing behaviour)::

    python3 scripts/process_youtube.py "https://www.youtube.com/watch?v=..."

Compare evaluation mode (caption-vs-audio opinion extraction)::

    GEMINI_API_KEY=xxx python3 scripts/process_youtube.py \\
        "https://www.youtube.com/watch?v=..." \\
        --compare \\
        --model-size base \\
        --gemini-model gemini-2.5-flash

In compare evaluation mode the script runs both a caption path and an audio
transcription path, extracts opinions from each, and writes
``outputs/youtube/<video_id>/comparison.md``.  This is an evaluation workflow,
not the default publishing path.
"""
import argparse
import sys
from pathlib import Path

from youtube_to_wechat.output import write_article, write_comparison, write_outputs
from youtube_to_wechat.youtube_meta import extract_video_id
from youtube_to_wechat.ytdlp import YtDlpError, download_audio, fetch_info, fetch_transcript


def _run_comparison(
    url: str,
    video_id: str,
    meta: dict,
    output_base: Path,
    subtitle_transcript: str,
    subtitle_transcript_error: str | None,
    no_check_certificates: bool,
    model_size: str,
    gemini_model: str,
    writer_profile: str,
    writer_profile_dir: Path,
) -> Path:
    """Run both extraction paths and write comparison.md.  Returns its path."""
    from youtube_to_wechat.compare import render_comparison_md
    from youtube_to_wechat.extractor import ExtractorError, GeminiExtractor
    from youtube_to_wechat.transcriber import FasterWhisperTranscriber, TranscriberError

    extractor = GeminiExtractor(model=gemini_model)

    # ── Path A: subtitle ──────────────────────────────────────────────────────
    subtitle_opinions = None
    subtitle_extract_error = subtitle_transcript_error
    if subtitle_transcript and not subtitle_extract_error:
        print("[compare] Extracting opinions from subtitle transcript …")
        try:
            subtitle_opinions = extractor.extract(subtitle_transcript, meta)
        except ExtractorError as exc:
            subtitle_extract_error = str(exc)
            print(f"[compare] Subtitle extraction error: {exc}", file=sys.stderr)

    # ── Path B: audio → Whisper ───────────────────────────────────────────────
    audio_transcript = ""
    audio_opinions = None
    audio_error: str | None = None

    audio_dir = output_base / video_id / "audio"
    print("[compare] Downloading audio for Whisper transcription …")
    try:
        audio_path = download_audio(
            url, audio_dir, no_check_certificates=no_check_certificates
        )
    except YtDlpError as exc:
        audio_error = str(exc)
        audio_path = None
        print(f"[compare] Audio download error: {exc}", file=sys.stderr)

    if audio_path:
        print(f"[compare] Transcribing with faster-whisper ({model_size}) …")
        transcriber = FasterWhisperTranscriber(model_size=model_size)
        try:
            audio_transcript = transcriber.transcribe(audio_path)
        except TranscriberError as exc:
            audio_error = str(exc)
            print(f"[compare] Whisper error: {exc}", file=sys.stderr)

    if audio_transcript and not audio_error:
        print("[compare] Extracting opinions from audio transcript …")
        try:
            audio_opinions = extractor.extract(audio_transcript, meta)
        except ExtractorError as exc:
            audio_error = str(exc)
            print(f"[compare] Audio extraction error: {exc}", file=sys.stderr)

    # ── Render and write comparison.md ────────────────────────────────────────
    md = render_comparison_md(
        meta=meta,
        subtitle_transcript=subtitle_transcript,
        audio_transcript=audio_transcript,
        subtitle_opinions=subtitle_opinions,
        audio_opinions=audio_opinions,
        subtitle_error=subtitle_extract_error,
        audio_error=audio_error,
    )
    comparison_path = write_comparison(output_base, video_id, md)

    # ── Generate article.md ───────────────────────────────────────────────────
    from youtube_to_wechat.writer import GeminiWriter, WriterError  # noqa: PLC0415
    from youtube_to_wechat.writer_profiles import load_writer_profile  # noqa: PLC0415

    # Use subtitle transcript when available, fall back to audio.
    article_transcript = subtitle_transcript or audio_transcript
    if article_transcript:
        print("[compare] Generating article draft …")
        profile = load_writer_profile(writer_profile, writer_profile_dir)
        writer = GeminiWriter(
            model=gemini_model,
            profile_name=profile.name,
            profile_prompt=profile.prompt,
        )
        try:
            article = writer.write(article_transcript, meta)

            # --- Auto Chart Generation Plugin ---
            if article.chart_data:
                from youtube_to_wechat.charting import generate_infographic # noqa: PLC0415
                chart_path = output_base / video_id / "infographic.png"
                chart_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"[compare] Generating infographic from extracted data...")
                if generate_infographic(article.chart_data, str(chart_path)):
                    # Insert the image into the markdown right after "核心数据与财务表现"
                    target_heading = "### 二、核心数据与财务表现"
                    if target_heading in article.markdown:
                        parts = article.markdown.split(target_heading, 1)
                        article.markdown = f"{parts[0]}{target_heading}\n\n![核心数据对比图](infographic.png)\n{parts[1]}"
                    else:
                        article.markdown = f"![核心数据对比图](infographic.png)\n\n" + article.markdown

            write_article(output_base, video_id, article.markdown)
            print(f"[compare] Article title suggestion: {article.title}")
        except WriterError as exc:
            print(f"[compare] Article generation error: {exc}", file=sys.stderr)

    return comparison_path



def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process one YouTube video into local draft files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--output-dir", default="outputs/youtube", help="Base output directory"
    )
    parser.add_argument(
        "--no-check-certificates",
        action="store_true",
        help="Pass --no-check-certificates to yt-dlp (for broken CA setups).",
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Skip audio download (no effect when --compare is set).",
    )
    # ── Comparison mode flags ─────────────────────────────────────────────────
    parser.add_argument(
        "--compare",
        action="store_true",
        help=(
            "Enable caption-vs-audio compare evaluation: extract opinions from "
            "both the caption transcript and an audio Whisper transcript, then "
            "write comparison.md. Requires GEMINI_API_KEY."
        ),
    )
    parser.add_argument(
        "--model-size",
        default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="faster-whisper model size used in --compare mode (default: base).",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-2.5-flash",
        help="Gemini model name used for opinion extraction (default: gemini-2.5-flash).",
    )
    parser.add_argument(
        "--writer-profile",
        default="deep-stock-analysis",
        help="Writer profile name under config/writer_profiles (default: deep-stock-analysis).",
    )
    parser.add_argument(
        "--writer-profile-dir",
        default="config/writer_profiles",
        help="Directory containing writer profile Markdown files.",
    )
    args = parser.parse_args()

    try:
        video_id = extract_video_id(args.url)
        meta = fetch_info(args.url, no_check_certificates=args.no_check_certificates)
        meta.setdefault("video_id", video_id)
        meta.setdefault("url", args.url)
        output_base = Path(args.output_dir)
        run: dict = {"status": "ok", "transcript_status": "pending", "audio_status": "skipped"}

        # ── Subtitle / caption path ───────────────────────────────────────────
        subtitle_error: str | None = None
        try:
            transcript = fetch_transcript(
                args.url,
                output_base / video_id / "_subs",
                no_check_certificates=args.no_check_certificates,
            )
            run["transcript_status"] = "ok"
        except YtDlpError as exc:
            transcript = ""
            subtitle_error = str(exc)
            run["transcript_status"] = "error"
            run["transcript_error"] = subtitle_error

        # ── Audio download path (basic mode only) ─────────────────────────────
        if not args.compare and not args.skip_audio:
            try:
                audio_path = download_audio(
                    args.url,
                    output_base / video_id / "audio",
                    no_check_certificates=args.no_check_certificates,
                )
                run["audio_status"] = "ok"
                run["audio_path"] = str(audio_path) if audio_path else ""
            except YtDlpError as exc:
                run["audio_status"] = "error"
                run["audio_error"] = str(exc)

        if run["transcript_status"] != "ok" and run["audio_status"] != "ok":
            run["status"] = "error"
        elif run["transcript_status"] != "ok" or run["audio_status"] != "ok":
            run["status"] = "partial"

        output_dir = write_outputs(output_base, video_id, meta, transcript, run=run)

        # ── Comparison mode ───────────────────────────────────────────────────
        if args.compare:
            comparison_path = _run_comparison(
                url=args.url,
                video_id=video_id,
                meta=meta,
                output_base=output_base,
                subtitle_transcript=transcript,
                subtitle_transcript_error=subtitle_error,
                no_check_certificates=args.no_check_certificates,
                model_size=args.model_size,
                gemini_model=args.gemini_model,
                writer_profile=args.writer_profile,
                writer_profile_dir=Path(args.writer_profile_dir),
            )
            print(f"Comparison report: {comparison_path}")

    except (ValueError, YtDlpError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote outputs to {output_dir}")
    print(f"Transcript: {run['transcript_status']}; audio: {run['audio_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
