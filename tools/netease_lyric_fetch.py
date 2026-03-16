#!/usr/bin/env python
import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import requests
except ImportError:  # pragma: no cover - runtime dependency hint
    requests = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "netease_lyric_fetch_log.jsonl"


@dataclass
class RequestAttempt:
    url: str
    status_code: Optional[int] = None
    ok: bool = False
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    response_snippet: Optional[str] = None


@dataclass
class FetchResult:
    timestamp: str
    input_raw: str
    parsed_song_id: Optional[str]
    resolved_url: Optional[str]
    parse_steps: List[str] = field(default_factory=list)
    request_attempts: List[RequestAttempt] = field(default_factory=list)
    got_lyrics: bool = False
    lyrics_snippet: Optional[str] = None
    failure_category: Optional[str] = None
    failure_reason: Optional[str] = None
    next_step_hint: Optional[str] = None


def _safe_snippet(text: str, limit: int = 200) -> str:
    text = text.replace("\r", " ").replace("\n", " ")
    return text[:limit]


def parse_input(input_str: str) -> (Optional[str], Optional[str], List[str]):
    steps: List[str] = []
    input_str = input_str.strip()

    if not input_str:
        steps.append("empty_input")
        return None, None, steps

    # pure numeric -> treat as song id
    if input_str.isdigit():
        steps.append("input_detected_as_song_id")
        song_id = input_str
        resolved_url = f"https://music.163.com/song?id={song_id}"
        steps.append(f"resolved_url_from_id:{resolved_url}")
        return song_id, resolved_url, steps

    # otherwise try to parse from URL
    steps.append("input_detected_as_url_like")
    url = input_str

    # common patterns: ?id=123456, /song?id=123456, /song/123456/, /song/123456
    patterns = [
        r"[?&]id=(\d+)",
        r"/song/(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            song_id = match.group(1)
            steps.append(f"parsed_song_id_via_pattern:{pattern}")
            steps.append(f"parsed_song_id:{song_id}")
            return song_id, url, steps

    steps.append("failed_to_parse_song_id_from_input")
    return None, url, steps


def fetch_lyrics_from_netease(song_id: str) -> (List[RequestAttempt], Optional[str], Optional[str], Optional[str]):
    """
    Perform at least one NetEase lyric API attempt.
    Returns (attempts, lyrics_text_or_none, failure_category, failure_reason).
    """
    attempts: List[RequestAttempt] = []

    if requests is None:
        attempts.append(
            RequestAttempt(
                url="(requests_not_installed)",
                ok=False,
                error_type="dependency_missing",
                error_message="python-requests not installed; cannot perform HTTP requests",
            )
        )
        return attempts, None, "dependency_missing", "python-requests is not installed"

    endpoints = [
        # classic lyric endpoint; may be limited / changed by NetEase
        "https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1",
    ]

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (netease_lyric_fetch_mvp)",
        "Referer": "https://music.163.com/",
    }

    for tmpl in endpoints:
        url = tmpl.format(song_id=song_id)
        attempt = RequestAttempt(url=url)
        try:
            resp = session.get(url, headers=headers, timeout=8)
            attempt.status_code = resp.status_code
            attempt.ok = resp.ok
            attempt.response_snippet = _safe_snippet(resp.text)

            if not resp.ok:
                attempt.error_type = "http_error"
                attempt.error_message = f"http_status_{resp.status_code}"
                attempts.append(attempt)
                continue

            try:
                data = resp.json()
            except Exception as e:  # pragma: no cover - defensive
                attempt.error_type = "json_decode_error"
                attempt.error_message = repr(e)
                attempts.append(attempt)
                continue

            lrc = data.get("lrc") if isinstance(data, dict) else None
            lyric_text = lrc.get("lyric") if isinstance(lrc, dict) else None
            if lyric_text:
                attempts.append(attempt)
                return attempts, lyric_text, None, None

            attempt.error_type = "no_lyric_in_response"
            attempt.error_message = "response JSON lacks 'lrc.lyric'"
            attempts.append(attempt)
        except Exception as e:
            attempt.ok = False
            attempt.error_type = "network_or_runtime_error"
            attempt.error_message = repr(e)
            attempts.append(attempt)

    return attempts, None, "no_usable_lyric_response", "all known endpoints tried but no usable lyrics found"


def write_log_entry(result: FetchResult) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            **asdict(result),
            "request_attempts": [asdict(a) for a in result.request_attempts],
        },
        ensure_ascii=False,
    )
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def maybe_dump_lyrics_files(song_id: str, lyrics: str) -> None:
    """
    Optional: align with existing repo conventions and dump per-song artifacts.
    """
    txt_path = REPO_ROOT / f"netease_lyric_{song_id}.txt"
    json_path = REPO_ROOT / f"netease_lyric_{song_id}.json"

    try:
        if not txt_path.exists():
            txt_path.write_text(lyrics, encoding="utf-8")
    except Exception:
        # best-effort; logging is primary
        pass

    try:
        if not json_path.exists():
            json_path.write_text(
                json.dumps({"song_id": song_id, "lyric_lrc": lyrics}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        pass


def run_once(input_value: str) -> FetchResult:
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    song_id, resolved_url, parse_steps = parse_input(input_value)

    result = FetchResult(
        timestamp=timestamp,
        input_raw=input_value,
        parsed_song_id=song_id,
        resolved_url=resolved_url,
        parse_steps=parse_steps,
    )

    if not song_id:
        result.failure_category = "input_parse_error"
        result.failure_reason = "could_not_extract_song_id_from_input"
        result.next_step_hint = "请提供纯数字 song id，或包含 id=xxx 的完整网易云歌曲链接。"
        return result

    attempts, lyrics, failure_category, failure_reason = fetch_lyrics_from_netease(song_id)
    result.request_attempts = attempts

    if lyrics:
        result.got_lyrics = True
        result.lyrics_snippet = _safe_snippet(lyrics, limit=400)
        result.failure_category = None
        result.failure_reason = None
        result.next_step_hint = "如需进一步处理歌词，可基于已生成的 per-song 文本 / JSON 文件继续开发。"
        maybe_dump_lyrics_files(song_id, lyrics)
    else:
        result.got_lyrics = False
        result.failure_category = failure_category or "unknown_failure"
        result.failure_reason = failure_reason
        result.next_step_hint = (
            "考虑检查本机网络/登录状态，或补充更多 NetEase Web API 端点与反爬策略，再重试同一 song id。"
        )

    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Minimal NetEase lyric fetcher MVP. "
            "Input can be a NetEase song URL or numeric song id. "
            "Outputs a JSONL log entry and optional per-song artifacts."
        )
    )
    parser.add_argument(
        "input",
        metavar="URL_OR_ID",
        help="网易云歌曲短链/长链，或纯数字 song id",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="仅在 stdout 输出结果，不写入 JSONL 日志（调试用）。",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    fetch_result = run_once(args.input)

    # stdout 提供一份可读摘要，便于在 CLI 直接观察
    summary = {
        "input_raw": fetch_result.input_raw,
        "parsed_song_id": fetch_result.parsed_song_id,
        "resolved_url": fetch_result.resolved_url,
        "got_lyrics": fetch_result.got_lyrics,
        "failure_category": fetch_result.failure_category,
        "failure_reason": fetch_result.failure_reason,
        "lyrics_snippet": fetch_result.lyrics_snippet,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not args.no_log:
        write_log_entry(fetch_result)

    return 0


if __name__ == "__main__":
    sys.exit(main())

