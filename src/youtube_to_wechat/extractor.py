"""Opinion extraction plugin interface and built-in implementations.

Usage::

    from youtube_to_wechat.extractor import GeminiExtractor

    extractor = GeminiExtractor()  # reads GEMINI_API_KEY from env
    result = extractor.extract(transcript="...", meta={"title": "..."})
    print(result.opinions)

To add a new backend, subclass ``BaseExtractor`` and implement
``extract(transcript, meta) -> OpinionResult``.
"""
import abc
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OpinionResult:
    """Structured output from an opinion extraction pass.

    Attributes:
        opinions:     Core opinions expressed in the content (3–8 full sentences).
        summary:      One-sentence summary of the main theme (≤ 50 chars).
        key_points:   Short bullet-style takeaways (≤ 20 chars each).
        review_notes: Facts or claims that require human verification.
    """

    opinions: List[str] = field(default_factory=list)
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    review_notes: List[str] = field(default_factory=list)


class ExtractorError(RuntimeError):
    """Raised when opinion extraction fails."""


class BaseExtractor(abc.ABC):
    """Plugin interface for extracting structured opinions from a transcript.

    Each backend receives the cleaned transcript text and a metadata dict
    (same shape as ``meta.json`` written by :mod:`youtube_to_wechat.output`)
    and returns an :class:`OpinionResult`.
    """

    @abc.abstractmethod
    def extract(self, transcript: str, meta: dict) -> OpinionResult:
        """Extract structured opinions from a transcript.

        Args:
            transcript: Cleaned plain-text transcript (output of
                :func:`~youtube_to_wechat.cleaner.clean_vtt` or a transcriber).
            meta: Video metadata dict (at minimum ``{"title": "..."}``).

        Returns:
            :class:`OpinionResult` with populated fields.

        Raises:
            ExtractorError: On API or parsing failures.
        """


# ---------------------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------------------

_GEMINI_SYSTEM_PROMPT = """\
你是一位专业的内容分析师。你将收到一段视频的文字转录，请从中提取核心观点并输出结构化 JSON。

输出格式（严格 JSON，不要 markdown 代码块）：
{
  "summary": "一句话概括视频核心主题（不超过 50 字）",
  "opinions": [
    "核心观点 1（完整陈述句，有主语有观点）",
    "核心观点 2"
  ],
  "key_points": [
    "要点 1（不超过 20 字）",
    "要点 2"
  ],
  "review_notes": [
    "需要人工核查的事实点或存疑信息（如没有可为空列表）"
  ]
}

要求：
- opinions 提取 3–8 条，每条是完整陈述句
- key_points 提取 3–6 条，每条不超过 20 字
- review_notes 如果没有存疑点请返回空列表 []
- 所有内容用中文输出
- 严格只输出 JSON，不要任何额外说明或 markdown 包裹
"""

# Transcript is truncated to this many characters to stay within model limits.
_MAX_TRANSCRIPT_CHARS = 12_000


class GeminiExtractor(BaseExtractor):
    """Opinion extractor powered by Google Gemini.

    Args:
        model: Gemini model name.  Defaults to ``"gemini-2.5-flash"``.
        api_key: Gemini API key.  Falls back to the ``GEMINI_API_KEY``
            environment variable when not provided.

    Example::

        extractor = GeminiExtractor(model="gemini-2.5-flash")
        result = extractor.extract(transcript, meta)
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
    ) -> None:
        self.model_name = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def _get_client(self):
        """Return a configured google.genai Client."""
        try:
            from google import genai  # noqa: PLC0415
        except ImportError as exc:
            raise ExtractorError(
                "google-genai is not installed. "
                "Install it with: pip install google-genai"
            ) from exc
        if not self.api_key:
            raise ExtractorError(
                "GEMINI_API_KEY is not set. "
                "Export it as an environment variable or pass api_key= to GeminiExtractor."
            )
        return genai.Client(api_key=self.api_key)

    def extract(self, transcript: str, meta: dict) -> OpinionResult:
        """Send transcript to Gemini and parse the JSON response.

        Args:
            transcript: Cleaned transcript text.
            meta: Video metadata dict.

        Returns:
            Parsed :class:`OpinionResult`.

        Raises:
            ExtractorError: On API errors or unparseable responses.
        """
        if not transcript.strip():
            return OpinionResult(review_notes=["transcript 为空，无法提取观点"])

        title = meta.get("title", "")
        truncated = transcript[:_MAX_TRANSCRIPT_CHARS]
        # Embed system prompt in the user message for the new SDK
        prompt = (
            f"{_GEMINI_SYSTEM_PROMPT}\n\n"
            f"视频标题：{title}\n\nTranscript：\n\n{truncated}"
        )

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            raw = response.text.strip()
        except ExtractorError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ExtractorError(f"Gemini API call failed: {exc}") from exc

        return _parse_opinion_json(raw)


def _parse_opinion_json(raw: str) -> OpinionResult:
    """Parse a JSON string (possibly wrapped in markdown fences) into OpinionResult."""
    text = raw

    # Strip ```json ... ``` or ``` ... ``` fences if present.
    if text.startswith("```"):
        parts = text.split("```")
        # parts[0] is empty, parts[1] is the inner block, parts[2] is trailing
        inner = parts[1] if len(parts) >= 2 else text
        if inner.startswith("json"):
            inner = inner[4:]
        text = inner.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return OpinionResult(
            summary="JSON 解析失败，原始回复见 review_notes",
            review_notes=[f"原始模型回复（前 500 字）：{raw[:500]}"],
        )

    return OpinionResult(
        opinions=data.get("opinions", []),
        summary=data.get("summary", ""),
        key_points=data.get("key_points", []),
        review_notes=data.get("review_notes", []),
    )
