# YouTube Source Adapter MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first source adapter for a broader content pipeline: accept one YouTube URL, fetch metadata and captions with `yt-dlp`, clean transcript text, and write local output files for later article generation.

**Architecture:** Keep the first version modular but small: source parsing, transcript cleanup, YouTube fetching, compare evaluation, writer profile, and output writing live in separate modules under `src/youtube_to_wechat`. The single-video CLI produces deterministic files under `outputs/youtube/<video_id>/`; channel sources produce files under `outputs/youtube/<source_slug>/<video_id>/`. Future Xiaoyuzhou and blog adapters should reuse the same source metadata and transcript vocabulary.

**Tech Stack:** Python 3 standard library, `yt-dlp` command line when installed, `unittest` for tests, JSON/Markdown/HTML local output.

## Naming Boundaries

- `source`: any external content adapter. The current adapter is YouTube; future adapters include Xiaoyuzhou and blogs.
- `transcript`: normalized text for model input, with an origin such as `caption`, `audio-transcription`, or `article-text`.
- `writer profile`: a named prompt/audience/style configuration. The current experiment profile is `alchemy-research`.
- `compare evaluation`: an explicit evaluation workflow. Current `--compare` runs `caption-vs-audio`; it is not the default publishing path.
- `processed store`: `data/processed.json` records each channel's latest scanned videos and each processed video's status/output path.

---

### Task 1: Python Project Skeleton

**Files:**
- Create: `src/youtube_to_wechat/__init__.py`
- Create: `src/youtube_to_wechat/youtube_meta.py`
- Create: `src/youtube_to_wechat/cleaner.py`
- Create: `src/youtube_to_wechat/output.py`
- Create: `src/youtube_to_wechat/ytdlp.py`
- Create: `scripts/process_youtube.py`
- Create: `tests/test_youtube_meta.py`
- Create: `tests/test_cleaner.py`

- [ ] **Step 1: Write failing URL parsing tests**

Create `tests/test_youtube_meta.py`:

```python
import unittest

from youtube_to_wechat.youtube_meta import extract_video_id


class ExtractVideoIdTests(unittest.TestCase):
    def test_extracts_video_id_from_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=6C7FjGs22g8"),
            "6C7FjGs22g8",
        )

    def test_extracts_video_id_from_short_url(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/6C7FjGs22g8?si=abc"),
            "6C7FjGs22g8",
        )

    def test_rejects_non_youtube_url(self):
        with self.assertRaises(ValueError):
            extract_video_id("https://example.com/watch?v=6C7FjGs22g8")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_youtube_meta -v
```

Expected: FAIL because `youtube_to_wechat.youtube_meta` does not exist.

- [ ] **Step 3: Implement URL parsing**

Create `src/youtube_to_wechat/__init__.py` as an empty package marker.

Create `src/youtube_to_wechat/youtube_meta.py`:

```python
from urllib.parse import parse_qs, urlparse


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            if video_id:
                return video_id

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id:
            return video_id

    raise ValueError(f"Unsupported YouTube URL: {url}")
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_youtube_meta -v
```

Expected: 3 tests pass.

### Task 2: Transcript Cleaner

**Files:**
- Create: `tests/test_cleaner.py`
- Modify: `src/youtube_to_wechat/cleaner.py`

- [ ] **Step 1: Write failing cleaner tests**

Create `tests/test_cleaner.py`:

```python
import unittest

from youtube_to_wechat.cleaner import clean_vtt


class CleanVttTests(unittest.TestCase):
    def test_removes_vtt_timestamps_and_deduplicates_lines(self):
        raw = """WEBVTT

00:00:00.000 --> 00:00:01.000
Hello world

00:00:01.000 --> 00:00:02.000
Hello world
This is useful

00:00:02.000 --> 00:00:03.000
[Music]
"""

        self.assertEqual(clean_vtt(raw), "Hello world\nThis is useful")

    def test_removes_inline_vtt_tags(self):
        raw = """WEBVTT

00:00:00.000 --> 00:00:01.000
<c.colorE5E5E5>Hello</c> <00:00:00.500>there
"""

        self.assertEqual(clean_vtt(raw), "Hello there")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cleaner -v
```

Expected: FAIL because `clean_vtt` does not exist.

- [ ] **Step 3: Implement cleaner**

Create `src/youtube_to_wechat/cleaner.py`:

```python
import re


TIMESTAMP_LINE = re.compile(r"^\d\d:\d\d:\d\d[.,]\d{3}\s+-->\s+\d\d:\d\d:\d\d[.,]\d{3}")
INLINE_TIMESTAMP = re.compile(r"<\d\d:\d\d:\d\d[.,]\d{3}>")
HTML_TAG = re.compile(r"</?[^>]+>")
SKIP_LINES = {"WEBVTT", "Kind: captions", "Language: en", "[Music]", "(Music)"}


def clean_vtt(raw: str) -> str:
    lines = []
    previous = None

    for original_line in raw.splitlines():
        line = original_line.strip()
        if not line:
            continue
        if line in SKIP_LINES:
            continue
        if TIMESTAMP_LINE.match(line):
            continue
        if line.isdigit():
            continue

        line = INLINE_TIMESTAMP.sub("", line)
        line = HTML_TAG.sub("", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if line == previous:
            continue

        lines.append(line)
        previous = line

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cleaner -v
```

Expected: 2 tests pass.

### Task 3: Output Writer and CLI

