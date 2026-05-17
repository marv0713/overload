#!/usr/bin/env python3
"""Process latest eligible videos from configured YouTube channel sources."""
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from youtube_to_wechat.output import write_article, write_outputs
from youtube_to_wechat.processed_store import ProcessedStore, slugify_source_name
from youtube_to_wechat.source_config import SourceConfig, load_source_config
from youtube_to_wechat.writer import GeminiWriter, WriterError
from youtube_to_wechat.writer_profiles import load_writer_profile
from youtube_to_wechat.youtube_channel import (
    ChannelVideo,
    fetch_channel_videos,
    select_eligible_videos_for_source,
)
from youtube_to_wechat.youtube_meta import extract_video_id
from youtube_to_wechat.ytdlp import YtDlpError, download_audio, fetch_info, fetch_transcript


@dataclass
class SourceCandidate:
    source: SourceConfig
    source_slug: str
    video: ChannelVideo


def process_video_url(
    url: str,
    output_base: Path,
    no_check_certificates: bool = False,
    skip_audio: bool = False,
    generate_article: bool = False,
    writer_profile: str = "deep-stock-analysis",
    writer_profile_dir: Path = Path("config/writer_profiles"),
    gemini_model: str = "gemini-2.5-flash",
) -> tuple[Path, dict]:
    video_id = extract_video_id(url)
    meta = fetch_info(url, no_check_certificates=no_check_certificates)
    meta.setdefault("video_id", video_id)
    meta.setdefault("url", url)

    run: dict = {
        "status": "ok",
        "transcript_status": "pending",
        "audio_status": "skipped",
        "article_status": "skipped",
        "writer_profile": writer_profile,
    }
    try:
        transcript = fetch_transcript(
            url,
            output_base / video_id / "_subs",
            no_check_certificates=no_check_certificates,
        )
        run["transcript_status"] = "ok"
    except YtDlpError as exc:
        transcript = ""
        run["transcript_status"] = "error"
        run["transcript_error"] = str(exc)

    if not skip_audio:
        try:
            audio_path = download_audio(
                url,
                output_base / video_id / "audio",
                no_check_certificates=no_check_certificates,
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
    if generate_article and transcript:
        try:
            profile = load_writer_profile(writer_profile, writer_profile_dir)
            writer = GeminiWriter(
                model=gemini_model,
                profile_name=profile.name,
                profile_prompt=profile.prompt,
            )
            article = writer.write(transcript, meta)
            write_article(output_base, video_id, article.markdown)
            run["article_status"] = "ok"
            run["article_title"] = article.title
        except (OSError, WriterError) as exc:
            run["article_status"] = "error"
            run["article_error"] = str(exc)
            if run["status"] == "ok":
                run["status"] = "partial"
        (output_dir / "run.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return output_dir, run


def collect_source_candidates(
    sources: list[SourceConfig],
    store: ProcessedStore,
    channel_limit: int,
    no_check_certificates: bool,
) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    for source in sources:
        if not source.enabled:
            print(f"[skip] {source.name}: disabled")
            continue
        if source.type != "youtube_channel":
            print(f"[skip] {source.name}: unsupported source type {source.type}")
            continue

        source_slug = slugify_source_name(source.name)
        source_seen_before = store.has_source(source_slug)
        videos = fetch_channel_videos(
            source.url,
            limit=channel_limit,
            no_check_certificates=no_check_certificates,
        )
        store.record_source_scan(source_name=source.name, source_slug=source_slug, videos=videos)
        selected_videos = select_eligible_videos_for_source(
            videos,
            min_duration_seconds=source.min_duration_seconds,
            processed_video_ids=store.processed_video_ids(),
            source_seen_before=source_seen_before,
            stop_at_video_ids=store.processed_video_ids_for_source(source_slug),
        )
        if not selected_videos:
            print(f"[skip] {source.name}: no new long video found")
            continue
        for video in selected_videos:
            candidates.append(SourceCandidate(source=source, source_slug=source_slug, video=video))

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.source.priority,
            candidate.video.published_at or "9999-12-31",
        ),
    )


def process_candidate(
    candidate: SourceCandidate,
    store: ProcessedStore,
    output_base: Path,
    no_check_certificates: bool,
    dry_run: bool,
    generate_article: bool = False,
    writer_profile_dir: Path = Path("config/writer_profiles"),
    gemini_model: str = "gemini-2.5-flash",
) -> int:
    source = candidate.source
    selected = candidate.video
    print(f"[pick] {source.name}: {selected.title} ({selected.duration_seconds}s)")
    print(f"       {selected.url}")
    if dry_run:
        return 0

    output_dir, run = process_video_url(
        selected.url,
        output_base=output_base / candidate.source_slug,
        no_check_certificates=no_check_certificates,
        skip_audio=source.compare_evaluation == "none",
        generate_article=generate_article,
        writer_profile=source.writer_profile,
        writer_profile_dir=writer_profile_dir,
        gemini_model=gemini_model,
    )
    if run["status"] != "error":
        issue = store.allocate_issue(source.series)
        store.mark_processed(
            selected.video_id,
            source_name=source.name,
            source_slug=candidate.source_slug,
            title=selected.title,
            url=selected.url,
            output_dir=str(output_dir),
            status=run["status"],
            series=source.series,
            issue=issue,
            writer_profile=source.writer_profile,
        )
        print(f"[issue] {source.series}: {issue}")
    print(f"[done] {source.name}: {run['status']} -> {output_dir}")
    return 1


