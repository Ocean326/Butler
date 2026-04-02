from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IDEAS_DIR = ROOT / "Ideas"
INSIGHTS_DIR = ROOT / "Insights"
CONFIG_PATH = INSIGHTS_DIR / "knowledge_tree_config.json"
README_PATH = INSIGHTS_DIR / "README.md"
INDEX_PATH = INSIGHTS_DIR / "index.md"
TREE_JSON_PATH = INSIGHTS_DIR / "knowledge_tree.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def markdown_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem


def markdown_summary(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    candidates: list[str] = []
    for line in lines[1:80]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            candidates.append(stripped.lstrip("> ").strip())
        elif not stripped.startswith(("#", "-", "*", "|", "```")):
            candidates.append(stripped)
        if candidates:
            break
    if not candidates:
        return ""
    summary = re.sub(r"\s+", " ", candidates[0])
    return summary[:120] + ("…" if len(summary) > 120 else "")


def relative(path: Path) -> str:
    return path.relative_to(INSIGHTS_DIR).as_posix()


def doc_meta(path: Path, summary_override: str | None = None) -> dict:
    rel = relative(path)
    summary = summary_override or markdown_summary(path)
    return {
        "path": rel,
        "title": markdown_title(path),
        "summary": summary,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        "sort_key": path.stat().st_mtime,
    }


def count_raw_assets() -> dict:
    raw_dir = ROOT / "Raw"
    files = [path for path in raw_dir.rglob("*") if path.is_file()]
    md_count = sum(1 for path in files if path.suffix.lower() == ".md")
    json_count = sum(1 for path in files if path.suffix.lower() == ".json")
    image_count = sum(1 for path in files if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    return {
        "all_files": len(files),
        "md_files": md_count,
        "json_files": json_count,
        "image_files": image_count,
    }


def count_ideas_assets() -> dict:
    if not IDEAS_DIR.exists():
        return {
            "all_files": 0,
            "note_files": 0,
            "inbox_files": 0,
            "thread_files": 0,
        }
    files = [path for path in IDEAS_DIR.rglob("*") if path.is_file()]
    note_files = [
        path
        for path in files
        if path.suffix.lower() == ".md" and path.name != "README.md" and "templates" not in path.parts
    ]
    return {
        "all_files": len(files),
        "note_files": len(note_files),
        "inbox_files": sum(1 for path in note_files if "inbox" in path.parts),
        "thread_files": sum(1 for path in note_files if "threads" in path.parts),
    }


def count_working_assets() -> dict:
    working_dir = ROOT / "Working"
    files = [path for path in working_dir.rglob("*") if path.is_file()]
    return {
        "all_files": len(files),
        "md_files": sum(1 for path in files if path.suffix.lower() == ".md"),
    }


def score_branch(filename: str, keywords: list[str]) -> int:
    lowered = filename.lower().replace("-", "_")
    score = 0
    for keyword in keywords:
        if keyword.lower() in lowered:
            score += 1
    return score


def assign_branch(doc_path: str, config: dict) -> str:
    scores = []
    for branch_id in config["branch_order"]:
        keywords = config["branches"][branch_id].get("archive_keywords", [])
        scores.append((score_branch(doc_path, keywords), branch_id))
    scores.sort(reverse=True)
    if scores and scores[0][0] > 0:
        return scores[0][1]
    return "uncategorized"


def build_tree(config: dict) -> dict:
    mainline_docs: dict[str, dict] = {}
    for path in sorted((INSIGHTS_DIR / "mainline").glob("*.md")):
        rel = relative(path)
        summary_override = config.get("mainline_summaries", {}).get(rel)
        mainline_docs[rel] = doc_meta(path, summary_override=summary_override)

    standalone_docs: list[dict] = []
    for path in sorted((INSIGHTS_DIR / "standalone_archive").rglob("*.md")):
        if path.name in {"index.md", "README.md"}:
            continue
        standalone_docs.append(doc_meta(path))

    branches: dict[str, dict] = {}
    for branch_id in config["branch_order"]:
        branch_conf = config["branches"][branch_id]
        branches[branch_id] = {
            "title": branch_conf["title"],
            "question": branch_conf["question"],
            "mainline_docs": [mainline_docs[path] for path in branch_conf["mainline"] if path in mainline_docs],
            "archive_docs": [],
        }

    uncategorized: list[dict] = []
    for doc in standalone_docs:
        branch_id = assign_branch(doc["path"], config)
        if branch_id == "uncategorized":
            uncategorized.append(doc)
        else:
            branches[branch_id]["archive_docs"].append(doc)

    for branch in branches.values():
        branch["archive_docs"].sort(key=lambda item: item["sort_key"], reverse=True)
        for doc in branch["mainline_docs"] + branch["archive_docs"]:
            doc.pop("sort_key", None)

    for doc in uncategorized:
        doc.pop("sort_key", None)

    crossline_docs = []
    for item in config.get("crossline_docs", []):
        path = INSIGHTS_DIR / item["path"]
        if path.exists():
            crossline_docs.append(
                {
                    "path": item["path"],
                    "title": item["title"],
                    "summary": item["summary"],
                    "updated_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )

    ideas_stats = count_ideas_assets()
    raw_stats = count_raw_assets()
    working_stats = count_working_assets()
    all_times = [
        path.stat().st_mtime
        for path in list((INSIGHTS_DIR / "mainline").glob("*.md")) + list((INSIGHTS_DIR / "standalone_archive").rglob("*.md"))
        if path.name not in {"index.md", "README.md"}
    ]
    latest = datetime.fromtimestamp(max(all_times)).strftime("%Y-%m-%d %H:%M") if all_times else ""
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "latest_source_update": latest,
        "stats": {
            "ideas": ideas_stats,
            "raw": raw_stats,
            "working": working_stats,
            "mainline_docs": sum(len(branches[branch_id]["mainline_docs"]) for branch_id in config["branch_order"]),
            "crossline_docs": len(crossline_docs),
            "standalone_docs": len(standalone_docs),
            "branches": len(config["branch_order"]),
            "uncategorized_docs": len(uncategorized),
        },
        "branches": branches,
        "crossline_docs": crossline_docs,
        "uncategorized_docs": uncategorized,
        "reading_paths": config.get("reading_paths", []),
    }


def format_doc_bullet(doc: dict) -> str:
    summary = f" — {doc['summary']}" if doc.get("summary") else ""
    return f"- `{doc['path']}`：{doc['title']}{summary}"


def render_readme(tree: dict, config: dict) -> str:
    lines: list[str] = []
    stats = tree["stats"]
    lines.append("# BrainStorm Insights 知识目录")
    lines.append("")
    lines.append(f"> 自动生成：{tree['generated_at']}  |  最近源文档更新时间：{tree['latest_source_update']}")
    lines.append("> 刷新命令：`python BrainStorm/tools/refresh_brainstorm.py`")
    lines.append("")
    lines.append("## 这个目录解决什么问题")
    lines.append("")
    lines.append("- 把 `Insights/mainline/` 当作知识树主干，把 `standalone_archive/` 自动挂到对应分支。")
    lines.append("- 明确 `Ideas/` 只是脑暴入口池，不直接进入知识树。")
    lines.append("- 把「新增素材 → 挂靠分支 → 回看主线 → 再合并总结」变成固定阅读入口。")
    lines.append("- 让你以后默认从这里读，而不是在 `Insights/` 里凭文件名硬找。")
    lines.append("")
    lines.append("## 当前快照")
    lines.append("")
    lines.append(f"- `Ideas/`：{stats['ideas']['note_files']} 篇想法笔记（`inbox` {stats['ideas']['inbox_files']} / `threads` {stats['ideas']['thread_files']}，不纳入知识树）。")
    lines.append(f"- `Raw/`：{stats['raw']['md_files']} 篇 Markdown + {stats['raw']['json_files']} 个 JSON + {stats['raw']['image_files']} 个图片/OCR 资产。")
    lines.append(f"- `Working/`：{stats['working']['md_files']} 篇工作稿。")
    lines.append(f"- `Insights/`：{stats['mainline_docs']} 篇主线文档 + {stats['crossline_docs']} 篇跨主线总图 + {stats['standalone_docs']} 篇归档洞察，归入 {stats['branches']} 个知识分支。")
    if stats["uncategorized_docs"]:
        lines.append(f"- `待归类`：{stats['uncategorized_docs']} 篇，建议人工看一眼命名或补关键词。")
    lines.append("")
    lines.append("## 阅读方式")
    lines.append("")
    lines.append("- 有新想法但还没证据：先记到 `Ideas/`，不要直接塞进主线。")
    lines.append("- 想建立全局框架：先看下面的「知识树」，每个分支先读主干，再抽查最近归档洞察。")
    lines.append("- 想直接落地 Butler：优先看「Butler 落地路径」。")
    lines.append("- 想处理新增素材：先确认它应挂到哪一条主线，再决定是否需要升级主线文档。")
    lines.append("")
    lines.append("## 知识树")
    lines.append("")
    for index, branch_id in enumerate(config["branch_order"], start=1):
        branch = tree["branches"][branch_id]
        lines.append(f"### {index}. {branch['title']}")
        lines.append("")
        lines.append(f"- 核心问题：{branch['question']}")
        lines.append(f"- 主干文档：{len(branch['mainline_docs'])} 篇")
        lines.append(f"- 归档洞察：{len(branch['archive_docs'])} 篇")
        lines.append("- 主干：")
        for doc in branch["mainline_docs"]:
            lines.append(format_doc_bullet(doc))
        if branch["archive_docs"]:
            lines.append("- 最近归档：")
            for doc in branch["archive_docs"][:5]:
                lines.append(format_doc_bullet(doc))
            if len(branch["archive_docs"]) > 5:
                lines.append(f"- 其余 {len(branch['archive_docs']) - 5} 篇：已同样归档在该分支下，可按文件名继续回溯。")
        lines.append("")
    if tree["crossline_docs"]:
        lines.append("## 跨主线总图")
        lines.append("")
        for doc in tree["crossline_docs"]:
            lines.append(format_doc_bullet(doc))
        lines.append("")
    if tree["reading_paths"]:
        lines.append("## 推荐阅读路径")
        lines.append("")
        for path_conf in tree["reading_paths"]:
            lines.append(f"### {path_conf['title']}")
            lines.append("")
            lines.append(f"- 适用场景：{path_conf['description']}")
            lines.append("- 顺序：")
            for doc_path in path_conf["docs"]:
                title = markdown_title(INSIGHTS_DIR / doc_path)
                lines.append(f"- `{doc_path}`：{title}")
            lines.append("")
    if tree["uncategorized_docs"]:
        lines.append("## 待归类")
        lines.append("")
        for doc in tree["uncategorized_docs"]:
            lines.append(format_doc_bullet(doc))
        lines.append("")
    lines.append("## 维护协议")
    lines.append("")
    lines.append("- 新增或合并 `Insights/` 文档后，执行一次 `python BrainStorm/tools/refresh_brainstorm.py`。")
    lines.append("- 若新主题无法自动挂到分支，先补 `knowledge_tree_config.json` 的关键词，再刷新。")
    lines.append("- `standalone Insight` 继续作为中间沉淀层；当同主题累计到可稳定抽象时，再把结论合并进主线。")
    lines.append("- `Insights/README.md` 是默认知识入口，`Insights/index.md` 保持为兼容索引，不再手工维护。")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_index(tree: dict, config: dict) -> str:
    lines = [
        "# BrainStorm Insights 索引",
        "",
        f"> 自动生成：{tree['generated_at']}",
        "",
        "- 默认阅读入口：`Insights/README.md`",
        f"- 主线文档：{tree['stats']['mainline_docs']} 篇",
        f"- 跨主线总图：{tree['stats']['crossline_docs']} 篇",
        f"- 归档洞察：{tree['stats']['standalone_docs']} 篇",
        "",
        "## 分支概览",
        "",
        "| 分支 | 主干 | 归档洞察 |",
        "|---|---:|---:|",
    ]
    for branch_id in config["branch_order"]:
        branch = tree["branches"][branch_id]
        lines.append(f"| {branch['title']} | {len(branch['mainline_docs'])} | {len(branch['archive_docs'])} |")
    lines.extend(
        [
            "",
            "## 跨主线总图",
            "",
            "- `mainline/Butler_跨主线落地路线图_2026Q1.md`：统一承接主线里的工程落地事项。",
            "",
            "## 维护协议",
            "",
            "- 刷新命令：`python BrainStorm/tools/refresh_brainstorm.py`",
            "- 详细知识树与阅读路径见 `Insights/README.md`。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    config = load_config()
    tree = build_tree(config)
    TREE_JSON_PATH.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    README_PATH.write_text(render_readme(tree, config), encoding="utf-8")
    INDEX_PATH.write_text(render_index(tree, config), encoding="utf-8")


if __name__ == "__main__":
    main()
