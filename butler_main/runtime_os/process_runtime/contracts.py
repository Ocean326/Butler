"""Typed collaboration contracts owned by the process runtime layer."""

try:
    from butler_main.multi_agents_os.session.contracts import (
        CollaborationPrimitiveContract,
        FROZEN_TYPED_PRIMITIVE_IDS,
        FROZEN_TYPED_PRIMITIVES,
        primitive_contract_by_id,
    )
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.session.contracts import (
        CollaborationPrimitiveContract,
        FROZEN_TYPED_PRIMITIVE_IDS,
        FROZEN_TYPED_PRIMITIVES,
        primitive_contract_by_id,
    )

__all__ = [
    "CollaborationPrimitiveContract",
    "FROZEN_TYPED_PRIMITIVE_IDS",
    "FROZEN_TYPED_PRIMITIVES",
    "primitive_contract_by_id",
]