def process_source(
    source: SourceConfig,
    store: ProcessedStore,
    output_base: Path,
    channel_limit: int,
    no_check_certificates: bool,
    dry_run: bool,
    generate_article: bool = False,
    writer_profile_dir: Path = Path("config/writer_profiles"),
    gemini_model: str = "gemini-2.5-flash",
) -> int:
    if not source.enabled:
        print(f"[skip] {source.name}: disabled")
        return 0
    if source.type != "youtube_channel":
        print(f"[skip] {source.name}: unsupported source type {source.type}")
        return 0

    source_slug = slugify_source_name(source.name)
    source_seen_before = store.has_source(source_slug)
    videos = fetch_channel_videos(
        source.url,
        limit=channel_limit,
        no_check_certificates=no_check_certificates,
    )
    store.record_source_scan(source_name=source.name, source_slug=source_slug, videos=videos)
    selected_videos = select_eligible_videos_for_source(
        videos,
        min_duration_seconds=source.min_duration_seconds,
        processed_video_ids=store.processed_video_ids(),
        source_seen_before=source_seen_before,
        stop_at_video_ids=store.processed_video_ids_for_source(source_slug),
    )
    selected = selected_videos[0] if selected_videos else None
    if selected is None:
        print(f"[skip] {source.name}: no new long video found")
        return 0

    print(f"[pick] {source.name}: {selected.title} ({selected.duration_seconds}s)")
    print(f"       {selected.url}")
    if dry_run:
        return 0

    output_dir, run = process_video_url(
        selected.url,
        output_base=output_base / source_slug,
        no_check_certificates=no_check_certificates,
        skip_audio=source.compare_evaluation == "none",
        generate_article=generate_article,
        writer_profile=source.writer_profile,
        writer_profile_dir=writer_profile_dir,
        gemini_model=gemini_model,
    )
    if run["status"] != "error":
        issue = store.allocate_issue(source.series)
        store.mark_processed(
            selected.video_id,
            source_name=source.name,
            source_slug=source_slug,
            title=selected.title,
            url=selected.url,
            output_dir=str(output_dir),
            status=run["status"],
            series=source.series,
            issue=issue,
            writer_profile=source.writer_profile,
        )
        print(f"[issue] {source.series}: {issue}")
    print(f"[done] {source.name}: {run['status']} -> {output_dir}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Process latest long videos from configured sources.")
    parser.add_argument("--config", default="config/sources.json", help="Source config JSON path")
    parser.add_argument("--store", default="data/processed.json", help="Processed video store path")
    parser.add_argument("--output-dir", default="outputs/youtube", help="Base output directory")
    parser.add_argument("--channel-limit", type=int, default=12, help="Videos to inspect per channel")
    parser.add_argument("--max-items", type=int, default=1, help="Maximum queued videos to process this run")
    parser.add_argument("--generate-article", action="store_true", help="Generate article.md using each source writer_profile")
    parser.add_argument("--writer-profile-dir", default="config/writer_profiles", help="Directory containing writer profile Markdown files")
    parser.add_argument("--gemini-model", default="gemini-2.5-flash", help="Gemini model used when --generate-article is set")
    parser.add_argument("--dry-run", action="store_true", help="Print selected videos without processing")
    parser.add_argument(
        "--no-check-certificates",
        action="store_true",
        help="Pass --no-check-certificates to yt-dlp.",
    )
    args = parser.parse_args()

    try:
        config = load_source_config(Path(args.config))
        store = ProcessedStore(Path(args.store))
        processed_count = 0
        candidates = collect_source_candidates(
            sources=config.sources,
            store=store,
            channel_limit=args.channel_limit,
            no_check_certificates=args.no_check_certificates,
        )
        for candidate in candidates[: args.max_items]:
            processed_count += process_candidate(
                candidate=candidate,
                store=store,
                output_base=Path(args.output_dir),
                no_check_certificates=args.no_check_certificates,
                dry_run=args.dry_run,
                generate_article=args.generate_article,
                writer_profile_dir=Path(args.writer_profile_dir),
                gemini_model=args.gemini_model,
            )
    except (OSError, ValueError, YtDlpError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Processed {processed_count} source item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
