import re


TIMESTAMP_LINE = re.compile(
    r"^\d\d:\d\d:\d\d[.,]\d{3}\s+-->\s+\d\d:\d\d:\d\d[.,]\d{3}"
)
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
