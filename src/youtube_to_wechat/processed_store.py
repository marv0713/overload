import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from youtube_to_wechat.youtube_channel import ChannelVideo


def slugify_source_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "source"


class ProcessedStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data = self._load()

    def is_processed(self, video_id: str) -> bool:
        return video_id in self._data.get("processed_videos", {})

    def processed_video_ids(self) -> set[str]:
        return set(self._data.get("processed_videos", {}).keys())

    def processed_video_ids_for_source(self, source_slug: str) -> set[str]:
        return {
            video_id
            for video_id, record in self._data.get("processed_videos", {}).items()
            if record.get("source_slug") == source_slug
        }

    def has_source(self, source_slug: str) -> bool:
        return source_slug in self._data.get("sources", {})

    def allocate_issue(self, series: str) -> str:
        series_record = self._data.setdefault("series", {}).setdefault(
            series, {"next_issue": 1}
        )
        issue_number = int(series_record.get("next_issue", 1))
        series_record["next_issue"] = issue_number + 1
        self._save()
        return f"No.{issue_number:03d}"

    def get_current_issue(self, series: str) -> str:
        series_record = self._data.get("series", {}).get(series, {"next_issue": 1})
        issue_number = max(1, int(series_record.get("next_issue", 1)) - 1)
        return f"No.{issue_number:03d}"

    def processing_record(self, video_id: str) -> dict[str, Any]:
        return self._data.get("processed_videos", {})[video_id]

    def source_record(self, source_slug: str) -> dict[str, Any]:
        return self._data.get("sources", {})[source_slug]

    def record_source_scan(
        self,
        source_name: str,
        source_slug: str,
        videos: list[ChannelVideo],
    ) -> None:
        self._data.setdefault("sources", {})[source_slug] = {
            "name": source_name,
            "scanned_at": _now(),
            "latest_videos": [
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "duration_seconds": video.duration_seconds,
                    "published_at": video.published_at,
                }
                for video in videos
            ],
        }
        self._save()

    def mark_processed(
        self,
        video_id: str,
        source_name: str,
        source_slug: str,
        title: str,
        url: str,
        output_dir: str,
        status: str,
        series: str = "",
        issue: str = "",
        writer_profile: str = "",
        ticker: str = "",
        cover_hook: str = "",
    ) -> None:
        record = {
            "source_name": source_name,
            "source_slug": source_slug,
            "title": title,
            "url": url,
            "output_dir": output_dir,
            "status": status,
            "processed_at": _now(),
        }
        if series:
            record["series"] = series
        if issue:
            record["issue"] = issue
        if writer_profile:
            record["writer_profile"] = writer_profile
        if ticker:
            record["ticker"] = ticker
        if cover_hook:
            record["cover_hook"] = cover_hook
        self._data.setdefault("processed_videos", {})[video_id] = record
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2) + "\n")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"sources": {}, "processed_videos": {}, "series": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
