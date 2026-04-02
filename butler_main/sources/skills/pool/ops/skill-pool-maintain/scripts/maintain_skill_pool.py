from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
for parent in [CURRENT_FILE, *CURRENT_FILE.parents]:
    if (parent / "butler_main").exists():
        import sys

        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from butler_main.sources.skills.shared.workspace_layout import find_workspace_root, resolve_output_dir, skill_temp_dir


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>[\s\S]*?)\n---\s*\n?", re.MULTILINE)
REQUIRED_FIELDS = ("name", "description")
INACTIVE_SKILL_STATUSES = {"draft", "incubating", "archived", "disabled", "private"}


def _parse_frontmatter(text: str) -> dict[str, str]:
    matched = FRONTMATTER_RE.match(text or "")
    if not matched:
        return {}
    metadata: dict[str, str] = {}
    for raw_line in matched.group("body").splitlines():
        line = str(raw_line or "").strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip('"').strip("'")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Butler skill pool maintenance inventory and suggestions.")
    parser.add_argument("--workspace", default=".", help="Butler workspace root")
    parser.add_argument("--output-dir", default="", help="Output directory; defaults to butler_main/sources/skills/temp/maintain")
    args = parser.parse_args()

    workspace = find_workspace_root(Path(args.workspace).resolve())
    source_root = workspace / "butler_main" / "sources" / "skills" / "pool"
    registry_path = workspace / "butler_main" / "sources" / "skills" / "collections" / "registry.json"
    output_dir = resolve_output_dir(workspace, args.output_dir, default_path=skill_temp_dir(workspace, "maintain"))

    registry = {}
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    collection_membership: dict[str, list[str]] = {}
    for collection_id, payload in (registry.get("collections") or {}).items():
        for raw in payload.get("skills") or []:
            if isinstance(raw, dict):
                path_text = str(raw.get("path") or "")
            else:
                path_text = str(raw or "")
            collection_membership.setdefault(path_text.replace("\\", "/"), []).append(collection_id)

    inventory: list[dict] = []
    for root_name, root in (("source", source_root),):
        if not root.exists():
            continue
        for skill_file in sorted(root.rglob("SKILL.md")):
            if any(part.startswith("_tmp") or part == "__pycache__" for part in skill_file.parts):
                continue
            skill_dir = skill_file.parent
            rel_dir = "./" + str(skill_dir.relative_to(workspace)).replace("\\", "/")
            try:
                text = skill_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                inventory.append(
                    {
                        "source_root": root_name,
                        "path": rel_dir,
                        "name": skill_dir.name,
                        "description": "",
                        "category": "",
                        "status": "unknown",
                        "missing_fields": ["read_error"],
                        "collections": collection_membership.get(rel_dir, []),
                    }
                )
                continue
            metadata = _parse_frontmatter(text)
            missing = [field for field in REQUIRED_FIELDS if not str(metadata.get(field) or "").strip()]
            inventory.append(
                {
                    "source_root": root_name,
                    "path": rel_dir,
                    "name": str(metadata.get("name") or skill_dir.name),
                    "description": str(metadata.get("description") or "").strip(),
                    "category": str(metadata.get("category") or "").strip(),
                    "status": str(metadata.get("status") or "active").strip().lower() or "active",
                    "missing_fields": missing,
                    "collections": collection_membership.get(rel_dir, []),
                }
            )

    inventory.sort(key=lambda item: (item["source_root"], item["path"]))
    (output_dir / "skill_pool_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")

    source_only = [item for item in inventory if item["source_root"] == "source"]
    missing_meta = [item for item in inventory if item["missing_fields"]]
    uncollected = [item for item in inventory if not item["collections"]]
    inactive = [item for item in inventory if item["status"] in INACTIVE_SKILL_STATUSES]
    lines = [
        "# Skill Pool Maintenance Report",
        "",
        f"- source skills: `{len(source_only)}`",
        f"- missing frontmatter core fields: `{len(missing_meta)}`",
        f"- not exposed by any collection: `{len(uncollected)}`",
        f"- inactive or incubating skills: `{len(inactive)}`",
        "",
        "## Suggestions",
        "",
        "1. 优先把长期保留的 skill 迁到 `sources/skills/pool/`。",
        "2. 对缺少 `name/description` 的 skill 补 frontmatter。",
        "3. 对未进入任何 collection 的 skill，判断是保留私有、加入 `skill_ops`，还是归档。",
        "4. 对 `status=draft/incubating` 的 skill，保持不暴露，直到实现、验证和审阅完成。",
        "",
    ]
    if missing_meta:
        lines.extend(["## Missing Frontmatter", ""])
        for item in missing_meta:
            lines.append(f"- {item['path']} -> missing: {', '.join(item['missing_fields'])}")
        lines.append("")
    if uncollected:
        lines.extend(["## Uncollected Skills", ""])
        for item in uncollected[:30]:
            lines.append(f"- {item['path']}")
        lines.append("")
    if inactive:
        lines.extend(["## Inactive Skills", ""])
        for item in inactive[:30]:
            lines.append(f"- {item['path']} ({item['status']})")
        lines.append("")
    (output_dir / "skill_pool_maintenance_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"inventory": len(inventory), "output_dir": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
