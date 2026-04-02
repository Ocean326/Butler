if __name__.startswith("butler_main."):
    from butler_main.runtime_os.process_runtime.session import (
        CollaborationSubstrate,
        JoinContract,
        MailboxMessage,
        RoleHandoff,
        StepOwnership,
    )
else:  # pragma: no cover - compatibility for top-level package imports
    from runtime_os.process_runtime.session import (
        CollaborationSubstrate,
        JoinContract,
        MailboxMessage,
        RoleHandoff,
        StepOwnership,
    )

__all__ = [
    "CollaborationSubstrate",
    "JoinContract",
    "MailboxMessage",
    "RoleHandoff",
    "StepOwnership",
]
