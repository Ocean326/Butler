from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
for parent in [CURRENT_FILE, *CURRENT_FILE.parents]:
    if (parent / "butler_main").exists():
        import sys

        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from butler_main.sources.skills.shared.workspace_layout import find_workspace_root, resolve_output_dir, skill_temp_dir


ROLE_TEXT = "feishu-workstation-agent, butler-continuation-agent, orchestrator-agent"

PROMOTION_MAP = {
    "trafilatura-web-extract": {
        "skill_name": "web-article-extract",
        "domain": "general",
        "description": "抓取普通网页正文并生成结构化摘录，优先用于博客、公告页、论坛正文页和研究页的轻量提取。",
        "trigger_examples": "网页正文提取, 抓一篇文章, 网页清洗, 博客页面抓取",
        "risk_level": "medium",
        "automation_safe": "true",
        "usage_args": "--url 'https://example.com/post' --output-dir '工作区/Butler/runtime/skills/web-article-extract'",
    },
    "feedparser-rss-ingest": {
        "skill_name": "rss-feed-watch",
        "domain": "general",
        "description": "拉取 RSS / Atom feed，输出最近条目摘要，适合做订阅监控、更新跟踪和摘要生成。",
        "trigger_examples": "订阅RSS, 监控feed, 抓博客更新, 拉取Atom",
        "risk_level": "low",
        "automation_safe": "true",
        "usage_args": "--feed 'https://example.com/feed.xml' --limit 5 --output-dir '工作区/Butler/runtime/skills/rss-feed-watch'",
    },
    "praw-reddit-ingest": {
        "skill_name": "reddit-thread-read",
        "domain": "forum",
        "description": "读取 Reddit 主题帖或 subreddit 列表，输出标题、分数、评论摘要，适合做社区舆情和帖子梳理。",
        "trigger_examples": "看Reddit热帖, 抓reddit评论, subreddit监控, reddit thread",
        "risk_level": "medium",
        "automation_safe": "false",
        "usage_args": "--subreddit 'LocalLLaMA' --sort hot --limit 5 --output-dir '工作区/Butler/runtime/skills/reddit-thread-read'",
    },
    "hackernews-api-ingest": {
        "skill_name": "hackernews-thread-watch",
        "domain": "forum",
        "description": "读取 Hacker News 热门或指定线程，输出标题、分数、评论摘要，适合开发工具和 AI 讨论跟踪。",
        "trigger_examples": "看HN热帖, Hacker News监控, HN评论抓取, yc新闻",
        "risk_level": "low",
        "automation_safe": "true",
        "usage_args": "--mode topstories --limit 10 --output-dir '工作区/Butler/runtime/skills/hackernews-thread-watch'",
    },
    "stackexchange-api-ingest": {
        "skill_name": "stackexchange-search",
        "domain": "forum",
        "description": "搜索 Stack Exchange / Stack Overflow 问答，输出问题标题、答案数和链接，适合技术问题对照检索。",
        "trigger_examples": "搜stackoverflow, 查技术问答, stackexchange检索, accepted answer",
        "risk_level": "low",
        "automation_safe": "true",
        "usage_args": "--query 'useEffectEvent React' --site stackoverflow --limit 5 --output-dir '工作区/Butler/runtime/skills/stackexchange-search'",
    },
    "discourse-api-monitor": {
        "skill_name": "discourse-topic-read",
        "domain": "forum",
        "description": "读取 Discourse 最新话题或指定 topic，用于社区论坛公告、支持贴和讨论串整理。",
        "trigger_examples": "读discourse论坛, 社区公告抓取, discourse topic, 官方论坛整理",
        "risk_level": "medium",
        "automation_safe": "false",
        "usage_args": "--base-url 'https://meta.discourse.org' --limit 5 --output-dir '工作区/Butler/runtime/skills/discourse-topic-read'",
    },
    "github-discussions-graphql": {
        "skill_name": "github-discussions-read",
        "domain": "forum",
        "description": "读取 GitHub Discussions 列表或单条讨论，适合开源社区支持区、路线图讨论和 FAQ 整理。",
        "trigger_examples": "读GitHub Discussions, repo社区讨论, maintainer faq, discussion线程",
        "risk_level": "medium",
        "automation_safe": "false",
        "usage_args": "--owner 'openai' --repo 'openai-python' --limit 5 --github-token-env GITHUB_TOKEN --output-dir '工作区/Butler/runtime/skills/github-discussions-read'",
    },
    "arxiv-py-paper-retrieval": {
        "skill_name": "arxiv-search",
        "domain": "research",
        "description": "搜索 arXiv 论文并输出标题、作者、摘要和链接，适合研究主题跟踪和论文初筛。",
        "trigger_examples": "查arxiv, 搜论文, arxiv主题跟踪, 研究论文检索",
        "risk_level": "low",
        "automation_safe": "true",
        "usage_args": "--query 'reasoning models' --limit 5 --output-dir '工作区/Butler/runtime/skills/arxiv-search'",
    },
    "semantic-scholar-api": {
        "skill_name": "semantic-scholar-search",
        "domain": "research",
        "description": "搜索 Semantic Scholar 文献或指定 paper id，输出摘要、引用数和链接，适合 citation 扩展。",
        "trigger_examples": "查Semantic Scholar, citation扩展, related papers, 论文引用图",
        "risk_level": "medium",
        "automation_safe": "false",
        "usage_args": "--query 'chain of thought prompting' --limit 5 --output-dir '工作区/Butler/runtime/skills/semantic-scholar-search'",
    },
    "openalex-pyalex": {
        "skill_name": "openalex-search",
        "domain": "research",
        "description": "搜索 OpenAlex works / authors 等实体，适合研究图谱、机构作者和主题全景检索。",
        "trigger_examples": "查OpenAlex, 研究图谱, 作者机构检索, 学术全景",
        "risk_level": "medium",
        "automation_safe": "false",
        "usage_args": "--query 'large language model agents' --entity-type works --limit 5 --output-dir '工作区/Butler/runtime/skills/openalex-search'",
    },
    "crossref-rest-metadata": {
        "skill_name": "crossref-doi-enrich",
        "domain": "research",
        "description": "按 DOI 或 bibliographic query 获取 Crossref 元数据，适合 DOI 补全和参考文献规范化。",
        "trigger_examples": "补DOI信息, Crossref元数据, reference normalize, 论文元数据补全",
        "risk_level": "low",
        "automation_safe": "true",
        "usage_args": "--query 'attention is all you need' --limit 5 --output-dir '工作区/Butler/runtime/skills/crossref-doi-enrich'",
    },
    "europepmc-rest-biomed": {
        "skill_name": "europepmc-search",
        "domain": "research",
        "description": "搜索 Europe PMC 文献，适合生物医药和生命科学文献检索。",
        "trigger_examples": "查Europe PMC, 生物医药论文, biomedical paper search, pubmed替代",
        "risk_level": "low",
        "automation_safe": "true",
        "usage_args": "--query 'single cell transformer' --limit 5 --output-dir '工作区/Butler/runtime/skills/europepmc-search'",
    },
}


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid json object: {path}")
    return payload


