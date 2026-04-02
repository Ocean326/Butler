from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".py",
    ".ps1",
}

LEGACY_PATTERNS = (
    "butler_bot_agent/agents/local_memory/",
    "butler_bot_agent/agents/recent_memory/",
    "butler_main/butler_bot_agent/agents/local_memory/",
    "butler_main/butler_bot_agent/agents/recent_memory/",
    "butler_bot_agent/skills/",
    "butler_main/butler_bot_agent/skills/",
    "butler_bot_agent/agents/docs/",
    "butler_bot_agent/agents/sub-agents/",
)

MOJIBAKE_TOKENS = ("Ã", "Â", "â€", "ï¼", "ï½", "å", "æ", "ç", "ðŸ", "¤")


def _count_cjk(text: str) -> int:
    count = 0
    for char in text:
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF:
            count += 1
    return count


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _scan_text_file(path: Path, workspace: Path) -> dict | None:
    if not _is_text_file(path):
        return None
    legacy_counter: Counter[str] = Counter()
    suspicious_counter: Counter[str] = Counter()
    suspicious_preview = ""
    cjk_chars = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\n")
                for pattern in LEGACY_PATTERNS:
                    hits = line.count(pattern)
                    if hits:
                        legacy_counter[pattern] += hits
                for token in MOJIBAKE_TOKENS:
                    hits = line.count(token)
                    if hits:
                        suspicious_counter[token] += hits
                if not suspicious_preview and any(token in line for token in MOJIBAKE_TOKENS):
                    suspicious_preview = line[:180]
                cjk_chars += _count_cjk(line)
    except OSError:
        return None
    suspicious_total = sum(suspicious_counter.values())
    return {
        "path": path.relative_to(workspace).as_posix(),
        "legacy_hits": dict(legacy_counter),
        "legacy_total": sum(legacy_counter.values()),
        "suspicious_hits": dict(suspicious_counter),
        "suspicious_total": suspicious_total,
        "cjk_chars": cjk_chars,
        "suspicious_preview": suspicious_preview,
    }


def _collect_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _summarize_tree(root: Path, workspace: Path) -> dict:
    files = _collect_files(root)
    total_bytes = sum(path.stat().st_size for path in files)
    by_suffix: Counter[str] = Counter(path.suffix.lower() or "<noext>" for path in files)
    largest = sorted(files, key=lambda item: item.stat().st_size, reverse=True)[:10]
    return {
        "root": root.relative_to(workspace).as_posix(),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "suffix_counts": dict(by_suffix.most_common()),
        "largest_files": [
            {
                "path": path.relative_to(workspace).as_posix(),
                "bytes": path.stat().st_size,
            }
            for path in largest
        ],
    }


def _collect_legacy_and_encoding_issues(data_root: Path, workspace: Path) -> tuple[list[dict], list[dict]]:
    legacy_hits: list[dict] = []
    encoding_hits: list[dict] = []
    for path in _collect_files(data_root):
        scanned = _scan_text_file(path, workspace)
        if not scanned:
            continue
        if scanned["legacy_total"] > 0:
            legacy_hits.append(
                {
                    "path": scanned["path"],
                    "total_hits": scanned["legacy_total"],
                    "patterns": scanned["legacy_hits"],
                }
            )
        suspicious_total = scanned["suspicious_total"]
        cjk_chars = scanned["cjk_chars"]
        if suspicious_total >= 24 and suspicious_total > max(8, int(cjk_chars * 0.4)):
            encoding_hits.append(
                {
                    "path": scanned["path"],
                    "suspicious_total": suspicious_total,
                    "cjk_chars": cjk_chars,
                    "tokens": scanned["suspicious_hits"],
                    "preview": scanned["suspicious_preview"],
                }
            )
    legacy_hits.sort(key=lambda item: (-item["total_hits"], item["path"]))
    encoding_hits.sort(key=lambda item: (-item["suspicious_total"], item["path"]))
    return legacy_hits, encoding_hits


