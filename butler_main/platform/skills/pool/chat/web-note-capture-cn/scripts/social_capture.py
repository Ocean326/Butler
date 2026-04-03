#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

TRAILING_URL_CHARS = "，。；！？】）》」』'\""
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


class CaptureError(RuntimeError):
    pass


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def extract_first_url(text: str) -> str:
    match = re.search(r"https?://[^\s\u3000]+", text)
    if not match:
        raise CaptureError("未在输入文本中找到可抓取的 URL。")
    return match.group(0).rstrip(TRAILING_URL_CHARS)


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "zhihu.com" in host:
        return "zhihu"
    if "xiaohongshu.com" in host or "xhslink.com" in host:
        return "xiaohongshu"
    raise CaptureError(f"暂不支持的平台: {host}")


def parse_cookie_header(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    value = raw.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    cookies: dict[str, str] = {}
    for item in value.split(";"):
        if "=" not in item:
            continue
        key, val = item.split("=", 1)
        cookies[key.strip()] = val.strip()
    return cookies


def load_cookie_header(args: argparse.Namespace) -> str | None:
    if args.cookie:
        return args.cookie
    if args.cookie_file:
        return Path(args.cookie_file).read_text(encoding="utf-8").strip()
    if args.cookie_env:
        return os.environ.get(args.cookie_env, "").strip() or None
    return None


def build_session(cookie_header: str | None) -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        }
    )
    cookies = parse_cookie_header(cookie_header)
    if cookies:
        session.cookies.update(cookies)
    return session


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\r\n?", "\n", value).strip()


