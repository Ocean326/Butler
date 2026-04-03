from __future__ import annotations

import json
import re


DECIDE_BLOCK_MARKER = "【decide】"


def parse_decide_from_reply(text: str) -> tuple[str, list[dict]]:
    if not text:
        return text, []
    if DECIDE_BLOCK_MARKER not in text:
        return text, []
    idx = text.find(DECIDE_BLOCK_MARKER)
    body = text[:idx].rstrip()
    rest = text[idx + len(DECIDE_BLOCK_MARKER) :].lstrip()
    decide_list: list[dict] = []
    try:
        json_text = re.sub(r"^```\w*\s*", "", rest.strip())
        json_text = re.sub(r"\s*```\s*$", "", json_text).strip()
        decoded = json.loads(json_text)
        if isinstance(decoded, list):
            for item in decoded:
                if isinstance(item, dict) and item.get("send"):
                    decide_list.append({"send": str(item["send"]).strip()})
            print(f"[decide解析] 成功解析 {len(decide_list)} 条: {[d.get('send') for d in decide_list]}", flush=True)
        else:
            print(f"[decide解析] decoded 非列表 type={type(decoded)}", flush=True)
    except (json.JSONDecodeError, TypeError) as exc:
        print(f"[decide解析] JSON 解析失败: {exc} | rest_preview={rest[:200]}", flush=True)
    return body, decide_list


__all__ = ["DECIDE_BLOCK_MARKER", "parse_decide_from_reply"]
