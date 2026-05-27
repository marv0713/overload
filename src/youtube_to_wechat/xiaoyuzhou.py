"""Xiaoyuzhou (小宇宙) podcast source adapter.

Fetches episode metadata and audio from an RSS feed (including RSSHub-generated
feeds), downloads the audio file for Whisper transcription, and normalises the
result into the same ``ChannelVideo``-compatible interface used by the YouTube
adapter so ``process_sources.py`` can treat both sources uniformly.

Usage::

    from youtube_to_wechat.xiaoyuzhou import fetch_podcast_episodes, download_episode_audio

    episodes = fetch_podcast_episodes("https://rsshub.app/xiaoyuzhou/podcast/PODCAST_ID")
    for ep in episodes:
        print(ep.title, ep.duration_seconds)
        audio_path = download_episode_audio(ep.audio_url, Path("outputs/audio"))
"""
from __future__ import annotations

import hashlib
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class XiaoyuzhouError(RuntimeError):
    """Raised when RSS fetch or audio download fails."""


@dataclass
class PodcastEpisode:
    """A single podcast episode extracted from an RSS feed.

    Attributes:
        episode_id:       Stable unique ID (RSS guid hash or URL hash).
        title:            Episode title.
        description:      RSS summary / show-notes (plain text, may be rich).
        audio_url:        Direct URL to the audio file (mp3 / m4a).
        duration_seconds: Episode duration in seconds (0 if unavailable).
        published_at:     ISO 8601 date string (e.g. ``"2024-03-15"``).
        episode_url:      Web page URL for the episode on Xiaoyuzhou.
        podcast_name:     Name of the parent podcast show.
    """

    episode_id: str
    title: str
    description: str
    audio_url: str
    duration_seconds: int
    published_at: str
    episode_url: str = ""
    podcast_name: str = ""


def fetch_podcast_episodes(
    rss_url: str,
    limit: int = 12,
    no_check_certificates: bool = False,
) -> list[PodcastEpisode]:
    """Parse an RSS feed and return the *limit* most recent episodes.

    Args:
        rss_url:               RSS or Atom feed URL (supports RSSHub feeds).
        limit:                 Maximum number of episodes to return.
        no_check_certificates: Skip SSL verification (useful on proxied networks).

    Returns:
        List of :class:`PodcastEpisode` objects, newest first.

    Raises:
        XiaoyuzhouError: If ``feedparser`` is not installed or the feed cannot
            be fetched / parsed.
    """
    try:
        import feedparser  # noqa: PLC0415
    except ImportError as exc:
        raise XiaoyuzhouError(
            "feedparser is not installed. Install it with: pip install feedparser"
        ) from exc

    if no_check_certificates:
        # Pre-fetch with SSL verification disabled, then pass bytes to feedparser
        import urllib.request as _ur  # noqa: PLC0415
        ctx = ssl._create_unverified_context()
        try:
            req = _ur.Request(rss_url, headers={"User-Agent": "Mozilla/5.0 (compatible; RSS reader)"})
            with _ur.urlopen(req, context=ctx, timeout=30) as resp:
                raw_bytes = resp.read()
            feed = feedparser.parse(raw_bytes)
        except Exception as exc:  # noqa: BLE001
            raise XiaoyuzhouError(f"Failed to fetch RSS feed {rss_url}: {exc}") from exc
    else:
        feed = feedparser.parse(rss_url)
    if feed.get("bozo") and not feed.get("entries"):
        raise XiaoyuzhouError(
            f"Failed to parse RSS feed {rss_url}: {feed.get('bozo_exception', 'unknown error')}"
        )

    podcast_name = feed.feed.get("title", "")
    episodes: list[PodcastEpisode] = []
    for entry in feed.entries[:limit]:
        ep = _episode_from_entry(entry, podcast_name)
        if ep is not None:
            episodes.append(ep)

    return episodes