def strip_xiaohongshu_hashtags(value: str) -> str:
    text = re.sub(r"#([^#\n]+)\[话题\]#", " ", value)
    text = re.sub(r"[@#][^\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def decode_js_string(value: str | None) -> str:
    if value is None:
        return ""
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return html.unescape(value.replace("\\/", "/"))


def strip_html(fragment: str | None) -> str:
    if not fragment:
        return ""
    text = fragment
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"</\s*li\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<\s*li[^>]*>", "- ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return normalize_text(text)


def iso_from_ms(timestamp_ms: int | None) -> str | None:
    if not timestamp_ms:
        return None
    return dt.datetime.fromtimestamp(timestamp_ms / 1000, tz=dt.timezone.utc).astimezone().isoformat()


def regex_first(text: str, patterns: list[str], flags: int = 0, group: int = 1) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(group)
    return None


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def resolve_url(session: requests.Session, url: str, timeout: int) -> tuple[str, str]:
    response = session.get(url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.url, response.text


def guess_image_extension(url: str, content_type: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return suffix
    lowered = (content_type or "").lower()
    if "png" in lowered:
        return ".png"
    if "webp" in lowered:
        return ".webp"
    if "gif" in lowered:
        return ".gif"
    if "bmp" in lowered:
        return ".bmp"
    return ".jpg"


def download_images_for_result(
    session: requests.Session,
    result: dict[str, Any],
    output_dir: Path,
    timeout: int,
) -> None:
    image_urls = result.get("images") or []
    if not image_urls:
        return

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    referer = str(result.get("resolved_url") or result.get("source_url") or "https://www.xiaohongshu.com/")

    assets: list[dict[str, Any]] = []
    for index, image_url in enumerate(image_urls, start=1):
        item: dict[str, Any] = {
            "index": index,
            "url": image_url,
            "status": "pending",
        }
        try:
            response = session.get(
                image_url,
                timeout=timeout,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    "Referer": referer,
                },
            )
            response.raise_for_status()
            suffix = guess_image_extension(image_url, response.headers.get("Content-Type"))
            digest = hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:12]
            file_path = (images_dir / f"{index:02d}_{digest}{suffix}").resolve()
            file_path.write_bytes(response.content)
            item["status"] = "downloaded"
            item["local_path"] = str(file_path)
        except Exception as exc:
            item["status"] = "error"
            item["error"] = str(exc)
        assets.append(item)

    result["image_assets"] = assets
    result["image_local_paths"] = [str(item["local_path"]) for item in assets if item.get("local_path")]
    if result.get("image_local_paths"):
        notes = result.setdefault("notes", [])
        notes.append("图片已下载到本地；后续应优先按 image_local_paths 直接读图整理，而不是默认再跑 OCR。")
    failed = [item for item in assets if item.get("status") != "downloaded"]
    if failed:
        result.setdefault("notes", []).append(f"共有 {len(failed)} 张图片下载失败，详见 image_assets 字段。")


def infer_content_mode(result: dict[str, Any]) -> tuple[str, str]:
    images = result.get("images") or []
    image_paths = result.get("image_local_paths") or []
    title = normalize_text(str(result.get("title") or ""))
    content_text = normalize_text(str(result.get("content_text") or ""))
    visible_text = strip_xiaohongshu_hashtags(content_text)
    generic_title = title in {"搜索小红书", "小红书"} or title.startswith("搜索小红书")
    text_short = len(visible_text) < 80
    hashtag_heavy = bool(content_text) and len(visible_text) < max(20, len(content_text) // 5)

    if images and image_paths and (generic_title or hashtag_heavy or text_short):
        return "image_primary", "正文文本较弱或标题命中站点壳，主要信息大概率在配图里。"
    if images and image_paths:
        return "mixed", "正文与配图都值得读；建议先看正文，再按需补图。"
    return "text_primary", "正文文本已足够作为主整理依据。"


def attach_agent_handoff(result: dict[str, Any]) -> None:
    content_mode, reason = infer_content_mode(result)
    image_paths = result.get("image_local_paths") or []
    should_read_images_first = bool(image_paths) and content_mode == "image_primary"
    next_step = (
        "若用户要求整理到头脑风暴，直接按 image_local_paths 顺序读图并写 Working；不要再次抓取。"
        if should_read_images_first
        else "若用户要求整理到头脑风暴，优先基于 content_text 起稿；再按需补读 image_local_paths。"
    )
    result["agent_handoff"] = {
        "content_mode": content_mode,
        "reason": reason,
        "image_count": len(result.get("images") or []),
        "local_image_count": len(image_paths),
        "should_read_images_first": should_read_images_first,
        "recommended_next_step": next_step,
        "ordered_image_paths": image_paths,
    }


def capture_xiaohongshu(session: requests.Session, source_text: str, timeout: int) -> dict[str, Any]:
    raw_url = extract_first_url(source_text)
    resolved_url, html_text = resolve_url(session, raw_url, timeout)
    parsed = urlparse(resolved_url)
    raw_parsed = urlparse(raw_url)
    query = parse_qs(parsed.query)
    note_id = (
        (query.get("target_note_id") or [None])[0]
        or regex_first(parsed.path, [r"/explore/([0-9a-z]+)", r"/discovery/item/([0-9a-z]+)"], flags=re.I)
        or regex_first(html_text, [r'"noteId":"([0-9a-z]+)"'], flags=re.I)
        or regex_first(raw_parsed.path, [r"/explore/([0-9a-z]+)", r"/discovery/item/([0-9a-z]+)"], flags=re.I)
    )
    if not note_id:
        raise CaptureError("小红书页面已打开，但没有定位到 note_id。")
    xsec_token = (query.get("xsec_token") or [None])[0]

    anchor = html_text.find(f'"noteId":"{note_id}"')
    if anchor == -1:
        anchor = html_text.find(f'"id":"{note_id}"')
    window = html_text[max(0, anchor - 4000) : anchor + 50000] if anchor != -1 else html_text

    title = decode_js_string(
        regex_first(
            window,
            [
                r'"displayTitle":"(.*?)"',
                r'"title":"(.*?)"',
            ],
            flags=re.S,
        )
    )
    desc = decode_js_string(regex_first(window, [r'"desc":"(.*?)"'], flags=re.S))
    author = decode_js_string(
        regex_first(
            window,
            [
                r'"user":\{"userId":"[^"]+","nickname":"(.*?)"',
                r'"nickname":"(.*?)"',
            ],
            flags=re.S,
        )
    )
    author_id = regex_first(window, [r'"userId":"([^"]+)"'])
    ip_location = decode_js_string(regex_first(window, [r'"ipLocation":"(.*?)"']))
    published_raw = regex_first(window, [r'"time":(\d{10,13})'])
    updated_raw = regex_first(window, [r'"lastUpdateTime":(\d{10,13})'])

    tags_blob = regex_first(window, [r'"tagList":\[(.*?)\](?:,"lastUpdateTime"|,"cover")'], flags=re.S)
    tags = dedupe_keep_order(
        [
            decode_js_string(match)
            for match in re.findall(r'"name":"(.*?)"', tags_blob or "", flags=re.S)
        ]
    )

    images = dedupe_keep_order(
        [
            decode_js_string(match)
            for match in re.findall(r'"urlDefault":"(http.*?)"', window, flags=re.S)
        ]
    )

    engagement = {
        "likes": regex_first(window, [r'"likedCount":"([^"]*)"']),
        "comments": regex_first(window, [r'"commentCount":"([^"]*)"']),
        "collects": regex_first(window, [r'"collectedCount":"([^"]*)"']),
        "shares": regex_first(window, [r'"shareCount":"([^"]*)"']),
    }

    content_text = normalize_text(desc)
    if not title:
        title = content_text.splitlines()[0][:50] if content_text else note_id

    return {
        "platform": "xiaohongshu",
        "status": "ok",
        "source_url": raw_url,
        "resolved_url": resolved_url,
        "id": note_id,
        "xsec_token": xsec_token,
        "title": title,
        "author": author,
        "author_id": author_id,
        "published_at": iso_from_ms(int(published_raw)) if published_raw else None,
        "updated_at": iso_from_ms(int(updated_raw)) if updated_raw else None,
        "ip_location": ip_location,
        "content_text": content_text,
        "tags": tags,
        "images": images,
        "engagement": engagement,
        "notes": [
            "当前结果来自分享页 HTML 首屏数据。",
            "默认不含完整评论；若后续要抓评论，可在依赖就绪后再接小红书 API 层。",
        ],
    }


def extract_zhihu_body(html_text: str) -> str:
    json_ld = regex_first(
        html_text,
        [r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'],
        flags=re.S | re.I,
    )
    if json_ld:
        try:
            data = json.loads(json_ld)
            article_body = data.get("articleBody")
            if isinstance(article_body, str) and article_body.strip():
                return normalize_text(article_body)
        except json.JSONDecodeError:
            pass

    rich_text_html = regex_first(
        html_text,
        [
            r'<div[^>]+class="[^"]*RichText ztext Post-RichText[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>\s*</article>',
            r'<div[^>]+class="[^"]*Post-RichText[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>',
            r'<div[^>]+class="[^"]*RichText[^"]*"[^>]*>([\s\S]*?)</div>',
        ],
        flags=re.S | re.I,
    )
    if rich_text_html:
        cleaned = re.sub(r"<style[\s\S]*?</style>", "", rich_text_html, flags=re.I)
        cleaned = re.sub(r"<script[\s\S]*?</script>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<button[\s\S]*?</button>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<figure[\s\S]*?</figure>", "", cleaned, flags=re.I)
        cleaned = re.sub(r'<a [^>]*href="[^"]*"[^>]*>', "", cleaned, flags=re.I)
        cleaned = cleaned.replace("</a>", "")
        return strip_html(cleaned)

    article_html = regex_first(
        html_text,
        [r"<article[\s\S]*?</article>"],
        flags=re.S | re.I,
        group=0,
    )
    return strip_html(article_html)


def capture_zhihu(session: requests.Session, source_text: str, timeout: int) -> dict[str, Any]:
    raw_url = extract_first_url(source_text)
    response = session.get(raw_url, timeout=timeout, allow_redirects=True)
    html_text = response.text
    if response.status_code == 403 or 'id="zh-zse-ck"' in html_text:
        raise CaptureError(
            "知乎返回了 403 / 挑战页。请登录知乎后，把当前文章请求里的 cookie 复制出来，"
            "再用 `--cookie`、`--cookie-file` 或 `--cookie-env` 重跑。"
        )
    response.raise_for_status()

    title = normalize_text(
        html.unescape(
            regex_first(
                html_text,
                [
                    r'<meta[^>]+itemProp="headline"[^>]+content="([^"]+)"',
                    r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
                    r"<title>(.*?)</title>",
                ],
                flags=re.S | re.I,
            )
            or ""
        )
    )
    author = normalize_text(
        html.unescape(
            regex_first(
                html_text,
                [
                    r'<meta[^>]+itemProp="name"[^>]+content="([^"]+)"',
                    r'<meta[^>]+name="author"[^>]+content="([^"]+)"',
                    r'"authorName":"(.*?)"',
                ],
                flags=re.S | re.I,
            )
            or ""
        )
    )
    published_at = regex_first(
        html_text,
        [
            r'<meta[^>]+itemProp="datePublished"[^>]+content="([^"]+)"',
            r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"',
            r'"datePublished":"(.*?)"',
        ],
        flags=re.S | re.I,
    )
    updated_at = regex_first(
        html_text,
        [
            r'<meta[^>]+itemProp="dateModified"[^>]+content="([^"]+)"',
            r'<meta[^>]+property="article:modified_time"[^>]+content="([^"]+)"',
            r'"dateModified":"(.*?)"',
        ],
        flags=re.S | re.I,
    )
    excerpt = normalize_text(
        html.unescape(
            regex_first(
                html_text,
                [
                    r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
                    r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
                ],
                flags=re.S | re.I,
            )
            or ""
        )
    )
    content_text = extract_zhihu_body(html_text)
    article_id = regex_first(raw_url, [r"/p/(\d+)"])

    return {
        "platform": "zhihu",
        "status": "ok",
        "source_url": raw_url,
        "resolved_url": response.url,
        "id": article_id,
        "title": title or article_id,
        "author": author,
        "published_at": published_at,
        "updated_at": updated_at,
        "excerpt": excerpt,
        "content_text": content_text,
        "images": dedupe_keep_order(
            re.findall(r'<img[^>]+src="([^"]+)"', html_text, flags=re.I)
        ),
        "tags": [],
        "engagement": {},
        "notes": [
            "知乎经常返回反爬挑战页；若这次能拿到正文，通常说明 cookie 或当前 IP 已通过校验。",
        ],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# {result.get('title') or result.get('id')}",
        "",
        f"- platform: {result.get('platform')}",
        f"- id: {result.get('id') or ''}",
        f"- source_url: {result.get('source_url') or ''}",
        f"- resolved_url: {result.get('resolved_url') or ''}",
        f"- author: {result.get('author') or ''}",
        f"- published_at: {result.get('published_at') or ''}",
        f"- updated_at: {result.get('updated_at') or ''}",
    ]
    if result.get("engagement"):
        lines.append(f"- engagement: {json.dumps(result['engagement'], ensure_ascii=False)}")
    if result.get("tags"):
        lines.append(f"- tags: {', '.join(result['tags'])}")
    lines.extend(["", "## Content", "", result.get("content_text") or ""])
    images = result.get("images") or []
    if images:
        lines.extend(["", "## Images", ""])
        assets_by_url = {
            str(item.get("url")): item
            for item in (result.get("image_assets") or [])
            if isinstance(item, dict) and item.get("url")
        }
        for index, image in enumerate(images, start=1):
            lines.append(f"### Image {index}")
            lines.append("")
            lines.append(f"- url: {image}")
            asset = assets_by_url.get(str(image)) or {}
            if asset.get("local_path"):
                lines.append(f"- local_path: {asset['local_path']}")
            if asset.get("status"):
                lines.append(f"- download_status: {asset['status']}")
            if asset.get("error"):
                lines.append(f"- error: {asset['error']}")
            lines.append("")
    local_paths = result.get("image_local_paths") or []
    if local_paths:
        lines.extend(["## Image Local Paths", ""])
        lines.extend(f"- {path}" for path in local_paths)
    handoff = result.get("agent_handoff") or {}
    if isinstance(handoff, dict) and handoff:
        lines.extend(["", "## Agent Handoff", ""])
        if handoff.get("content_mode"):
            lines.append(f"- content_mode: {handoff['content_mode']}")
        if handoff.get("reason"):
            lines.append(f"- reason: {handoff['reason']}")
        if handoff.get("should_read_images_first") is not None:
            lines.append(f"- should_read_images_first: {str(bool(handoff['should_read_images_first'])).lower()}")
        if handoff.get("recommended_next_step"):
            lines.append(f"- recommended_next_step: {handoff['recommended_next_step']}")
    notes = result.get("notes") or []
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines).strip() + "\n"


def render_handoff_markdown(result: dict[str, Any], json_path: Path, md_path: Path) -> str:
    handoff = result.get("agent_handoff") or {}
    lines = [
        "# Web Note Agent Handoff",
        "",
        f"- source_json: {json_path.resolve()}",
        f"- source_md: {md_path.resolve()}",
        f"- note_id: {result.get('id') or ''}",
        f"- title: {result.get('title') or ''}",
        f"- author: {result.get('author') or ''}",
    ]
    if isinstance(handoff, dict):
        lines.append(f"- content_mode: {handoff.get('content_mode') or ''}")
        lines.append(f"- should_read_images_first: {str(bool(handoff.get('should_read_images_first'))).lower()}")
        if handoff.get("reason"):
            lines.append(f"- reason: {handoff['reason']}")
        if handoff.get("recommended_next_step"):
            lines.append(f"- recommended_next_step: {handoff['recommended_next_step']}")
    lines.extend(["", "## Ordered Image Paths", ""])
    image_paths = result.get("image_local_paths") or []
    if image_paths:
        lines.extend(f"{index}. {path}" for index, path in enumerate(image_paths, start=1))
    else:
        lines.append("(none)")
    return "\n".join(lines).strip() + "\n"


def write_outputs(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{result['platform']}_{result.get('id') or 'capture'}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    handoff_path = output_dir / f"{stem}_handoff.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    handoff_path.write_text(render_handoff_markdown(result, json_path, md_path), encoding="utf-8")
    return json_path, md_path, handoff_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture zhihu/xiaohongshu note pages into JSON and Markdown.")
    parser.add_argument("source", help="单个 URL，或包含 URL 的分享文本。")
    parser.add_argument("--platform", choices=["auto", "zhihu", "xiaohongshu"], default="auto")
    parser.add_argument("--cookie", help="直接传入 Cookie 请求头值。")
    parser.add_argument("--cookie-file", help="从文本文件读取 Cookie。")
    parser.add_argument("--cookie-env", help="从环境变量读取 Cookie。")
    parser.add_argument("--output-dir", help="输出目录；不传则只打印 JSON。")
    parser.add_argument("--timeout", type=int, default=20, help="单次请求超时秒数。")
    parser.add_argument(
        "--skip-image-download",
        action="store_true",
        help="即使结果包含 images，也不在 output-dir 下下载图片。",
    )
    return parser.parse_args()


def main() -> int:
    configure_stdout()
    args = parse_args()
    cookie_header = load_cookie_header(args)
    session = build_session(cookie_header)
    try:
        raw_url = extract_first_url(args.source)
        platform = args.platform if args.platform != "auto" else detect_platform(raw_url)

        if platform == "xiaohongshu":
            result = capture_xiaohongshu(session, args.source, args.timeout)
        elif platform == "zhihu":
            result = capture_zhihu(session, args.source, args.timeout)
        else:
            raise CaptureError(f"未知平台: {platform}")
    except Exception as exc:
        error_payload = {
            "status": "error",
            "platform": locals().get("platform", "auto"),
            "source_url": locals().get("raw_url", args.source),
            "message": str(exc),
        }
        print(json.dumps(error_payload, ensure_ascii=False, indent=2))
        return 1

    if args.output_dir:
        if not args.skip_image_download:
            download_images_for_result(session, result, Path(args.output_dir), args.timeout)
        attach_agent_handoff(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        json_path, md_path, handoff_path = write_outputs(result, Path(args.output_dir))
        print(f"OUTPUT_JSON={json_path}")
        print(f"OUTPUT_MD={md_path}")
        print(f"OUTPUT_HANDOFF={handoff_path}")
    else:
        attach_agent_handoff(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
