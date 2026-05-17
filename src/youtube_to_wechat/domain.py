"""Source-neutral domain names used across the content pipeline.

The package still keeps its MVP ``youtube_to_wechat`` name, but the core
concepts are intentionally source-neutral so YouTube, Xiaoyuzhou, blogs, and
future adapters can share the same vocabulary.
"""
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


SourceType = Literal["youtube", "xiaoyuzhou", "blog"]
TranscriptOrigin = Literal["caption", "audio-transcription", "article-text", "manual"]


@dataclass
class SourceMetadata:
    """Normalized metadata for one source item from any adapter."""

    source_type: SourceType
    source_id: str
    source_url: str
    title: str
    author: str = ""
    published_at: str = ""
    thumbnail_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptArtifact:
    """Clean text plus provenance for how that text was obtained."""

    text: str
    origin: TranscriptOrigin
    language: str = ""
    source_path: str = ""


@dataclass
class WriterProfile:
    """Named writing style and audience target for article generation."""

    name: str
    audience: str
    prompt_style: str
    model: Optional[str] = None


@dataclass
class CompareEvaluation:
    """Configuration name for comparing two transcript or extraction paths."""

    name: str
    left_path: str
    right_path: str
    output_name: str = "comparison.md"
