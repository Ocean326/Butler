if __name__.startswith("butler_main."):
    from butler_main.runtime_os.process_runtime.contracts import (
        CollaborationPrimitiveContract,
        FROZEN_TYPED_PRIMITIVE_IDS,
        FROZEN_TYPED_PRIMITIVES,
        primitive_contract_by_id,
    )
else:  # pragma: no cover - compatibility for top-level package imports
    from runtime_os.process_runtime.contracts import (
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
