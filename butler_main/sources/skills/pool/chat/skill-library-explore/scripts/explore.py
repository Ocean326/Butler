"""
skill-library-explore: 多源技能/工具搜索与安全评估报告生成。
支持 GitHub / PyPI / npm 公开 API，无需鉴权。
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
for parent in [CURRENT_FILE, *CURRENT_FILE.parents]:
    if (parent / "butler_main").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from butler_main.sources.skills.shared.workspace_layout import find_workspace_root, resolve_output_dir, skill_temp_dir


USER_AGENT = "Butler-SkillExplorer/0.1"
TIMEOUT = 15


def _get(url: str) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
        print(f"  [WARN] 请求失败 {url}: {exc}", file=sys.stderr)
        return None


def _age_label(iso_str: str | None) -> str:
    if not iso_str:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - dt).days
        if days < 30:
            return f"{days}d ago (active)"
        if days < 180:
            return f"{days // 30}mo ago"
        return f"{days // 365}y+ ago (stale)"
    except Exception:
        return iso_str


def _safety(item: dict) -> list[str]:
    notes = []
    lic = item.get("license") or "unknown"
    if lic.lower() in ("unknown", "other", "none", ""):
        notes.append("许可证不明，需人工确认")
    pop = item.get("popularity", 0)
    if isinstance(pop, (int, float)) and pop < 10:
        notes.append(f"低人气 ({pop})，需额外审慎")
    if "stale" in item.get("last_updated_label", ""):
        notes.append("长期未更新，可能已弃维")
    return notes if notes else ["初筛无明显风险"]


# ── GitHub ────────────────────────────────────────────────

def search_github(query: str, limit: int = 5, lang: str | None = None) -> list[dict]:
    q = query
    if lang:
        q += f" language:{lang}"
    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&per_page={limit}"
    data = _get(url)
    if not data or "items" not in data:
        return []
    results = []
    for r in data["items"][:limit]:
        updated = r.get("pushed_at") or r.get("updated_at")
        item = {
            "source": "github",
            "name": r.get("full_name", ""),
            "description": (r.get("description") or "")[:200],
            "url": r.get("html_url", ""),
            "popularity": r.get("stargazers_count", 0),
            "license": (r.get("license") or {}).get("spdx_id", "unknown"),
            "last_updated": updated,
            "last_updated_label": _age_label(updated),
            "language": r.get("language", ""),
        }
        item["safety_notes"] = _safety(item)
        results.append(item)
    return results


# ── PyPI ──────────────────────────────────────────────────

def search_pypi(query: str, limit: int = 5) -> list[dict]:
    """PyPI 没有官方搜索 API，用 warehouse 的 simple search (JSON) 做近似。"""
    url = f"https://pypi.org/search/?q={urllib.parse.quote(query)}&o="
    # PyPI search 返回 HTML；改用 pypi.org/pypi/<name>/json 做精确查询行不通。
    # 折中方案：用 Google Custom Search 或直接列出 top candidates。
    # MVP 阶段：尝试通过 warehouse XML-RPC (已弃) 或直接 JSON endpoint。
    # 实际可用方案：使用 libraries.io API（免费 60 次/min）
    libs_url = f"https://libraries.io/api/search?q={urllib.parse.quote(query)}&platforms=pypi&per_page={limit}"
    data = _get(libs_url)
    if not data:
        return _pypi_fallback(query, limit)
    results = []
    for pkg in data[:limit]:
        updated = pkg.get("latest_stable_release_published_at") or pkg.get("latest_release_published_at")
        item = {
            "source": "pypi",
            "name": pkg.get("name", ""),
            "description": (pkg.get("description") or "")[:200],
            "url": pkg.get("homepage") or pkg.get("repository_url") or f"https://pypi.org/project/{pkg.get('name', '')}/",
            "popularity": pkg.get("stars", 0) or pkg.get("dependents_count", 0),
            "license": pkg.get("licenses") or "unknown",
            "last_updated": updated,
            "last_updated_label": _age_label(updated),
        }
        item["safety_notes"] = _safety(item)
        results.append(item)
    return results


def _pypi_fallback(query: str, limit: int) -> list[dict]:
    """当 libraries.io 不可用时，用 GitHub 搜索 Python 语言仓库作为兜底。"""
    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}+language:python&sort=stars&per_page={limit}"
    data = _get(url)
    if not data or "items" not in data:
        return []
    results = []
    for r in data["items"][:limit]:
        updated = r.get("pushed_at")
        item = {
            "source": "pypi (via github)",
            "name": r.get("full_name", ""),
            "description": (r.get("description") or "")[:200],
            "url": r.get("html_url", ""),
            "popularity": r.get("stargazers_count", 0),
            "license": (r.get("license") or {}).get("spdx_id", "unknown"),
            "last_updated": updated,
            "last_updated_label": _age_label(updated),
        }
        item["safety_notes"] = _safety(item)
        results.append(item)
    return results


# ── npm ───────────────────────────────────────────────────

def _npm_license(name: str) -> str:
    """从 npm 包详情 API 获取 license，搜索 API 不含此字段。"""
    if not name:
        return "unknown"
    data = _get(f"https://registry.npmjs.org/{urllib.parse.quote(name)}/latest")
    if isinstance(data, dict):
        lic = data.get("license")
        if isinstance(lic, str) and lic:
            return lic
        if isinstance(lic, dict):
            return lic.get("type", "unknown")
    return "unknown"


def search_npm(query: str, limit: int = 5) -> list[dict]:
    url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(query)}&size={limit}"
    data = _get(url)
    if not data or "objects" not in data:
        return []
    results = []
    for obj in data["objects"][:limit]:
        pkg = obj.get("package", {})
        score = obj.get("score", {}).get("detail", {})
        updated = pkg.get("date")
        item = {
            "source": "npm",
            "name": pkg.get("name", ""),
            "description": (pkg.get("description") or "")[:200],
            "url": pkg.get("links", {}).get("npm") or f"https://www.npmjs.com/package/{pkg.get('name', '')}",
            "popularity": round(score.get("popularity", 0) * 1000),
            "license": _npm_license(pkg.get("name", "")),
            "last_updated": updated,
            "last_updated_label": _age_label(updated),
        }
        item["safety_notes"] = _safety(item)
        results.append(item)
    return results


# ── 报告生成 ──────────────────────────────────────────────

def generate_report(query: str, all_results: list[dict]) -> str:
    lines = [
        f"# 技能/工具探索报告",
        f"",
        f"- **搜索词**: {query}",
        f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **结果数**: {len(all_results)}",
        f"",
    ]

    by_source: dict[str, list[dict]] = {}
    for r in all_results:
        by_source.setdefault(r["source"], []).append(r)

    for source, items in by_source.items():
        lines.append(f"## {source.upper()}")
        lines.append("")
        for i, item in enumerate(items, 1):
            lines.append(f"### {i}. {item['name']}")
            lines.append(f"")
            lines.append(f"- **描述**: {item['description']}")
            lines.append(f"- **链接**: {item['url']}")
            lines.append(f"- **人气**: {item['popularity']}")
            lines.append(f"- **许可证**: {item['license']}")
            lines.append(f"- **最后更新**: {item['last_updated_label']}")
            lines.append(f"- **安全评估**: {'; '.join(item['safety_notes'])}")
            lines.append("")
        lines.append("---")
        lines.append("")

    if not all_results:
        lines.append("> 未找到相关结果。建议调整关键词或手动在 GitHub / PyPI / npm 上搜索。")

    lines.append("## 下一步建议")
    lines.append("")
    lines.append("1. 从以上候选中选择最匹配的 1-2 个，人工审阅源码与依赖。")
    lines.append("2. 审阅通过后，按 `skills.md` 约定落地为本地 skill 或 MCP 接入。")
    lines.append("3. 落地后回到原任务重试，验证能力是否补齐。")
    lines.append("")
    return "\n".join(lines)


# ── 主流程 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="多源技能/工具探索")
    parser.add_argument("--query", required=True, help="搜索关键词")
    parser.add_argument("--sources", default="github,pypi,npm", help="搜索源，逗号分隔")
    parser.add_argument("--limit", type=int, default=5, help="每源最大结果数")
    parser.add_argument("--output-dir", default="", help="输出目录，默认 butler_main/sources/skills/temp/explore")
    parser.add_argument("--lang", default=None, help="偏好语言（仅 GitHub）")
    args = parser.parse_args()
    workspace = find_workspace_root(Path.cwd())
    output_dir = resolve_output_dir(workspace, args.output_dir, default_path=skill_temp_dir(workspace, "explore"))

    sources = [s.strip().lower() for s in args.sources.split(",")]
    all_results: list[dict] = []

    print(f"[skill-library-explore] 搜索: {args.query}")
    print(f"[skill-library-explore] 源: {', '.join(sources)} | 每源上限: {args.limit}")

    if "github" in sources:
        print("  → 搜索 GitHub ...")
        all_results.extend(search_github(args.query, args.limit, args.lang))

    if "pypi" in sources:
        print("  → 搜索 PyPI ...")
        all_results.extend(search_pypi(args.query, args.limit))

    if "npm" in sources:
        print("  → 搜索 npm ...")
        all_results.extend(search_npm(args.query, args.limit))

    print(f"[skill-library-explore] 共找到 {len(all_results)} 条结果")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(str(output_dir), f"explore_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"query": args.query, "sources": sources, "results": all_results}, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(str(output_dir), f"explore_{ts}.md")
    report = generate_report(args.query, all_results)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[skill-library-explore] 报告已生成:")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")


if __name__ == "__main__":
    main()
