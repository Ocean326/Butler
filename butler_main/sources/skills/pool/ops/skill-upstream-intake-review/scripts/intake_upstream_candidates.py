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


STATUS = "incubating"
ROLE_TEXT = "feishu-workstation-agent, butler-continuation-agent, orchestrator-agent"


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid json object: {path}")
    return payload


def _slug_domain(category: str) -> str:
    normalized = str(category or "").strip().lower()
    if normalized.startswith("forum"):
        return "forum"
    if normalized.startswith("research"):
        return "research"
    return "general"


def _normalize_text_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    result: list[str] = []
    for raw in values or []:
        text = str(raw or "").strip()
        if text:
            result.append(text)
    return result


def _frontmatter(candidate: dict) -> str:
    trigger_examples = {
        "general_information": "抓网页正文, 做RSS监控, 资料整理",
        "forum_information": "看论坛热帖, 拉评论树, 社区舆情",
        "research_information": "查论文, 扩citation, 跟踪研究主题",
    }.get(str(candidate.get("category") or "").strip(), "导入候选 skill, 生成草案, 审阅上游")
    lines = [
        "---",
        f"name: {candidate['id']}",
        f"description: Incubating Butler wrapper spec for upstream '{candidate['name']}'.",
        f"category: {_slug_domain(str(candidate.get('category') or 'general_information'))}",
        f"trigger_examples: {trigger_examples}",
        f"allowed_roles: {ROLE_TEXT}",
        "risk_level: medium",
        "automation_safe: false",
        "requires_skill_read: true",
        f"status: {STATUS}",
        f"upstream_name: {candidate['name']}",
        f"upstream_type: {str(candidate.get('upstream_type') or '').strip()}",
        f"review_priority: {str(candidate.get('priority') or '').strip()}",
        "---",
        "",
    ]
    return "\n".join(lines)


