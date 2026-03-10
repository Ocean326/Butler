# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta

from agent import load_config
from memory_manager import MemoryManager


def _default_config_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "configs", "butler_bot.json")


def _load_runtime_config(config_path: str) -> dict:
    path = config_path or _default_config_path()
    cfg = load_config(path)
    if not cfg.get("workspace_root"):
        cfg["workspace_root"] = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return cfg


def _make_manager(cfg: dict) -> MemoryManager:
    return MemoryManager(config_provider=lambda: cfg, run_model_fn=lambda *_: ("", False))


def _parse_date(value: str, end_of_day: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d" and end_of_day:
                return parsed + timedelta(days=1) - timedelta(seconds=1)
            return parsed
        except Exception:
            pass
    raise ValueError(f"无法解析日期: {value}")


def _print_json(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="本机调用飞书 管家bot 记忆接口")
    parser.add_argument("--config", default=_default_config_path(), help="配置文件路径")

    subparsers = parser.add_subparsers(dest="command", required=True)

    recent_list = subparsers.add_parser("recent-list", help="读取 recent_memory")
    recent_list.add_argument("--limit", type=int, default=10)
    recent_list.add_argument("--scope", choices=["talk", "beat"], default="talk")
    recent_list.add_argument("--json", action="store_true")

    recent_add = subparsers.add_parser("recent-add", help="追加一条短期记忆")
    recent_add.add_argument("--topic", required=True)
    recent_add.add_argument("--summary", required=True)
    recent_add.add_argument("--user-prompt", default="")
    recent_add.add_argument("--action", action="append", default=[])
    recent_add.add_argument("--scope", choices=["talk", "beat"], default="talk")
    recent_add.add_argument("--json", action="store_true")

    local_query = subparsers.add_parser("local-query", help="查询长期记忆")
    local_query.add_argument("--keyword", default="")
    local_query.add_argument("--since", default="")
    local_query.add_argument("--until", default="")
    local_query.add_argument("--limit", type=int, default=20)
    local_query.add_argument("--json", action="store_true")

    local_add = subparsers.add_parser("local-add", help="追加一条长期记忆")
    local_add.add_argument("--title", required=True)
    local_add.add_argument("--summary", required=True)
    local_add.add_argument("--keywords", default="")

    paths_cmd = subparsers.add_parser("paths", help="输出记忆目录路径")
    paths_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args()
    cfg = _load_runtime_config(args.config)
    manager = _make_manager(cfg)
    workspace = str(cfg.get("workspace_root") or os.getcwd())

    if args.command == "recent-list":
        entries = manager.get_recent_entries(workspace, limit=args.limit, pool=args.scope)
        if args.json:
            _print_json(entries)
        else:
            for item in entries:
                print(f"- [{item.get('timestamp')}] {item.get('topic')}: {item.get('summary')}")
        return 0

    if args.command == "recent-add":
        entry = manager.append_recent_entry(
            workspace,
            topic=args.topic,
            summary=args.summary,
            raw_user_prompt=args.user_prompt,
            next_actions=args.action,
            pool=args.scope,
        )
        if args.json:
            _print_json(entry)
        else:
            print(f"已写入 recent_memory: {entry.get('memory_id')}")
        return 0

    if args.command == "local-query":
        since = _parse_date(args.since) if args.since else None
        until = _parse_date(args.until, end_of_day=True) if args.until else None
        matches = manager.query_local_memory(
            workspace,
            keyword=args.keyword,
            since=since,
            until=until,
            limit=args.limit,
        )
        if args.json:
            _print_json(matches)
        else:
            for item in matches:
                print(f"- [{item.get('updated_at')}] {item.get('title')} | {item.get('path')}")
                print(f"  {item.get('snippet')}")
        return 0

    if args.command == "local-add":
        keywords = [x.strip() for x in str(args.keywords or "").split(",") if x.strip()]
        manager.append_local_memory_entry(workspace, args.title, args.summary, keywords)
        print(f"已写入 local_memory: {args.title}")
        return 0

    if args.command == "paths":
        recent_dir, recent_file, local_dir = manager._ensure_memory_dirs(workspace)
        index_path, l1_dir, l2_dir = manager._local_layer_paths(local_dir)
        payload = {
            "workspace_root": workspace,
            "recent_memory_dir": str(recent_dir),
            "recent_memory_file": str(recent_file),
            "beat_recent_memory_dir": str(manager._recent_pool_paths(workspace, "beat")[0]),
            "beat_recent_memory_file": str(manager._recent_pool_paths(workspace, "beat")[1]),
            "heartbeat_tasks_md_file": str(manager._heartbeat_tasks_md_path(workspace)),
            "local_memory_dir": str(local_dir),
            "local_memory_index_file": str(index_path),
            "local_memory_l1_dir": str(l1_dir),
            "local_memory_l2_dir": str(l2_dir),
            "heart_beat_memory_file": str(manager._heartbeat_memory_path(workspace)),
            "heartbeat_long_tasks_file": str(manager._heartbeat_long_tasks_path(workspace)),
        }
        if args.json:
            _print_json(payload)
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())