**Files:**
- Modify: `src/youtube_to_wechat/output.py`
- Modify: `src/youtube_to_wechat/ytdlp.py`
- Modify: `scripts/process_youtube.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Write failing output test**

Create `tests/test_output.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from youtube_to_wechat.output import write_outputs


class OutputTests(unittest.TestCase):
    def test_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = write_outputs(
                base_dir=Path(temp_dir),
                video_id="6C7FjGs22g8",
                meta={"video_id": "6C7FjGs22g8", "title": "Demo"},
                transcript="Transcript body",
            )

            self.assertEqual(output_dir.name, "6C7FjGs22g8")
            self.assertEqual((output_dir / "transcript.txt").read_text(), "Transcript body\n")
            meta = json.loads((output_dir / "meta.json").read_text())
            self.assertEqual(meta["title"], "Demo")
            self.assertIn("Demo", (output_dir / "article.md").read_text())
            self.assertIn("<h1>Demo</h1>", (output_dir / "article.html").read_text())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_output -v
```

Expected: FAIL because `write_outputs` does not exist.

- [ ] **Step 3: Implement output and ytdlp wrapper**

Create `src/youtube_to_wechat/output.py`:

```python
import html
import json
from pathlib import Path
from typing import Any


def write_outputs(base_dir: Path, video_id: str, meta: dict[str, Any], transcript: str) -> Path:
    output_dir = base_dir / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    title = meta.get("title") or video_id
    source_url = meta.get("webpage_url") or meta.get("url") or f"https://www.youtube.com/watch?v={video_id}"
    article_md = (
        f"# {title}\n\n"
        f"来源：{source_url}\n\n"
        "## 待提取观点\n\n"
        "第一版先完成视频文本提取。下一步会接入模型，将 transcript 生成公众号文章。\n"
    )
    article_html = (
        f"<h1>{html.escape(title)}</h1>\n"
        f"<p>来源：<a href=\"{html.escape(source_url)}\">{html.escape(source_url)}</a></p>\n"
        "<h2>待提取观点</h2>\n"
        "<p>第一版先完成视频文本提取。下一步会接入模型，将 transcript 生成公众号文章。</p>\n"
    )

    (output_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    (output_dir / "transcript.txt").write_text(transcript.rstrip() + "\n")
    (output_dir / "article.md").write_text(article_md)
    (output_dir / "article.html").write_text(article_html)
    (output_dir / "run.json").write_text(json.dumps({"status": "ok"}, ensure_ascii=False, indent=2) + "\n")

    return output_dir
```

Create `src/youtube_to_wechat/ytdlp.py`:

```python
import json
import shutil
import subprocess
from pathlib import Path

from youtube_to_wechat.cleaner import clean_vtt


class YtDlpError(RuntimeError):
    pass


def require_ytdlp() -> str:
    executable = shutil.which("yt-dlp")
    if executable is None:
        raise YtDlpError("yt-dlp is not installed. Install it with: python3 -m pip install yt-dlp")
    return executable


def fetch_info(url: str) -> dict:
    executable = require_ytdlp()
    result = subprocess.run(
        [executable, "--dump-single-json", "--skip-download", url],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise YtDlpError(result.stderr.strip() or "yt-dlp failed while fetching metadata")
    return json.loads(result.stdout)


def fetch_transcript(url: str, work_dir: Path, languages: list[str] | None = None) -> str:
    executable = require_ytdlp()
    languages = languages or ["zh-Hans", "zh", "en"]
    work_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            executable,
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            ",".join(languages),
            "--sub-format",
            "vtt",
            "-o",
            str(work_dir / "%(id)s.%(ext)s"),
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise YtDlpError(result.stderr.strip() or "yt-dlp failed while fetching subtitles")

    vtt_files = sorted(work_dir.glob("*.vtt"))
    if not vtt_files:
        raise YtDlpError("No subtitles were available for this video.")

    return clean_vtt(vtt_files[0].read_text(errors="ignore"))
```

- [ ] **Step 4: Implement CLI**

Create `scripts/process_youtube.py`:

```python
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from youtube_to_wechat.output import write_outputs
from youtube_to_wechat.youtube_meta import extract_video_id
from youtube_to_wechat.ytdlp import YtDlpError, fetch_info, fetch_transcript


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one YouTube video into local draft files.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--output-dir", default="outputs/youtube", help="Base output directory")
    args = parser.parse_args()

    try:
        video_id = extract_video_id(args.url)
        meta = fetch_info(args.url)
        meta.setdefault("video_id", video_id)
        meta.setdefault("url", args.url)
        transcript = fetch_transcript(args.url, Path(args.output_dir) / video_id / "_subs")
        output_dir = write_outputs(Path(args.output_dir), video_id, meta, transcript)
    except (ValueError, YtDlpError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote outputs to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected: all tests pass.

### Task 4: Try the Sample Video

**Files:**
- Generated: `outputs/youtube/6C7FjGs22g8/*`

- [ ] **Step 1: Check local dependencies**

Run:

```bash
which yt-dlp
```

Expected: prints a path. If not, install `yt-dlp`.

- [ ] **Step 2: Run the sample video**

Run:

```bash
PYTHONPATH=src python3 scripts/process_youtube.py "https://www.youtube.com/watch?v=6C7FjGs22g8"
```

Expected: output directory is printed, or a clear YouTube/subtitle error is printed.

- [ ] **Step 3: Inspect generated files**

Run:

```bash
find outputs/youtube/6C7FjGs22g8 -maxdepth 1 -type f -print
```

Expected: `meta.json`, `transcript.txt`, `article.md`, `article.html`, and `run.json` exist when the sample succeeds.
