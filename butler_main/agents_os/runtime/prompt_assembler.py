from __future__ import annotations

from typing import Any, Mapping, Sequence


class PromptAssembler:
    def assemble(self, context: Mapping[str, Any], blocks: Sequence[str]) -> str:
        pieces = [str(context.get("base_prompt", ""))]
        pieces.extend(blocks)
        return "\n\n".join(piece for piece in pieces if piece)
