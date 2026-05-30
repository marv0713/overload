import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


SourceConfigType = Literal["youtube_channel", "podcast_rss"]


@dataclass
class SourceConfig:
    type: SourceConfigType
    name: str
    url: str
    enabled: bool = True
    series: str = "炼金投研"
    priority: int = 100
    min_duration_seconds: int = 600
    writer_profile: str = "alchemy-research"
    compare_evaluation: str = "none"
    rss_url: str = ""  # Required for podcast_rss sources


@dataclass
class SourceConfigFile:
    sources: list[SourceConfig] = field(default_factory=list)


import os

def load_source_config(path: Path) -> SourceConfigFile:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if db_url:
        try:
            import psycopg2
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT value FROM overlord_config WHERE key = 'sources';")
                    row = cur.fetchone()
                    if row and row[0]:
                        sources = [_source_from_dict(item) for item in row[0].get("sources", [])]
                        return SourceConfigFile(sources=sources)
        except Exception as e:
            print(f"Warning: Failed to load sources from Supabase, falling back to local: {e}")

    data = json.loads(path.read_text(encoding="utf-8"))
    sources = [_source_from_dict(item) for item in data.get("sources", [])]
    return SourceConfigFile(sources=sources)


def _source_from_dict(data: dict[str, Any]) -> SourceConfig:
    return SourceConfig(
        type=data["type"],
        name=data["name"],
        url=data["url"],
        enabled=data.get("enabled", True),
        series=data.get("series", "炼金投研"),
        priority=int(data.get("priority", 100)),
        min_duration_seconds=int(data.get("min_duration_seconds", 600)),
        writer_profile=data.get("writer_profile", "alchemy-research"),
        compare_evaluation=data.get("compare_evaluation", "none"),
        rss_url=data.get("rss_url", ""),
    )
