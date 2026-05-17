#!/usr/bin/env python3
import argparse
import html
import json
import re
import sys
from pathlib import Path

from youtube_to_wechat.wechat import (
    WechatError,
    add_draft,
    build_draft_article,
    get_access_token,
    load_env,
    require_env,
    upload_permanent_thumb,
    upload_content_image,
    _markdown_to_html,
)


def _read_article(article_path: Path, access_token: str = "") -> tuple[str, str, str]:
    text = article_path.read_text(encoding="utf-8")
    title = _extract_title(text, article_path)
    digest = _extract_digest(text)
    if article_path.suffix.lower() == ".html":
        content = text
    else:
        content = _markdown_to_html(text)

    # NEW: Find and upload local images to WeChat
    if access_token:
        content = _replace_local_images(content, article_path.parent, access_token)

    return title, digest, content


def _replace_local_images(content: str, base_dir: Path, access_token: str) -> str:
    import re
    def img_replacer(match):
        img_tag = match.group(0)
        src_match = re.search(r'src=[\'"](.+?)[\'"]', img_tag)
        if not src_match:
            return img_tag

        src = src_match.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return img_tag

        local_path = base_dir / src
        if local_path.exists():
            print(f"Uploading embedded image: {src} ...")
            try:
                wechat_url = upload_content_image(access_token, local_path)
                return img_tag.replace(src, wechat_url)
            except Exception as e:
                print(f"Warning: Failed to upload image {src}: {e}")
        return img_tag

    return re.sub(r'<img [^>]+>', img_replacer, content)


def _extract_title(text: str, article_path: Path) -> str:
    import re
    # Search for the first # H1 heading in the entire text
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Fallback to search for <h1> tag
    h1_match = re.search(r"<h1>(.+?)</h1>", text, re.IGNORECASE)
    if h1_match:
        return h1_match.group(1).strip()

    return article_path.parent.name


def _extract_digest(text: str) -> str:
    import re
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("> 摘要："):
            return stripped[len("> 摘要：") :].strip()
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"[#>*_`\\-]+", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:110] or "AI 提炼的投研内容草稿。"


def _source_url(article_path: Path) -> str:
    meta_path = article_path.parent / "meta.json"
    if not meta_path.exists():
        return ""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return meta.get("webpage_url") or meta.get("url") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Push a local article to WeChat draft box.")
    parser.add_argument("article", help="Path to article.md or article.html")
    parser.add_argument("--cover", required=True, help="Cover image path")
    parser.add_argument("--column", default="炼金投研", help="Column name included in title")
    parser.add_argument("--env", default=".env", help="Env file path")
    args = parser.parse_args()

    try:
        article_path = Path(args.article)
        cover_path = Path(args.cover)
        env = load_env(Path(args.env))
        required = require_env(env, ["WECHAT_APPID", "WECHAT_APPSECRET", "WECHAT_AUTHOR"])

        token = get_access_token(required["WECHAT_APPID"], required["WECHAT_APPSECRET"])
        title, digest, content = _read_article(article_path, token)
        thumb_media_id = upload_permanent_thumb(token, cover_path)
        article = build_draft_article(
            title=title,
            author=required["WECHAT_AUTHOR"],
            digest=digest,
            content=content,
            thumb_media_id=thumb_media_id,
            column=args.column,
            source_url=_source_url(article_path),
        )
        draft_media_id = add_draft(token, article)
    except (OSError, WechatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"WeChat draft created: {draft_media_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