def _skill_markdown(candidate: dict) -> str:
    why = _normalize_text_list(candidate.get("why_recommended"))
    risks = _normalize_text_list(candidate.get("risks"))
    collections = _normalize_text_list(candidate.get("suggested_collection_ids"))
    lines = [
        _frontmatter(candidate).rstrip(),
        f"# {candidate['name']}",
        "",
        "## Status",
        "",
        "- `incubating`",
        "- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。",
        "- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。",
        "",
        "## Proposed Butler Shape",
        "",
        f"- {str(candidate.get('butler_skill_shape') or '').strip()}",
        "",
        "## Upstream",
        "",
        f"- repo_or_entry: {str(candidate.get('repo_url') or '').strip()}",
        f"- docs: {str(candidate.get('docs_url') or '').strip()}",
        f"- upstream_type: {str(candidate.get('upstream_type') or '').strip()}",
        f"- maturity: {str(candidate.get('maturity') or '').strip()}",
        "",
        "## Why This Matters",
        "",
    ]
    for item in why:
        lines.append(f"- {item}")
    if not why:
        lines.append("- 值得做进一步审阅。")
    lines.extend(["", "## Risks", ""])
    for item in risks:
        lines.append(f"- {item}")
    if not risks:
        lines.append("- 风险待补充。")
    lines.extend(["", "## Suggested Future Exposure", ""])
    for item in collections:
        lines.append(f"- {item}")
    if not collections:
        lines.append("- 暂不建议暴露。")
    lines.extend(
        [
            "",
            "## Implementation Checklist",
            "",
            "- 明确 Butler 输入输出 contract，不直接复刻上游 API。",
            "- 确认认证、限流、缓存和错误恢复策略。",
            "- 补执行脚本或 tool bridge，而不是只停留在说明文档。",
            "- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。",
            "- 审阅后再决定是否加入 collection registry。",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _review_markdown(candidate: dict, relative_dir: str) -> str:
    priority = str(candidate.get("priority") or "").strip() or "P1"
    verdict = "推荐进入第一批实现" if priority == "P0" else "保留在第二批或专题实现"
    lines = [
        f"# Review: {candidate['name']}",
        "",
        f"- candidate_id: `{candidate['id']}`",
        f"- imported_path: `{relative_dir}`",
        f"- priority: `{priority}`",
        f"- verdict: `{verdict}`",
        f"- upstream_type: `{str(candidate.get('upstream_type') or '').strip()}`",
        "",
        "## Review Summary",
        "",
        f"- proposed_butler_shape: {str(candidate.get('butler_skill_shape') or '').strip()}",
        f"- repo_or_entry: {str(candidate.get('repo_url') or '').strip()}",
        f"- docs: {str(candidate.get('docs_url') or '').strip()}",
        "",
        "## Why Recommended",
        "",
    ]
    for item in _normalize_text_list(candidate.get("why_recommended")):
        lines.append(f"- {item}")
    lines.extend(["", "## Risks", ""])
    for item in _normalize_text_list(candidate.get("risks")):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Next Action",
            "",
            "- 当前已作为 incubating skill 落库，但尚未实现执行脚本。",
            "- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import external upstream candidates into Butler incubating skill pool and generate review reports.")
    parser.add_argument("--workspace", default=".", help="Butler workspace root")
    parser.add_argument(
        "--candidates-file",
        default="butler_main/sources/skills/agent/skill_manager_agent/references/external_skill_candidates_2026-03-24.json",
        help="Candidate JSON file",
    )
    parser.add_argument("--dest-root", default="butler_main/sources/skills/pool/incubating", help="Incubating skill root")
    parser.add_argument("--output-dir", default="", help="Output directory; defaults to butler_main/sources/skills/temp/upstream-review")
    parser.add_argument("--ids", default="", help="Comma-separated candidate ids to intake")
    parser.add_argument("--replace", action="store_true", help="Replace existing incubating directories")
    args = parser.parse_args()

    workspace = find_workspace_root(Path(args.workspace).resolve())
    candidates_path = (workspace / args.candidates_file).resolve()
    dest_root = (workspace / args.dest_root).resolve()
    output_dir = resolve_output_dir(workspace, args.output_dir, default_path=skill_temp_dir(workspace, "upstream-review"))

    payload = _read_json(candidates_path)
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise SystemExit(f"invalid candidates list: {candidates_path}")
    requested_ids = {item.strip() for item in str(args.ids or "").split(",") if item.strip()}
    selected = [
        item
        for item in candidates
        if isinstance(item, dict) and str(item.get("id") or "").strip() and (not requested_ids or str(item.get("id") or "").strip() in requested_ids)
    ]
    if not selected:
        raise SystemExit("no candidate matched the request")

    imported: list[dict] = []
    for candidate in selected:
        domain = _slug_domain(str(candidate.get("category") or ""))
        target_dir = dest_root / domain / str(candidate["id"]).strip()
        if target_dir.exists():
            if not args.replace:
                imported.append(
                    {
                        "id": candidate["id"],
                        "name": candidate["name"],
                        "path": "./" + str(target_dir.relative_to(workspace)).replace("\\", "/"),
                        "status": "skipped_existing",
                    }
                )
                continue
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        relative_dir = "./" + str(target_dir.relative_to(workspace)).replace("\\", "/")
        (target_dir / "SKILL.md").write_text(_skill_markdown(candidate), encoding="utf-8")
        (target_dir / "UPSTREAM_REVIEW.md").write_text(_review_markdown(candidate, relative_dir), encoding="utf-8")
        intake_payload = {
            "candidate": candidate,
            "imported_at": "2026-03-24",
            "status": STATUS,
            "relative_dir": relative_dir,
            "review_state": "imported_for_review",
        }
        (target_dir / "UPSTREAM_INTAKE.json").write_text(
            json.dumps(intake_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        imported.append(
            {
                "id": candidate["id"],
                "name": candidate["name"],
                "path": relative_dir,
                "status": "imported",
                "priority": str(candidate.get("priority") or "").strip() or "P1",
                "category": domain,
            }
        )

    summary = {
        "candidates_file": "./" + str(candidates_path.relative_to(workspace)).replace("\\", "/"),
        "dest_root": "./" + str(dest_root.relative_to(workspace)).replace("\\", "/"),
        "selected_count": len(selected),
        "imported_count": len([item for item in imported if item["status"] == "imported"]),
        "skipped_existing_count": len([item for item in imported if item["status"] == "skipped_existing"]),
        "items": imported,
    }
    (output_dir / "skill_upstream_intake_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Skill Upstream Intake Report",
        "",
        f"- candidates_file: `{summary['candidates_file']}`",
        f"- dest_root: `{summary['dest_root']}`",
        f"- selected_count: `{summary['selected_count']}`",
        f"- imported_count: `{summary['imported_count']}`",
        f"- skipped_existing_count: `{summary['skipped_existing_count']}`",
        "",
        "## Items",
        "",
    ]
    for item in imported:
        lines.append(f"- `{item['id']}` | `{item['status']}` | `{item['path']}`")
    lines.append("")
    (output_dir / "skill_upstream_intake_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

