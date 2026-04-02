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
OBSOLETE_MEMORY_MARKERS = (
    "已退役",
    "过时",
    "obsolete",
    "历史材料",
    "历史诊断参考",
    "不再作为现役",
    "不再作为运行时",
    "不再作为 prompt 真源",
    "仅保留为历史",
    "仅视为过时材料",
    "已清退",
    "已删除",
)
LEGACY_RUNTIME_TOKENS = (
    "guardian",
    "restart_guardian_agent",
    "feishu-workstation-agent",
    "sub-agent",
    "team execution",
    "public agent library",
    "memory_manager",
)
CURRENT_RUNTIME_MARKERS = (
    "background_maintenance",
    "task_ledger.json",
    "codex 原生",
    "chat 前台不再维护",
    "当前守护",
    "当前真源",
    "已退役",
    "不再作为现役",
)


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
    exclude_obsolete: bool = True


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

    def query(self, params: LocalMemoryQueryParams) -> list[dict]:
        self._ensure_index_current()
        payload = self.load_index()
        tokens = self._tokenize(" ".join(part for part in [params.query_text, params.keyword] if str(part or "").strip()))
        keyword = str(params.keyword or "").strip().lower()
        category_filter = {str(item).strip() for item in params.categories if str(item).strip()}
        memory_type_filter = {self._normalize_memory_type(str(item).strip()) for item in params.memory_types if str(item).strip()}
        scored: list[tuple[float, dict]] = []
        for entry in payload.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category") or "misc").strip() or "misc"
            memory_type = self._normalize_memory_type(str(entry.get("memory_type") or "task").strip() or "task")
            if params.exclude_obsolete and self._is_obsolete_entry(entry):
                continue
            if category_filter and category not in category_filter:
                continue
            if memory_type_filter and memory_type not in memory_type_filter:
                continue
            score = self._score_entry(entry, tokens=tokens, keyword=keyword)
            if (tokens or keyword) and score <= 0:
                continue
            if not tokens and not keyword and str(entry.get("stability") or "") == "stable" and params.prefer_stable:
                score += 1.0
            scored.append((score, dict(entry)))
        scored.sort(key=lambda item: (item[0], str(item[1].get("updated_at") or "")), reverse=True)
        return [item for _, item in scored[: max(1, int(params.limit or 20))]]

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
            line = f"- [{tags}] {title}: 当前结论: {current}" if tags else f"- {title}: 当前结论: {current}"
            lines.append(line)
        text = "\n".join(lines).strip()
        return text if len(text) <= max_chars else text[:max_chars].rstrip() + "\n..."

    def rebuild_index(self) -> dict:
        self.ensure_layout()
        entries: list[dict] = []
        for path in self._iter_source_files():
            text = self._read_text(path)
            entries.append(
                {
                    "entry_id": path.stem,
                    "title": self._extract_title(path, text),
                    "category": self._choose_category(text),
                    "memory_type": self._infer_memory_type(self._choose_category(text)),
                    "current_conclusion": self._extract_current_conclusion(text) or self._first_content_excerpt(text, limit=220),
                    "snippet": self._first_content_excerpt(text, limit=220),
                    "source_path": path.name,
                    "stability": "stable" if any(token in text for token in ("长期", "默认", "约定")) else "volatile",
                    "updated_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        payload = self._default_index()
        payload["entries"] = entries[:800]
        self.save_index(payload)
        return {"entry_count": len(entries), "updated_at": payload.get("updated_at", "")}

    def _ensure_index_current(self) -> None:
        self.ensure_layout()
        source_files = self._iter_source_files()
        if not self._index_path.exists():
            self.rebuild_index()
            return
        payload = self.load_index()
        if source_files and not (payload.get("entries") or []):
            self.rebuild_index()
            return
        try:
            index_mtime = self._index_path.stat().st_mtime
        except OSError:
            self.rebuild_index()
            return
        latest_source_mtime = 0.0
        for path in source_files:
            try:
                latest_source_mtime = max(latest_source_mtime, path.stat().st_mtime)
            except OSError:
                continue
        if latest_source_mtime > index_mtime:
            self.rebuild_index()

    def _score_entry(self, entry: dict, *, tokens: list[str], keyword: str) -> float:
        haystack = " ".join(
            [
                str(entry.get("title") or ""),
                str(entry.get("current_conclusion") or ""),
                str(entry.get("snippet") or ""),
            ]
        ).lower()
        score = 0.0
        for token in tokens:
            if token and token in haystack:
                score += 1.0
        if keyword and keyword in haystack:
            score += 1.5
        return score

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _iter_source_files(self) -> list[Path]:
        _, l1_dir, _ = self.layer_paths()
        source_files = [path for path in self.local_dir.glob("*.md") if path.name.lower() != LOCAL_README_FILE]
        source_files.extend(path for path in l1_dir.glob("*.md"))
        return sorted(source_files, key=lambda item: item.name.lower())

    def _extract_title(self, path: Path, text: str) -> str:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                return line.lstrip("#").strip()[:80]
            return line[:80]
        return path.stem

    def _extract_current_conclusion(self, text: str) -> str:
        matched = re.search(r"(?:当前结论|结论)[:：]\s*(.+)", text)
        return matched.group(1).strip()[:220] if matched else ""

    def _first_content_excerpt(self, text: str, *, limit: int) -> str:
        return re.sub(r"\s+", " ", text or "").strip()[:limit]

    def _choose_category(self, text: str) -> str:
        haystack = str(text or "").lower()
        if any(token in haystack for token in ("偏好", "喜欢", "习惯", "preference")):
            return "preferences"
        if any(token in haystack for token in ("规则", "约束", "必须", "rule")):
            return "rules"
        if any(token in haystack for token in ("项目", "任务", "推进", "project")):
            return "projects"
        if any(token in haystack for token in ("关系", "朋友", "家人", "relationship")):
            return "relationships"
        if any(token in haystack for token in ("研究", "资料", "paper", "research")):
            return "research"
        return "misc"

    def _infer_memory_type(self, category: str) -> str:
        if category in PERSONAL_MEMORY_CATEGORIES:
            return "personal"
        if category in TOOL_MEMORY_CATEGORIES:
            return "reference"
        return "task"

    def _tokenize(self, text: str) -> list[str]:
        raw = str(text or "")
        tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9_:-]{2,}|[\u4e00-\u9fff]{2,}", raw)]
        compact_cn = "".join(re.findall(r"[\u4e00-\u9fff]", raw))
        for size in (2, 3, 4):
            if len(compact_cn) < size:
                continue
            for idx in range(len(compact_cn) - size + 1):
                tokens.append(compact_cn[idx: idx + size])
        deduped: list[str] = []
        for token in tokens:
            if token and token not in deduped:
                deduped.append(token)
        return deduped

    def _normalize_memory_type(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"profile", "personal", "persona"}:
            return "personal"
        if normalized in {"reference", "tool", "tools"}:
            return "reference"
        return normalized or "task"

    def _is_obsolete_entry(self, entry: dict) -> bool:
        title = str(entry.get("title") or "").strip()
        source_path = str(entry.get("source_path") or "").strip()
        identity_haystack = " ".join([title, source_path]).lower()
        body_haystack = " ".join(
            [
                str(entry.get("current_conclusion") or ""),
                str(entry.get("snippet") or ""),
            ]
        ).lower()
        haystack = f"{identity_haystack} {body_haystack}".strip()
        if not haystack:
            return False
        has_obsolete_marker = any(marker.lower() in haystack for marker in OBSOLETE_MEMORY_MARKERS)
        has_legacy_identity = any(token in identity_haystack for token in LEGACY_RUNTIME_TOKENS)
        has_current_marker = any(marker.lower() in haystack for marker in CURRENT_RUNTIME_MARKERS)
        if has_legacy_identity and (has_obsolete_marker or not has_current_marker):
            return True
        if has_obsolete_marker and not has_current_marker:
            return True
        return False


__all__ = ["LocalMemoryIndexService", "LocalMemoryQueryParams"]
