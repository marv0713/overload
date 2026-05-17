import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


SourceConfigType = Literal["youtube_channel"]


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


@dataclass
class SourceConfigFile:
    sources: list[SourceConfig] = field(default_factory=list)


def load_source_config(path: Path) -> SourceConfigFile:
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
    )
