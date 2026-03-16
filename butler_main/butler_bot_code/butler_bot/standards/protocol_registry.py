from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from standards.architecture_manifest import protocol_spec_map


@dataclass(frozen=True)
class ProtocolDocument:
    protocol_id: str
    title: str
    relative_path: str
    applies_to: tuple[str, ...]
    summary: str
    text: str


class ProtocolRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parent
        self._protocols_dir = self._root / "protocols"
        self._spec_map = protocol_spec_map()

    def get(self, protocol_id: str) -> ProtocolDocument | None:
        normalized = str(protocol_id or "").strip()
        spec = self._spec_map.get(normalized)
        if spec is None:
            return None
        path = self._protocols_dir / Path(spec.relative_path).name
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        return ProtocolDocument(
            protocol_id=spec.protocol_id,
            title=spec.title,
            relative_path=spec.relative_path,
            applies_to=spec.applies_to,
            summary=spec.summary,
            text=text,
        )

    def render_prompt_block(self, protocol_id: str, *, heading: str | None = None) -> str:
        document = self.get(protocol_id)
        if document is None or not document.text:
            return ""
        title = str(heading or document.title).strip() or document.title
        return f"【{title}】\n{document.text}\n\n"

    def render_catalog(self, protocol_ids: list[str] | tuple[str, ...]) -> str:
        lines: list[str] = []
        for protocol_id in protocol_ids:
            document = self.get(protocol_id)
            if document is None:
                continue
            lines.append(f"- {document.protocol_id}: {document.summary}")
        return "\n".join(lines).strip()


@lru_cache(maxsize=1)
def get_protocol_registry() -> ProtocolRegistry:
    return ProtocolRegistry()