def _wrapper_script(candidate_id: str) -> str:
    return f"""from __future__ import annotations

import sys
from pathlib import Path


def _workspace_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "butler_main").exists():
            return parent
    raise SystemExit("workspace root not found")


ROOT = _workspace_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from butler_main.sources.skills.shared.upstream_source_runtime import main


if __name__ == "__main__":
    raise SystemExit(main(source_id="{candidate_id}"))
"""


def _skill_markdown(candidate: dict, candidate_id: str, config: dict[str, str]) -> str:
    return f"""---
name: {config['skill_name']}
description: {config['description']}
category: {config['domain']}
trigger_examples: {config['trigger_examples']}
allowed_roles: {ROLE_TEXT}
risk_level: {config['risk_level']}
automation_safe: {config['automation_safe']}
requires_skill_read: true
status: active
source_candidate_id: {candidate_id}
upstream_name: {candidate.get('name', '')}
upstream_repo_or_entry: {candidate.get('repo_url', '')}
---

# {config['skill_name']}

这个 skill 是由 incubating 候选 `{candidate_id}` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: {candidate.get('name', '')}
- repo or entry: {candidate.get('repo_url', '')}
- docs: {candidate.get('docs_url', '')}
- original candidate path: ./butler_main/sources/skills/pool/incubating/{config['domain']}/{candidate_id}

## 运行方式

```powershell
& '.venv\\Scripts\\python.exe' `
  'butler_main/sources/skills/pool/{config['domain']}/{config['skill_name']}/scripts/run.py' `
  {config['usage_args']}
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill
"""