def _build_file_map(root: Path, exclude_prefixes: tuple[str, ...] = ()) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    if not root.exists():
        return mapping
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if any(relative.startswith(prefix) for prefix in exclude_prefixes):
            continue
        mapping[relative] = path
    return mapping


def _compare_dirs(left: Path, right: Path, workspace: Path, left_exclude_prefixes: tuple[str, ...] = ()) -> dict:
    left_map = _build_file_map(left, exclude_prefixes=left_exclude_prefixes)
    right_map = _build_file_map(right)
    shared = sorted(set(left_map) & set(right_map))
    identical: list[dict] = []
    different: list[dict] = []
    for relative in shared:
        left_path = left_map[relative]
        right_path = right_map[relative]
        same_size = left_path.stat().st_size == right_path.stat().st_size
        same_hash = same_size and _sha1(left_path) == _sha1(right_path)
        item = {
            "relative_path": relative,
            "left_path": left_path.relative_to(workspace).as_posix(),
            "right_path": right_path.relative_to(workspace).as_posix(),
            "bytes": left_path.stat().st_size,
        }
        if same_hash:
            identical.append(item)
        else:
            different.append(item)
    return {
        "left": left.relative_to(workspace).as_posix(),
        "right": right.relative_to(workspace).as_posix(),
        "shared_count": len(shared),
        "identical_count": len(identical),
        "different_count": len(different),
        "left_only_count": len(set(left_map) - set(right_map)),
        "right_only_count": len(set(right_map) - set(left_map)),
        "identical_examples": identical[:20],
        "different_examples": different[:20],
    }


