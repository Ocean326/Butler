from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re


LOCAL_INDEX_FILE = "L0_index.json"
LOCAL_RELATIONS_FILE = ".relations.json"
LOCAL_README_FILE = "readme.md"
LOCAL_L1_SUMMARY_DIR_NAME = "L1_summaries"
LOCAL_L2_DETAIL_DIR_NAME = "L2_details"
LOCAL_CATEGORY_NAMES = (
    "identity",
    "preferences",
    "rules",
    "projects",
    "research",
    "operations",
    "relationships",
    "references",
    "reflections",
    "misc",
)
PERSONAL_MEMORY_CATEGORIES = {"identity", "preferences", "relationships", "reflections"}
TOOL_MEMORY_CATEGORIES = {"rules", "references"}


@dataclass(frozen=True)
class LocalMemoryQueryParams:
    query_text: str = ""
    keyword: str = ""
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 20
    include_details: bool = False
    categories: tuple[str, ...] = ()
    memory_types: tuple[str, ...] = ()
    prefer_stable: bool = True


class LocalMemoryIndexService:
    def __init__(self, local_dir: Path) -> None:
        self.local_dir = Path(local_dir)

    def ensure_layout(self) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)
        _, l1_dir, l2_dir = self.layer_paths()
        l1_dir.mkdir(parents=True, exist_ok=True)
        l2_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            payload = self._default_index()
            payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if not self._relations_path.exists():
            payload = self._default_relations()
            payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._relations_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def layer_paths(self) -> tuple[Path, Path, Path]:
        return self._index_path, self.local_dir / LOCAL_L1_SUMMARY_DIR_NAME, self.local_dir / LOCAL_L2_DETAIL_DIR_NAME

    @property
    def _index_path(self) -> Path:
        return self.local_dir / LOCAL_INDEX_FILE

    @property
    def _relations_path(self) -> Path:
        return self.local_dir / LOCAL_RELATIONS_FILE

    def _default_index(self) -> dict:
        return {
            "schema_version": 3,
            "updated_at": "",
            "categories": [{"name": name, "description": ""} for name in LOCAL_CATEGORY_NAMES],
            "entries": [],
        }

    def _default_relations(self) -> dict:
        return {"schema_version": 1, "updated_at": "", "relations": []}

    def load_index(self) -> dict:
        self.ensure_layout()
        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            payload = self._default_index()
        if not isinstance(payload, dict):
            payload = self._default_index()
        payload.setdefault("schema_version", 3)
        payload.setdefault("updated_at", "")
        payload["categories"] = [item for item in payload.get("categories") or [] if isinstance(item, dict)]
        payload["entries"] = [item for item in payload.get("entries") or [] if isinstance(item, dict)]
        return payload

    def save_index(self, payload: dict) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)
        normalized = dict(payload or {})
        normalized["schema_version"] = 3
        normalized["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized["categories"] = [item for item in normalized.get("categories") or [] if isinstance(item, dict)][:10]
        normalized["entries"] = [item for item in normalized.get("entries") or [] if isinstance(item, dict)][-800:]
        self._index_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_relations(self) -> dict:
        self.ensure_layout()
        try:
            payload = json.loads(self._relations_path.read_text(encoding="utf-8"))
        except Exception:
            payload = self._default_relations()
        if not isinstance(payload, dict):
            payload = self._default_relations()
        payload.setdefault("schema_version", 1)
        payload.setdefault("updated_at", "")
        payload["relations"] = [item for item in payload.get("relations") or [] if isinstance(item, dict)]
        return payload

    def save_relations(self, payload: dict) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)
        normalized = dict(payload or {})
        normalized["schema_version"] = 1
        normalized["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized["relations"] = [item for item in normalized.get("relations") or [] if isinstance(item, dict)][-1200:]
        self._relations_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def rebuild_index(self) -> dict:
        self.ensure_layout()
        entries: list[dict] = []
        relations: list[dict] = []
        detail_by_stem = {path.stem.lower(): path for path in self._detail_candidate_files()}
        for path in self._summary_candidate_files():
            detail_path = detail_by_stem.get(path.stem.lower()) or detail_by_stem.get(f"{path.stem}_detail".lower())
            detail_rel = self._relative_path(detail_path) if detail_path else ""
            entries.append(self._build_entry(path, detail_rel=detail_rel))
            relations.append(
                {
                    "source_path": self._relative_path(path),
                    "target_path": detail_rel,
                    "relation_type": "summary_to_detail" if detail_rel else "summary_only",
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        referenced = {item["target_path"] for item in relations if str(item.get("target_path") or "").strip()}
        orphan_count = 0
        for path in self._detail_candidate_files():
            detail_rel = self._relative_path(path)
            if detail_rel in referenced:
                continue
            orphan_count += 1
            entries.append(self._build_entry(path, detail_rel=detail_rel, layer="L2"))
        payload = self._default_index()
        payload["entries"] = sorted(entries, key=lambda item: str(item.get("updated_at") or ""), reverse=True)[:800]
        self.save_index(payload)
        self.save_relations({"schema_version": 1, "relations": relations})
        return {
            "entry_count": len(payload["entries"]),
            "summary_file_count": len(self._summary_candidate_files()),
            "orphan_detail_count": orphan_count,
            "updated_at": self.load_index().get("updated_at"),
        }

    def query(self, params: LocalMemoryQueryParams) -> list[dict]:
        self._ensure_index_current()
        payload = self.load_index()
        tokens = self._tokenize(" ".join(part for part in [params.query_text, params.keyword] if str(part or "").strip()))
        keyword = str(params.keyword or "").strip().lower()
        category_filter = {str(item).strip() for item in params.categories if str(item).strip()}
        memory_type_filter = {str(item).strip() for item in params.memory_types if str(item).strip()}
        scored: list[tuple[float, dict]] = []
        for entry in payload.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category") or "misc").strip() or "misc"
            memory_type = str(entry.get("memory_type") or "task").strip() or "task"
            if category_filter and category not in category_filter:
                continue
            if memory_type_filter and memory_type not in memory_type_filter:
                continue
            updated_at = self._parse_datetime(str(entry.get("updated_at") or ""))
            if params.since and updated_at and updated_at < params.since:
                continue
            if params.until and updated_at and updated_at > params.until:
                continue
            score, detail_match = self._score_entry(entry, tokens=tokens, keyword=keyword, include_details=params.include_details)
            if (tokens or keyword) and score <= 0:
                continue
            if not tokens and not keyword and params.prefer_stable and str(entry.get("stability") or "") == "stable":
                score += 1.0
            scored.append((score, self._build_query_result(entry, include_details=params.include_details, detail_match=detail_match)))
        scored.sort(
            key=lambda item: (
                item[0],
                1 if str(item[1].get("stability") or "") == "stable" else 0,
                str(item[1].get("updated_at") or ""),
            ),
            reverse=True,
        )
        limit = max(1, int(params.limit or 20))
        return [item for _, item in scored[:limit]]

    def render_prompt_hits(
        self,
        query_text: str,
        *,
        limit: int = 4,
        include_details: bool = False,
        max_chars: int = 2400,
        categories: tuple[str, ...] = (),
        memory_types: tuple[str, ...] = (),
    ) -> str:
        matches = self.query(
            LocalMemoryQueryParams(
                query_text=query_text,
                limit=limit,
                include_details=include_details,
                categories=categories,
                memory_types=memory_types,
            )
        )
        lines: list[str] = []
        for item in matches:
            tags = "/".join(
                part
                for part in [
                    str(item.get("memory_type") or "").strip(),
                    str(item.get("category") or "").strip(),
                    str(item.get("stability") or "").strip(),
                ]
                if part
            )
            title = str(item.get("title") or "长期记忆").strip()
            current = str(item.get("current_conclusion") or item.get("snippet") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            line = f"- [{tags}] {title}: 当前结论: {current}" if tags else f"- {title}: 当前结论: {current}"
            if snippet and snippet not in current:
                line += f" | 命中片段: {snippet}"
            lines.append(line)
        text = "\n".join(lines).strip()
        return text if len(text) <= max_chars else text[:max_chars].rstrip() + "\n..."

    def _summary_candidate_files(self) -> list[Path]:
        _, l1_dir, _ = self.layer_paths()
        root_files = [
            path
            for path in self.local_dir.glob("*.md")
            if path.is_file() and path.name.lower() not in {LOCAL_README_FILE, LOCAL_INDEX_FILE.lower()}
        ]
        l1_files = [path for path in l1_dir.glob("*.md") if path.is_file()]
        return sorted(root_files + l1_files, key=lambda item: item.name.lower())

    def _detail_candidate_files(self) -> list[Path]:
        _, _, l2_dir = self.layer_paths()
        return sorted([path for path in l2_dir.glob("*.md") if path.is_file()], key=lambda item: item.name.lower())

    def _relative_path(self, path: Path | None) -> str:
        if not path:
            return ""
        try:
            return path.relative_to(self.local_dir).as_posix()
        except Exception:
            return path.name

    def _build_entry(self, path: Path, *, detail_rel: str, layer: str = "L1") -> dict:
        text = self._read_text(path)
        title = self._extract_title(path, text)
        current = self._extract_current_conclusion(text)
        summary = current or self._first_content_excerpt(text, limit=220)
        keywords = self._collect_keywords(title, text)
        category = self._choose_category(title, summary, keywords)
        updated_at = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "entry_id": path.stem,
            "title": title[:80],
            "category": category,
            "memory_type": self._infer_memory_type(category),
            "keywords": keywords[:8],
            "summary": summary[:220],
            "current_conclusion": current[:220] if current else summary[:220],
            "history_evolution": self._extract_list_section(text, "历史演化", limit=4),
            "applicable_scenarios": self._extract_list_section(text, "适用情景", limit=6),
            "current_effective": current[:220] if current else summary[:220],
            "layer": layer,
            "summary_path": self._relative_path(path) if layer != "L2" else "",
            "detail_path": detail_rel,
            "source_of_truth": self._relative_path(path),
            "retrieval_tags": keywords[:8],
            "stability": self._infer_stability(path, title, category),
            "source_type": "",
            "source_reason": "",
            "source_topic": title[:80],
            "updated_at": updated_at,
        }

    def _score_entry(self, entry: dict, *, tokens: set[str], keyword: str, include_details: bool) -> tuple[float, str]:
        haystack = "\n".join(
            [
                str(entry.get("title") or ""),
                str(entry.get("summary") or ""),
                str(entry.get("current_conclusion") or ""),
                " ".join(str(item) for item in entry.get("keywords") or []),
                " ".join(str(item) for item in entry.get("retrieval_tags") or []),
                " ".join(str(item) for item in entry.get("applicable_scenarios") or []),
            ]
        ).lower()
        score = 0.0
        if keyword and keyword in haystack:
            score += 6.0
        if tokens:
            score += float(sum(1 for token in tokens if token in haystack)) * 2.0
        detail_match = ""
        if include_details:
            detail_text = self._load_detail_text(entry)
            detail_lower = detail_text.lower()
            if keyword and keyword in detail_lower:
                score += 4.0
                detail_match = self._matching_line(detail_text, keyword)
            elif tokens:
                overlap = [token for token in tokens if token in detail_lower]
                if overlap:
                    score += float(len(overlap))
                    detail_match = self._matching_line(detail_text, overlap[0])
        if str(entry.get("stability") or "") == "stable":
            score += 0.5
        return score, detail_match

    def _build_query_result(self, entry: dict, *, include_details: bool, detail_match: str) -> dict:
        summary_rel = str(entry.get("summary_path") or "").strip()
        detail_rel = str(entry.get("detail_path") or "").strip()
        primary_path = self.local_dir / (summary_rel or detail_rel) if (summary_rel or detail_rel) else self.local_dir
        primary_text = self._read_primary_text(entry)
        snippet = detail_match or self._matching_line(primary_text, str(entry.get("current_conclusion") or ""))
        if not snippet:
            snippet = str(entry.get("current_conclusion") or entry.get("summary") or "").strip()[:220]
        return {
            "title": str(entry.get("title") or "长期记忆").strip(),
            "path": str(primary_path),
            "updated_at": str(entry.get("updated_at") or "").strip(),
            "snippet": snippet,
            "layer": str(entry.get("layer") or "L1").strip() or "L1",
            "category": str(entry.get("category") or "misc").strip() or "misc",
            "current_conclusion": str(entry.get("current_conclusion") or "").strip(),
            "history_evolution": entry.get("history_evolution") if isinstance(entry.get("history_evolution"), list) else [],
            "applicable_scenarios": entry.get("applicable_scenarios") if isinstance(entry.get("applicable_scenarios"), list) else [],
            "detail_path": str(self.local_dir / detail_rel) if detail_rel else "",
            "summary_path": str(self.local_dir / summary_rel) if summary_rel else "",
            "memory_type": str(entry.get("memory_type") or "task").strip() or "task",
            "stability": str(entry.get("stability") or "candidate").strip() or "candidate",
            "source_of_truth": str(entry.get("source_of_truth") or "").strip(),
            "retrieval_tags": entry.get("retrieval_tags") if isinstance(entry.get("retrieval_tags"), list) else [],
            "include_details": bool(include_details),
        }

    def _ensure_index_current(self) -> None:
        payload = self.load_index()
        entries = [item for item in payload.get("entries") or [] if isinstance(item, dict)]
        if payload.get("schema_version") != 3 or (not entries and (self._summary_candidate_files() or self._detail_candidate_files())):
            self.rebuild_index()

    def _read_primary_text(self, entry: dict) -> str:
        for rel_path in (str(entry.get("summary_path") or "").strip(), str(entry.get("detail_path") or "").strip()):
            if not rel_path:
                continue
            path = self.local_dir / rel_path
            if path.exists():
                return self._read_text(path)
        return ""

    def _load_detail_text(self, entry: dict) -> str:
        rel_path = str(entry.get("detail_path") or "").strip()
        if not rel_path:
            return ""
        path = self.local_dir / rel_path
        return self._read_text(path) if path.exists() else ""

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _extract_title(self, path: Path, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    return title
        return path.stem.replace("_", " ").strip() or path.stem

    def _extract_current_conclusion(self, text: str) -> str:
        lines = text.splitlines()
        headings = {"当前结论", "Current Conclusion", "current_conclusion"}
        for index, line in enumerate(lines):
            if line.strip().lstrip("#").strip() not in headings:
                continue
            collected: list[str] = []
            for candidate in lines[index + 1:]:
                raw = candidate.strip()
                if not raw:
                    if collected:
                        break
                    continue
                if raw.startswith("#") and collected:
                    break
                normalized = raw.lstrip("- ").strip()
                if normalized:
                    collected.append(normalized)
                if len("；".join(collected)) >= 220:
                    break
            if collected:
                return "；".join(collected)[:220]
        return self._first_content_excerpt(text, limit=220)

    def _extract_list_section(self, text: str, heading: str, limit: int) -> list[str]:
        lines = text.splitlines()
        results: list[str] = []
        for index, line in enumerate(lines):
            if line.strip().lstrip("#").strip() != heading:
                continue
            for candidate in lines[index + 1:]:
                raw = candidate.strip()
                if not raw:
                    if results:
                        break
                    continue
                if raw.startswith("#") and results:
                    break
                results.append(raw.lstrip("- ").strip()[:220])
                if len(results) >= limit:
                    break
            break
        return [item for item in results if item]

    def _first_content_excerpt(self, text: str, limit: int) -> str:
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped.lstrip("- "))
            if len(" ".join(lines)) >= limit:
                break
        return re.sub(r"\s+", " ", " ".join(lines)).strip()[:limit]

    def _collect_keywords(self, title: str, text: str) -> list[str]:
        keywords: list[str] = []
        for candidate in re.findall(r"[A-Za-z0-9_./-]{3,}|[\u4e00-\u9fff]{2,8}", f"{title}\n{text}"):
            normalized = str(candidate).strip().lower()
            if not normalized or normalized in keywords:
                continue
            if normalized in {"当前结论", "历史演化", "适用情景", "来源", "updated", "schema", "memory"}:
                continue
            keywords.append(normalized)
            if len(keywords) >= 12:
                break
        return keywords

    def _choose_category(self, title: str, summary: str, keywords: list[str]) -> str:
        text = "\n".join([title, summary, " ".join(keywords)]).lower()
        rules = {
            "identity": ["人格", "身份", "自我认知", "worldview", "identity", "soul"],
            "preferences": ["偏好", "喜好", "preference", "style", "画像"],
            "rules": ["规则", "约定", "must", "policy", "protocol"],
            "projects": ["项目", "workspace", "task", "任务", "upgrade"],
            "research": ["research", "论文", "文献", "组会", "实验"],
            "operations": ["运行", "心跳", "guardian", "maintenance", "ops", "治理"],
            "relationships": ["关系", "用户", "陪伴", "chat", "feishu"],
            "references": ["reference", "索引", "目录", "链接", "文档"],
            "reflections": ["反思", "复盘", "想法", "self_mind", "cognition"],
        }
        for category, patterns in rules.items():
            if any(pattern in text for pattern in patterns):
                return category
        return "misc"

    def _infer_memory_type(self, category: str) -> str:
        if category in PERSONAL_MEMORY_CATEGORIES:
            return "personal"
        if category in TOOL_MEMORY_CATEGORIES:
            return "tool"
        return "task"

    def _infer_stability(self, path: Path, title: str, category: str) -> str:
        rel_path = self._relative_path(path).lower()
        title_lower = title.lower()
        if any(marker in title_lower for marker in ("soul", "画像", "人格", "自我认知", "约定", "偏好")):
            return "stable"
        if any(marker in rel_path for marker in ("current_user_profile", "butler_soul", "人格", "飞书与记忆约定")):
            return "stable"
        if category in {"identity", "preferences", "rules", "relationships"}:
            return "stable"
        return "candidate"

    def _parse_datetime(self, value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return None

    def _matching_line(self, text: str, query: str) -> str:
        needle = str(query or "").strip().lower()
        if not needle:
            return ""
        for line in text.splitlines():
            stripped = line.strip()
            if needle in stripped.lower():
                return stripped[:220]
        return ""

    def _tokenize(self, text: str) -> set[str]:
        return {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9_./-]{3,}|[\u4e00-\u9fff]{2,8}", str(text or ""))
            if token.strip()
        }