def _reference_markdown(candidate: dict, candidate_id: str, config: dict[str, str]) -> str:
    lines = [
        f"# Upstream Reference: {candidate.get('name', candidate_id)}",
        "",
        f"- candidate_id: `{candidate_id}`",
        f"- active_skill: `{config['skill_name']}`",
        f"- repo_or_entry: {candidate.get('repo_url', '')}",
        f"- docs: {candidate.get('docs_url', '')}",
        "",
        "## Why This Skill Exists",
        "",
    ]
    for item in candidate.get("why_recommended") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Risks", ""])
    for item in candidate.get("risks") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Promotion Note", "", "- 该 skill 由 `skill-incubating-promote` 生成并纳入 active skill 池。"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote incubating upstream candidates into active executable Butler skills.")
    parser.add_argument("--workspace", default=".", help="Workspace root")
    parser.add_argument("--candidates-file", default="butler_main/sources/skills/agent/skill_manager_agent/references/external_skill_candidates_2026-03-24.json", help="Candidate JSON file")
    parser.add_argument("--ids", default="", help="Comma-separated candidate ids to promote")
    parser.add_argument("--all-supported", action="store_true", help="Promote all supported candidates")
    parser.add_argument("--replace", action="store_true", help="Replace existing active skill directories")
    parser.add_argument("--output-dir", default="", help="Output directory; defaults to butler_main/sources/skills/temp/promote")
    args = parser.parse_args()

    workspace = find_workspace_root(Path(args.workspace).resolve())
    candidates_path = (workspace / args.candidates_file).resolve()
    output_dir = resolve_output_dir(workspace, args.output_dir, default_path=skill_temp_dir(workspace, "promote"))
    payload = _load_json(candidates_path)
    candidates = {str(item.get("id") or "").strip(): item for item in payload.get("candidates") or [] if isinstance(item, dict)}
    requested = {item.strip() for item in str(args.ids or "").split(",") if item.strip()}
    if args.all_supported:
        requested = set(PROMOTION_MAP)
    if not requested:
        raise SystemExit("no candidate ids requested")

    promoted: list[dict] = []
    registry_entries: dict[str, dict] = {}
    for candidate_id in sorted(requested):
        config = PROMOTION_MAP.get(candidate_id)
        candidate = candidates.get(candidate_id)
        if config is None or candidate is None:
            promoted.append({"candidate_id": candidate_id, "status": "unsupported_or_missing"})
            continue
        target_dir = workspace / "butler_main" / "sources" / "skills" / "pool" / config["domain"] / config["skill_name"]
        if target_dir.exists() and args.replace:
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir = target_dir / "scripts"
        refs_dir = target_dir / "references"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        refs_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(_skill_markdown(candidate, candidate_id, config), encoding="utf-8")
        (refs_dir / "upstream.md").write_text(_reference_markdown(candidate, candidate_id, config), encoding="utf-8")
        (scripts_dir / "run.py").write_text(_wrapper_script(candidate_id), encoding="utf-8")
        conversion_json = {
            "candidate_id": candidate_id,
            "active_skill_name": config["skill_name"],
            "active_skill_path": "./" + str(target_dir.relative_to(workspace)).replace("\\", "/"),
            "promoted_at": "2026-03-24",
            "promotion_mode": "auto_template",
            "upstream_name": candidate.get("name"),
        }
        (target_dir / "CONVERSION.json").write_text(json.dumps(conversion_json, ensure_ascii=False, indent=2), encoding="utf-8")
        promoted.append({"candidate_id": candidate_id, "status": "promoted", **conversion_json})
        registry_entries[candidate_id] = {"status": "active", "active_skill_name": config["skill_name"], "active_skill_path": conversion_json["active_skill_path"], "auto_promotable": True}

    for candidate_id, config in PROMOTION_MAP.items():
        registry_entries.setdefault(
            candidate_id,
            {
                "status": "defined_not_promoted",
                "active_skill_name": config["skill_name"],
                "active_skill_path": f"./butler_main/sources/skills/pool/{config['domain']}/{config['skill_name']}",
                "auto_promotable": True,
            },
        )
    for candidate_id, candidate in candidates.items():
        registry_entries.setdefault(
            candidate_id,
            {
                "status": "incubating_manual",
                "active_skill_name": "",
                "active_skill_path": "",
                "auto_promotable": False,
                "reason": f"no auto-promotion template for upstream '{candidate.get('name', candidate_id)}'",
            },
        )
    registry_path = workspace / "butler_main" / "sources" / "skills" / "agent" / "skill_manager_agent" / "references" / "upstream_skill_conversion_registry.json"
    registry_payload = {"generated_at": "2026-03-24", "entries": registry_entries}
    registry_path.write_text(json.dumps(registry_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {"requested_count": len(requested), "promoted": promoted, "registry_path": "./" + str(registry_path.relative_to(workspace)).replace("\\", "/")}
    (output_dir / "skill_promotion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Skill Promotion Report", "", f"- requested_count: `{len(requested)}`", f"- registry_path: `{report['registry_path']}`", "", "## Items", ""]
    for item in promoted:
        lines.append(f"- `{item['candidate_id']}` | `{item['status']}`")
    lines.append("")
    (output_dir / "skill_promotion_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