def _run_cleanup_script(workspace: Path) -> dict:
    script_path = workspace / "tools" / "cleanup_chat_data_legacy_paths.ps1"
    if not script_path.exists():
        return {
            "ran": False,
            "ok": False,
            "script": script_path.as_posix(),
            "error": "cleanup script not found",
        }
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-WorkspaceRoot",
        str(workspace),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return {
        "ran": True,
        "ok": completed.returncode == 0,
        "script": script_path.as_posix(),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _write_report(report: dict, output_dir: Path) -> None:
    json_path = output_dir / "memory_curation_report.json"
    md_path = output_dir / "memory_curation_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report["summary"]
    lines = [
        "# Memory Curation Report",
        "",
        f"- workspace: `{report['workspace']}`",
        f"- data_root: `{report['data_root']}`",
        f"- total_files: `{summary['total_files']}`",
        f"- legacy_hit_files: `{summary['legacy_hit_files']}`",
        f"- encoding_suspect_files: `{summary['encoding_suspect_files']}`",
        f"- mirror_overlap_files: `{summary['mirror_overlap_files']}`",
        "",
        "## Hot / Cold Snapshot",
        "",
    ]
    for section in report["trees"]:
        lines.append(
            f"- `{section['root']}`: files={section['file_count']} bytes={section['total_bytes']}"
        )
    lines.extend(["", "## Largest Files", ""])
    for item in report["largest_files"][:15]:
        lines.append(f"- `{item['path']}` ({item['bytes']} bytes)")
    lines.append("")

    if report["legacy_path_hits"]:
        lines.extend(["## Legacy Path Residues", ""])
        for item in report["legacy_path_hits"][:20]:
            lines.append(f"- `{item['path']}` -> hits={item['total_hits']}")
        lines.append("")

    if report["encoding_suspects"]:
        lines.extend(["## Encoding Suspects", ""])
        for item in report["encoding_suspects"][:20]:
            preview = item["preview"].replace("`", "'")
            lines.append(
                f"- `{item['path']}` -> suspicious={item['suspicious_total']} cjk={item['cjk_chars']} preview=`{preview[:120]}`"
            )
        lines.append("")

    lines.extend(["## Mirror Checks", ""])
    for check in report["mirror_checks"]:
        lines.append(
            f"- `{check['left']}` vs `{check['right']}` -> shared={check['shared_count']} identical={check['identical_count']} different={check['different_count']}"
        )
    lines.extend(
        [
            "",
            "## Suggestions",
            "",
            "1. 先处理 `encoding_suspects`，因为乱码会污染后续整理与检索。",
            "2. 对 `legacy_path_hits` 先跑 report，再决定是否执行路径批量重写。",
            "3. 对 `mirror_checks` 里长期 identical 的镜像，明确单一真源与保留理由。",
            "4. 对最大日志文件优先判断是否应归档、截断或移出热路径。",
            "",
        ]
    )

    cleanup = report.get("cleanup")
    if cleanup:
        lines.extend(["## Cleanup Run", ""])
        if cleanup.get("ran"):
            lines.append(f"- ok={cleanup.get('ok')} returncode={cleanup.get('returncode')}")
            if cleanup.get("stdout"):
                lines.append(f"- stdout: `{cleanup['stdout'][:300]}`")
            if cleanup.get("stderr"):
                lines.append(f"- stderr: `{cleanup['stderr'][:300]}`")
            if "remaining_legacy_hit_files" in cleanup:
                lines.append(f"- remaining_legacy_hit_files: `{cleanup['remaining_legacy_hit_files']}`")
        else:
            lines.append(f"- cleanup skipped: `{cleanup.get('error', 'not requested')}`")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and curate Butler chat memory assets.")
    parser.add_argument("--workspace", default=".", help="Butler workspace root")
    parser.add_argument(
        "--chat-data-root",
        default="butler_main/chat/data",
        help="Chat data root, relative to workspace",
    )
    parser.add_argument(
        "--output-dir",
        default="工作区/memory-curation",
        help="Output directory, relative to workspace",
    )
    parser.add_argument(
        "--rewrite-legacy-paths",
        action="store_true",
        help="Run the legacy path cleanup script after generating the audit report",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    data_root = (workspace / args.chat_data_root).resolve()
    output_dir = (workspace / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not data_root.exists():
        raise SystemExit(f"chat data root not found: {data_root}")

    hot_root = data_root / "hot"
    cold_root = data_root / "cold"

    trees = [
        _summarize_tree(hot_root, workspace),
        _summarize_tree(cold_root, workspace),
    ]
    all_largest = sorted(
        [item for tree in trees for item in tree["largest_files"]],
        key=lambda item: item["bytes"],
        reverse=True,
    )
    legacy_hits, encoding_hits = _collect_legacy_and_encoding_issues(data_root, workspace)
    mirror_checks = [
        _compare_dirs(hot_root, hot_root / "recent_memory", workspace, left_exclude_prefixes=("recent_memory/",)),
    ]

    report = {
        "workspace": workspace.as_posix(),
        "data_root": data_root.relative_to(workspace).as_posix(),
        "summary": {
            "total_files": sum(tree["file_count"] for tree in trees),
            "legacy_hit_files": len(legacy_hits),
            "encoding_suspect_files": len(encoding_hits),
            "mirror_overlap_files": sum(check["shared_count"] for check in mirror_checks),
        },
        "trees": trees,
        "largest_files": all_largest[:15],
        "legacy_path_hits": legacy_hits,
        "encoding_suspects": encoding_hits,
        "mirror_checks": mirror_checks,
    }

    if args.rewrite_legacy_paths:
        cleanup = _run_cleanup_script(workspace)
        post_legacy_hits, _ = _collect_legacy_and_encoding_issues(data_root, workspace)
        cleanup["remaining_legacy_hit_files"] = len(post_legacy_hits)
        report["cleanup"] = cleanup

    _write_report(report, output_dir)
    print(
        json.dumps(
            {
                "output_dir": output_dir.as_posix(),
                "legacy_hit_files": report["summary"]["legacy_hit_files"],
                "encoding_suspect_files": report["summary"]["encoding_suspect_files"],
                "mirror_overlap_files": report["summary"]["mirror_overlap_files"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
