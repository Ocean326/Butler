from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class ProtocolSpec:
    protocol_id: str
    title: str
    relative_path: str
    applies_to: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class ProtocolDocument:
    protocol_id: str
    title: str
    relative_path: str
    applies_to: tuple[str, ...]
    summary: str
    text: str


PROTOCOL_SPECS: tuple[ProtocolSpec, ...] = (
    ProtocolSpec("frontdoor_collaboration", "前门协作协议", "protocols/frontdoor_collaboration.md", ("frontdoor", "dialogue", "collaboration"), "统一 chat 前门作为协作消费者的对话口径。"),
    ProtocolSpec("background_entry_collaboration", "后台入口协作协议", "protocols/background_entry_collaboration.md", ("frontdoor", "background_entry", "collaboration"), "统一后台任务入口的协商、确认与最小正确性口径。"),
    ProtocolSpec("status_query_collaboration", "状态查询协作协议", "protocols/status_query_collaboration.md", ("frontdoor", "status_query", "observation"), "统一读取 observation 结果后的自然语言进度回报口径。"),
    ProtocolSpec("task_collaboration", "任务协作协议", "protocols/task_collaboration.md", ("dialogue", "task_ledger"), "统一任务入口、状态真源、验收回执与任务收口口径。"),
    ProtocolSpec("update_agent_maintenance", "统一维护入口协议", "protocols/update_agent_maintenance.md", ("maintenance", "update_agent"), "统一 role/prompt/code/config 收敛口径，先找单一真源再改。"),
    ProtocolSpec("self_update", "自我更新协作协议", "protocols/self_update.md", ("maintenance", "upgrade", "governor"), "约束自我升级必须走方案、审批、验证、回执链路。"),
    ProtocolSpec("self_mind_collaboration", "自我认识协作协议", "protocols/self_mind_collaboration.md", ("dialogue", "self_mind", "memory"), "统一 self_mind 与对话记忆层之间的分工和交接边界。"),
)


class ProtocolRegistry:
    def __init__(self, root: Path | None = None) -> None:
        base_root = root or Path(__file__).resolve().parent
        self._protocols_dir = base_root / "protocols"
        self._spec_map = {item.protocol_id: item for item in PROTOCOL_SPECS}

    def get(self, protocol_id: str) -> ProtocolDocument | None:
        spec = self._spec_map.get(str(protocol_id or "").strip())
        if spec is None:
            return None
        path = self._protocols_dir / Path(spec.relative_path).name
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        return ProtocolDocument(spec.protocol_id, spec.title, spec.relative_path, spec.applies_to, spec.summary, text)

    def render_prompt_block(self, protocol_id: str, *, heading: str | None = None) -> str:
        document = self.get(protocol_id)
        if document is None or not document.text:
            return ""
        title = str(heading or document.title).strip() or document.title
        return f"【{title}】\n{document.text}\n\n"


@lru_cache(maxsize=1)
def get_protocol_registry() -> ProtocolRegistry:
    return ProtocolRegistry()


__all__ = ["ProtocolRegistry", "get_protocol_registry"]