def download_episode_audio(
    audio_url: str,
    dest_dir: Path,
    no_check_certificates: bool = False,
) -> Path:
    """Download a podcast episode's audio file to *dest_dir*.

    The filename is derived from the URL's last path segment.  If the file
    already exists it is returned immediately without re-downloading.

    Args:
        audio_url:             Direct URL to the audio file.
        dest_dir:              Local directory to save the file.
        no_check_certificates: Skip SSL verification.

    Returns:
        Path to the downloaded local audio file.

    Raises:
        XiaoyuzhouError: On network or I/O failures.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = audio_url.split("?")[0].rstrip("/").split("/")[-1]
    if not filename or "." not in filename:
        filename = f"episode_{hashlib.md5(audio_url.encode()).hexdigest()[:8]}.mp3"

    dest_path = dest_dir / filename
    if dest_path.exists():
        return dest_path

    ctx = ssl._create_unverified_context() if no_check_certificates else ssl.create_default_context()
    try:
        with urllib.request.urlopen(audio_url, context=ctx, timeout=60) as resp:
            dest_path.write_bytes(resp.read())
    except Exception as exc:  # noqa: BLE001
        raise XiaoyuzhouError(f"Audio download failed for {audio_url}: {exc}") from exc

    return dest_path


def select_eligible_episodes(
    episodes: list[PodcastEpisode],
    min_duration_seconds: int,
    processed_episode_ids: set[str],
    source_seen_before: bool,
) -> list[PodcastEpisode]:
    """Filter and order episodes for processing.

    Mirrors the logic in ``youtube_channel.select_eligible_videos_for_source``:
    - Always skip already-processed episodes.
    - Always skip episodes shorter than *min_duration_seconds*.
    - If the source has never been processed before, return only the single
      latest eligible episode to avoid flooding the queue with back-catalogue.
    - Otherwise return all eligible episodes ordered oldest-first.
    """
    eligible = [
        ep
        for ep in episodes
        if ep.duration_seconds >= min_duration_seconds
        and ep.episode_id not in processed_episode_ids
    ]
    if not source_seen_before:
        return eligible[:1]
    return sorted(eligible, key=lambda ep: ep.published_at or "9999-12-31")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _episode_from_entry(entry: object, podcast_name: str) -> Optional[PodcastEpisode]:
    """Convert a feedparser entry dict into a :class:`PodcastEpisode`."""
    # Audio URL: look in enclosures first, then links
    audio_url = ""
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("audio"):
            audio_url = enc.get("href") or enc.get("url") or ""
            break
    if not audio_url:
        for link in getattr(entry, "links", []):
            if link.get("type", "").startswith("audio"):
                audio_url = link.get("href") or ""
                break

    if not audio_url:
        return None  # Skip episodes without audio

    # Stable ID: prefer RSS guid, fall back to URL hash
    guid = getattr(entry, "id", "") or getattr(entry, "guid", "")
    if not guid:
        guid = hashlib.md5(audio_url.encode()).hexdigest()
    episode_id = hashlib.md5(guid.encode()).hexdigest()[:16]

    # Duration: itunes:duration field (HH:MM:SS or seconds int)
    duration_seconds = _parse_duration(getattr(entry, "itunes_duration", "") or "")

    # Published date
    published_at = ""
    published_parsed = getattr(entry, "published_parsed", None)
    if published_parsed:
        import time  # noqa: PLC0415
        published_at = time.strftime("%Y-%m-%d", published_parsed)

    # Description: prefer summary, fall back to content
    description = getattr(entry, "summary", "") or ""
    if not description:
        content = getattr(entry, "content", [])
        if content:
            description = content[0].get("value", "")

    # Strip HTML tags from description
    import re  # noqa: PLC0415
    description = re.sub(r"<[^>]+>", " ", description).strip()

    return PodcastEpisode(
        episode_id=episode_id,
        title=getattr(entry, "title", "") or episode_id,
        description=description[:2000],  # cap to avoid huge prompts
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        published_at=published_at,
        episode_url=getattr(entry, "link", ""),
        podcast_name=podcast_name,
    )


def _parse_duration(value: str) -> int:
    """Parse itunes:duration into total seconds.

    Handles formats: ``"HH:MM:SS"``, ``"MM:SS"``, or plain integer seconds.
    """
    value = str(value).strip()
    if not value:
        return 0
    if ":" in value:
        parts = value.split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _make_open_resource(ssl_ctx):
    """Return a patched feedparser open_resource that skips SSL verification."""
    import urllib.request as _ur  # noqa: PLC0415

    def _open(url, *args, **kwargs):
        if isinstance(url, str) and url.startswith("http"):
            req = _ur.Request(url)
            return _ur.urlopen(req, context=ssl_ctx, timeout=30)
        return _ur.urlopen(url, timeout=30)

    return _open
