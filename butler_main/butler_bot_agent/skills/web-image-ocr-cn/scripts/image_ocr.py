#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def configure_stdout() -> None:
    try:
        import sys

        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()


def load_capture_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"capture json 必须是对象，当前类型: {type(data)!r}")
    return data


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_image(url: str, output_dir: Path, timeout: int = 20) -> Optional[Path]:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:
        return None

    ext = ".jpg"
    lowered = url.lower()
    if any(lowered.endswith(suffix) for suffix in (".png", ".jpeg", ".webp", ".gif")):
        ext = Path(lowered).suffix or ".jpg"

    safe_name = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
    file_path = output_dir / f"img_{safe_name}{ext}"
    file_path.write_bytes(resp.content)
    return file_path


def get_openai_config() -> Dict[str, str]:
    api_key = os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY 环境变量，无法执行 OpenAI OCR。")

    base_url = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    model = os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini"
    return {"api_key": api_key, "base_url": base_url.rstrip("/"), "model": model}


def call_openai_ocr(
    image_path: Path, config: Dict[str, str], prompt: str = "请帮我完整读出图片里的中文和英文文字，按自然段落输出。"
) -> str:
    img_bytes = image_path.read_bytes()
    b64 = base64.b64encode(img_bytes).decode("ascii")

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                        },
                    },
                ],
            }
        ],
    }

    url = f"{config['base_url']}/chat/completions"
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return json.dumps(data, ensure_ascii=False)


_paddle_ocr = None


def get_paddle_ocr():
    """
    延迟初始化 PaddleOCR，避免在未安装依赖的环境中直接导入失败。
    """
    global _paddle_ocr
    if _paddle_ocr is not None:
        return _paddle_ocr

    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "无法导入 PaddleOCR，请先在当前虚拟环境中安装：\n"
            "  pip install \"paddlepaddle>=2.0.0\" paddleocr\n"
            f"原始错误：{exc}"
        )

    # 中文优先，开启方向分类
    _paddle_ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
    return _paddle_ocr


def call_paddle_ocr(image_path: Path) -> str:
    """
    使用 PaddleOCR 对本地图片做 OCR，返回按行拼接的纯文本。
    """
    ocr = get_paddle_ocr()
    # result: List[List[Tuple[box, (text, score)]]]
    result = ocr.ocr(str(image_path), cls=True)
    lines: List[str] = []
    for page in result:
        for line in page:
            if not line or len(line) < 2:
                continue
            text = line[1][0]
            if text:
                lines.append(str(text))
    return "\n".join(lines).strip()


def render_markdown(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Web Image OCR Result")
    lines.append("")
    lines.append(f"- created_at: {payload.get('created_at', '')}")
    source = payload.get("source") or {}
    if isinstance(source, dict):
        capture_path = source.get("capture_json_path") or ""
        if capture_path:
            lines.append(f"- capture_json_path: {capture_path}")
    lines.append("")

    images = payload.get("images") or []
    for idx, item in enumerate(images, start=1):
        if not isinstance(item, dict):
            continue
        lines.append(f"## Image {idx}")
        lines.append("")
        if item.get("url"):
            lines.append(f"源地址: {item['url']}")
        if item.get("saved_path"):
            lines.append(f"本地文件: {item['saved_path']}")
        if item.get("error"):
            lines.append("")
            lines.append("识别失败：")
            lines.append("")
            lines.append(item["error"])
        else:
            lines.append("")
            lines.append("识别结果：")
            lines.append("")
            lines.append(item.get("ocr_text") or "(空)")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对网页抓取结果中的图片执行 OCR（中文优先）。")
    parser.add_argument(
        "--from-capture-json",
        help="来自 web-note-capture-cn 的 JSON 结果路径，读取其中的 images 字段作为图片 URL 列表。",
    )
    parser.add_argument(
        "--image-url",
        action="append",
        help="单张图片 URL，可重复多次指定。",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="输出目录，将写入 OCR JSON 与 Markdown。",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="只下载图片，不调用 OpenAI OCR（调试或无 Key 时可用）。",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="下载图片超时时间（秒）。",
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "paddle"],
        default="paddle",
        help="OCR 后端：paddle（默认，本地 PaddleOCR）或 openai。",
    )
    return parser.parse_args()


def collect_image_urls(args: argparse.Namespace) -> tuple[List[str], Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    urls: List[str] = []

    if args.from_capture_json:
        capture_path = Path(args.from_capture_json)
        data = load_capture_json(capture_path)
        images = data.get("images") or []
        if isinstance(images, list):
            urls.extend([u for u in images if isinstance(u, str) and u.strip()])
        meta["source"] = {
            "type": "web-note-capture-cn",
            "capture_json_path": str(capture_path),
            "platform": data.get("platform"),
            "id": data.get("id"),
            "title": data.get("title"),
        }

    if args.image_url:
        urls.extend([u for u in args.image_url if isinstance(u, str) and u.strip()])

    # 去重保序
    seen: set[str] = set()
    deduped: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    return deduped, meta


def main() -> int:
    configure_stdout()
    args = parse_args()

    image_urls, meta = collect_image_urls(args)
    if not image_urls:
        print(json.dumps({"status": "error", "message": "未获得任何图片 URL。"}, ensure_ascii=False, indent=2))
        return 1

    output_dir = ensure_output_dir(Path(args.output_dir))
    images_dir = ensure_output_dir(output_dir / "images")

    ocr_backend = args.backend
    ocr_config: Optional[Dict[str, str]] = None
    if not args.download_only and ocr_backend == "openai":
        try:
            ocr_config = get_openai_config()
        except Exception as exc:
            # 降级：依然下载图片，但在结果中标出无法 OCR
            ocr_config = None
            meta.setdefault("warnings", []).append(str(exc))

    results: List[Dict[str, Any]] = []
    for url in image_urls:
        item: Dict[str, Any] = {"url": url}
        img_path = download_image(url, images_dir, timeout=args.timeout)
        if img_path is None:
            item["error"] = "图片下载失败或超时。"
            results.append(item)
            continue
        item["saved_path"] = str(img_path)

        if args.download_only:
            item["error"] = item.get("error") or "未执行 OCR（download-only 模式）。"
            results.append(item)
            continue

        try:
            if ocr_backend == "openai":
                if ocr_config is None:
                    item["error"] = item.get("error") or "未执行 OCR（缺少 OpenAI 配置）。"
                else:
                    text = call_openai_ocr(img_path, ocr_config)
                    item["ocr_text"] = text
            elif ocr_backend == "paddle":
                text = call_paddle_ocr(img_path)
                if text:
                    item["ocr_text"] = text
                else:
                    item["error"] = item.get("error") or "PaddleOCR 未识别出有效文字。"
            else:
                item["error"] = item.get("error") or f"未知 OCR 后端: {ocr_backend}"
        except Exception as exc:
            item["error"] = f"OCR 调用失败: {exc}"

        results.append(item)

    payload: Dict[str, Any] = {
        "status": "ok",
        "created_at": iso_now(),
        "source": meta.get("source"),
        "warnings": meta.get("warnings", []),
        "images": results,
    }

    # 若来自 capture json，则沿用其 stem 作为前缀；否则用通用前缀
    stem = "web_image_ocr"
    source = payload.get("source") or {}
    if isinstance(source, dict) and source.get("capture_json_path"):
        stem = f"{Path(source['capture_json_path']).stem}_ocr"

    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"OUTPUT_JSON={json_path}")
    print(f"OUTPUT_MD={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

