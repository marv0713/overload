import json
import subprocess
from dataclasses import dataclass
from typing import Iterable, Optional

from youtube_to_wechat.ytdlp import YtDlpError, ytdlp_command, ytdlp_options


@dataclass
class ChannelVideo:
    video_id: str
    title: str
    url: str
    duration_seconds: int
    published_at: str = ""


def select_latest_eligible_video(
    videos: Iterable[ChannelVideo],
    min_duration_seconds: int,
    processed_video_ids: set[str],
) -> Optional[ChannelVideo]:
    for video in videos:
        if video.duration_seconds < min_duration_seconds:
            continue
        if video.video_id in processed_video_ids:
            continue
        return video
    return None


def select_eligible_videos_for_source(
    videos: Iterable[ChannelVideo],
    min_duration_seconds: int,
    processed_video_ids: set[str],
    source_seen_before: bool,
    stop_at_video_ids: set[str] | None = None,
) -> list[ChannelVideo]:
    source_videos = list(videos)
    if source_seen_before and stop_at_video_ids:
        processed_indices = [
            index
            for index, video in enumerate(source_videos)
            if video.video_id in stop_at_video_ids
        ]
        if processed_indices:
            source_videos = source_videos[: max(processed_indices)]

    eligible = [
        video
        for video in source_videos
        if video.duration_seconds >= min_duration_seconds
        and video.video_id not in processed_video_ids
    ]
    if not source_seen_before:
        return eligible[:1]
    return [
        video
        for _, video in sorted(
            enumerate(eligible),
            key=lambda item: (item[1].published_at or "9999-12-31", -item[0]),
        )
    ]


def fetch_channel_videos(
    channel_url: str,
    limit: int = 12,
    no_check_certificates: bool = False,
) -> list[ChannelVideo]:
    result = subprocess.run(
        [
            *ytdlp_command(),
            *ytdlp_options(no_check_certificates),
            "--dump-single-json",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            _videos_url(channel_url),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise YtDlpError(result.stderr.strip() or "yt-dlp failed while fetching channel videos")

    data = json.loads(result.stdout)
    return [_video_from_entry(entry) for entry in data.get("entries", []) if entry]


def _videos_url(channel_url: str) -> str:
    cleaned = channel_url.rstrip("/")
    if cleaned.endswith("/videos"):
        return cleaned
    return f"{cleaned}/videos"


def _video_from_entry(entry: dict) -> ChannelVideo:
    video_id = entry.get("id") or entry.get("url") or ""
    url = entry.get("webpage_url") or entry.get("url") or ""
    if url and url.startswith("http"):
        video_url = url
    else:
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    return ChannelVideo(
        video_id=video_id,
        title=entry.get("title") or video_id,
        url=video_url,
        duration_seconds=int(entry.get("duration") or 0),
        published_at=_published_at_from_entry(entry),
    )


def _published_at_from_entry(entry: dict) -> str:
    upload_date = str(entry.get("upload_date") or "")
    if len(upload_date) == 8 and upload_date.isdigit():
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    timestamp = entry.get("timestamp") or entry.get("release_timestamp")
    if timestamp:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date().isoformat()
    return ""
