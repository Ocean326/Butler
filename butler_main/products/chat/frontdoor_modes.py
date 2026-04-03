from __future__ import annotations

from dataclasses import dataclass
import re


MAIN_SCENE_SLASH_MODES = {"chat", "share", "brainstorm", "project", "bg"}
PROJECT_PHASE_SLASH_MODES = {"plan", "imp", "review"}
BACKGROUND_COMPAT_SLASH_MODES = {"delivery", "research"}
CONTROL_SLASH_MODES = {"status", "govern", "reset"}
_SUPPORTED_FRONTDOOR_MODES = (
    MAIN_SCENE_SLASH_MODES
    | PROJECT_PHASE_SLASH_MODES
    | BACKGROUND_COMPAT_SLASH_MODES
    | CONTROL_SLASH_MODES
)
_SLASH_MODE_PATTERN = re.compile(r"^/(?P<mode>[A-Za-z_]+)(?:\s+(?P<body>.*))?$", re.DOTALL)


@dataclass(slots=True, frozen=True)
class FrontDoorSlashCommand:
    mode_id: str
    command_text: str
    body: str = ""
    command_group: str = "scene"


def parse_frontdoor_slash_command(user_text: str) -> FrontDoorSlashCommand | None:
    text = str(user_text or "").strip()
    if not text.startswith("/"):
        return None
    matched = _SLASH_MODE_PATTERN.match(text)
    if matched is None:
        return None
    mode_id = str(matched.group("mode") or "").strip().lower()
    if mode_id not in _SUPPORTED_FRONTDOOR_MODES:
        return None
    body = str(matched.group("body") or "").strip()
    return FrontDoorSlashCommand(
        mode_id=mode_id,
        command_text=f"/{mode_id}",
        body=body,
        command_group=_command_group_for_mode(mode_id),
    )


def is_scene_mode(mode_id: str) -> bool:
    return str(mode_id or "").strip().lower() in MAIN_SCENE_SLASH_MODES


def is_project_phase_mode(mode_id: str) -> bool:
    return str(mode_id or "").strip().lower() in PROJECT_PHASE_SLASH_MODES


def is_control_mode(mode_id: str) -> bool:
    return str(mode_id or "").strip().lower() in CONTROL_SLASH_MODES


def is_background_compat_mode(mode_id: str) -> bool:
    return str(mode_id or "").strip().lower() in BACKGROUND_COMPAT_SLASH_MODES


def _command_group_for_mode(mode_id: str) -> str:
    normalized = str(mode_id or "").strip().lower()
    if normalized in MAIN_SCENE_SLASH_MODES:
        return "scene"
    if normalized in PROJECT_PHASE_SLASH_MODES:
        return "project_phase"
    if normalized in CONTROL_SLASH_MODES:
        return "control"
    if normalized in BACKGROUND_COMPAT_SLASH_MODES:
        return "background_compat"
    return "scene"


__all__ = [
    "BACKGROUND_COMPAT_SLASH_MODES",
    "CONTROL_SLASH_MODES",
    "FrontDoorSlashCommand",
    "MAIN_SCENE_SLASH_MODES",
    "PROJECT_PHASE_SLASH_MODES",
    "is_background_compat_mode",
    "is_control_mode",
    "is_project_phase_mode",
    "is_scene_mode",
    "parse_frontdoor_slash_command",
]
