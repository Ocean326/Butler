from __future__ import annotations

import os
from pathlib import Path


BUTLER_MAIN_REL = Path("butler_main")
PRODUCTS_REL = BUTLER_MAIN_REL / "products"
PLATFORM_REL = BUTLER_MAIN_REL / "platform"
COMPAT_REL = BUTLER_MAIN_REL / "compat"
INCUBATION_REL = BUTLER_MAIN_REL / "incubation"

HOST_RUNTIME_REL = BUTLER_MAIN_REL / "butler_bot_code"
HOST_BODY_MODULE_REL = HOST_RUNTIME_REL / "butler_bot"

LEGACY_CHAT_REL = BUTLER_MAIN_REL / "chat"
PRODUCT_CHAT_REL = PRODUCTS_REL / "chat"

LEGACY_ORCHESTRATOR_REL = BUTLER_MAIN_REL / "orchestrator"
PRODUCT_CAMPAIGN_ORCHESTRATOR_REL = PRODUCTS_REL / "campaign_orchestrator"
PRODUCT_ORCHESTRATOR_REL = PRODUCT_CAMPAIGN_ORCHESTRATOR_REL / "orchestrator"
PRODUCT_CONSOLE_REL = PRODUCT_CAMPAIGN_ORCHESTRATOR_REL / "console"
LEGACY_CONSOLE_REL = BUTLER_MAIN_REL / "console"
LEGACY_CAMPAIGN_REL = BUTLER_MAIN_REL / "domains" / "campaign"
PRODUCT_CAMPAIGN_REL = PRODUCT_CAMPAIGN_ORCHESTRATOR_REL / "campaign"

LEGACY_SKILLS_REL = BUTLER_MAIN_REL / "sources" / "skills"
PLATFORM_SKILLS_REL = PLATFORM_REL / "skills"

LEGACY_RESEARCH_REL = BUTLER_MAIN_REL / "research"
INCUBATION_RESEARCH_REL = INCUBATION_REL / "research"


_REPO_MARKERS: tuple[Path, ...] = (
    HOST_RUNTIME_REL,
    PRODUCT_CHAT_REL,
    LEGACY_CHAT_REL,
    PRODUCT_ORCHESTRATOR_REL,
    LEGACY_ORCHESTRATOR_REL,
    PRODUCT_CONSOLE_REL,
    LEGACY_CONSOLE_REL,
    PRODUCT_CAMPAIGN_REL,
    LEGACY_CAMPAIGN_REL,
    PLATFORM_SKILLS_REL,
    LEGACY_SKILLS_REL,
    INCUBATION_RESEARCH_REL,
    LEGACY_RESEARCH_REL,
    BUTLER_MAIN_REL / "runtime_os",
)


def _normalize_candidate_path(start: str | Path | None) -> Path:
    candidate = Path(start or os.getcwd()).resolve()
    if candidate.is_file():
        return candidate.parent
    return candidate


def is_butler_repo_root(candidate: str | Path) -> bool:
    path = Path(candidate).resolve()
    butler_main_dir = path / "butler_main"
    if not butler_main_dir.is_dir():
        return False
    return any((path / marker).exists() for marker in _REPO_MARKERS)


def resolve_repo_root(start: str | Path | None = None) -> Path:
    base = _normalize_candidate_path(start)
    nested = (base / "Butler").resolve()
    candidates: list[Path] = [base, *base.parents]
    if nested != base:
        candidates.extend([nested, *nested.parents])
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if is_butler_repo_root(candidate):
            return candidate
    return base


def resolve_repo_path(
    repo_root: str | Path,
    *,
    canonical_rel: Path,
    compat_rel: Path | None = None,
    prefer_canonical: bool = True,
    require_existing: bool = False,
) -> Path:
    root = Path(repo_root).resolve()
    ordered = [canonical_rel, compat_rel] if prefer_canonical else [compat_rel, canonical_rel]
    seen: set[str] = set()
    fallback = canonical_rel if prefer_canonical or compat_rel is None else compat_rel
    for rel in ordered:
        if rel is None:
            continue
        key = rel.as_posix()
        if key in seen:
            continue
        seen.add(key)
        candidate = root / rel
        if not require_existing or candidate.exists():
            return candidate
    return root / fallback


__all__ = [
    "BUTLER_MAIN_REL",
    "COMPAT_REL",
    "HOST_BODY_MODULE_REL",
    "HOST_RUNTIME_REL",
    "INCUBATION_RESEARCH_REL",
    "INCUBATION_REL",
    "LEGACY_CAMPAIGN_REL",
    "LEGACY_CHAT_REL",
    "LEGACY_CONSOLE_REL",
    "LEGACY_ORCHESTRATOR_REL",
    "LEGACY_RESEARCH_REL",
    "LEGACY_SKILLS_REL",
    "PLATFORM_REL",
    "PLATFORM_SKILLS_REL",
    "PRODUCT_CAMPAIGN_ORCHESTRATOR_REL",
    "PRODUCT_CAMPAIGN_REL",
    "PRODUCT_CHAT_REL",
    "PRODUCT_CONSOLE_REL",
    "PRODUCT_ORCHESTRATOR_REL",
    "PRODUCTS_REL",
    "is_butler_repo_root",
    "resolve_repo_path",
    "resolve_repo_root",
]
