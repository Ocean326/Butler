try:
    from butler_main.multi_agents_os.session.collaboration import (
        CollaborationSubstrate,
        JoinContract,
        MailboxMessage,
        RoleHandoff,
        StepOwnership,
    )
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.session.collaboration import (
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
