from __future__ import annotations

from butler_paths import CURRENT_USER_PROFILE_FILE_REL, resolve_butler_root

from ..models import ProfileWriteRequest


class UserProfileWriterAdapter:
    def __init__(self, manager=None) -> None:
        self._manager = manager

    def apply(self, workspace: str, request: ProfileWriteRequest) -> str:
        root = resolve_butler_root(workspace)
        path = root / CURRENT_USER_PROFILE_FILE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except Exception:
                existing = ""

        content = str(request.content or "").strip()
        if not content:
            return "skip-empty-profile-write"

        if request.action == "forget":
            updated = self._remove_line(existing, content)
            path.write_text(updated, encoding="utf-8")
            return "profile-forget"

        category = str(request.category or "misc").strip() or "misc"
        line = f"- {content}"
        section_title = f"## {category}"
        updated = self._upsert_section_line(existing, section_title, line)
        path.write_text(updated, encoding="utf-8")
        return "profile-write"

    def _remove_line(self, text: str, content: str) -> str:
        lines = [line for line in str(text or "").splitlines() if content not in line]
        return "\n".join(lines).rstrip() + ("\n" if lines else "")

    def _upsert_section_line(self, text: str, section_title: str, line: str) -> str:
        source = str(text or "").rstrip()
        if not source:
            return f"{section_title}\n{line}\n"
        if line in source:
            return source + "\n"
        if section_title not in source:
            return source + f"\n\n{section_title}\n{line}\n"
        lines = source.splitlines()
        out: list[str] = []
        inserted = False
        for index, current in enumerate(lines):
            out.append(current)
            if current.strip() != section_title:
                continue
            next_index = index + 1
            while next_index < len(lines) and lines[next_index].strip().startswith("- "):
                next_index += 1
            out.append(line)
            inserted = True
        if not inserted:
            out.extend(["", section_title, line])
        return "\n".join(out).rstrip() + "\n"
