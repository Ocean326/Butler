from __future__ import annotations

import os
from pathlib import Path


BODY_HOME_REL = Path("butler_main") / "butler_bot_code"
AGENT_HOME_REL = Path("butler_main") / "butler_bot_agent" / "agents"
SKILLS_HOME_REL = Path("butler_main") / "butler_bot_agent" / "skills"
SPACE_HOME_REL = Path("butler_main") / "butle_bot_space"
COMPANY_HOME_REL = Path("工作区")
STATE_DIR_REL = AGENT_HOME_REL / "state"
TASK_WORKSPACES_DIR_REL = STATE_DIR_REL / "task_workspaces"
GUARDIAN_REQUESTS_DIR_REL = STATE_DIR_REL / "guardian_requests"
GUARDIAN_LEDGER_DIR_REL = STATE_DIR_REL / "guardian_ledger"
FEISHU_AGENT_ROLE_FILE_REL = AGENT_HOME_REL / "feishu-workstation-agent.md"
HEARTBEAT_PLANNER_AGENT_ROLE_FILE_REL = AGENT_HOME_REL / "heartbeat-planner-agent.md"
HEARTBEAT_PLANNER_CONTEXT_FILE_REL = AGENT_HOME_REL / "heartbeat-planner-context.md"
SUBCONSCIOUS_AGENT_ROLE_FILE_REL = AGENT_HOME_REL / "subconscious-agent.md"
FILE_MANAGER_AGENT_ROLE_FILE_REL = AGENT_HOME_REL / "sub-agents" / "file-manager-agent.md"
HEARTBEAT_EXECUTOR_AGENT_ROLE_FILE_REL = AGENT_HOME_REL / "sub-agents" / "heartbeat-executor-agent.md"
RECENT_MEMORY_DIR_REL = AGENT_HOME_REL / "recent_memory"
BEAT_RECENT_MEMORY_DIR_REL = RECENT_MEMORY_DIR_REL / "beat_recent"
LOCAL_MEMORY_DIR_REL = AGENT_HOME_REL / "local_memory"
BUTLER_SOUL_FILE_REL = LOCAL_MEMORY_DIR_REL / "Butler_SOUL.md"
CURRENT_USER_PROFILE_FILE_REL = LOCAL_MEMORY_DIR_REL / "Current_User_Profile.private.md"
CURRENT_USER_PROFILE_TEMPLATE_FILE_REL = LOCAL_MEMORY_DIR_REL / "Current_User_Profile.template.md"
TASK_LEDGER_REL = STATE_DIR_REL / "task_ledger.json"
HEARTBEAT_LAST_SENT_REL = RECENT_MEMORY_DIR_REL / "heartbeat_last_sent.json"
MANAGER_PS1_REL = BODY_HOME_REL / "manager.ps1"
RUN_DIR_REL = BODY_HOME_REL / "run"
LOG_DIR_REL = BODY_HOME_REL / "logs"
CONFIG_DIR_REL = BODY_HOME_REL / "configs"
PROMPTS_DIR_REL = BODY_HOME_REL / "prompts"
HEARTBEAT_PROMPT_REL = PROMPTS_DIR_REL / "heart_beat.md"
RESTART_REQUEST_JSON_REL = COMPANY_HOME_REL / "restart_request.json"
HEARTBEAT_UPGRADE_REQUEST_JSON_REL = COMPANY_HOME_REL / "heartbeat_upgrade_request.json"
RESTART_REPORT_DIR_REL = COMPANY_HOME_REL / "governance" / "self_upgrade_reports"


def prompt_path_text(path: Path) -> str:
    return f"./{path.as_posix()}"


def _normalize_workspace_candidate(workspace: str | Path | None) -> Path:
    candidate = Path(workspace or os.getcwd()).resolve()
    parts_lower = [p.lower() for p in candidate.parts]
    if "butler_main" in parts_lower:
        idx = parts_lower.index("butler_main")
        if idx > 0:
            return Path(*candidate.parts[:idx])
    if candidate.name in {"butler_bot_code", "butler_bot_agent", "butle_bot_space"} and candidate.parent.name == "butler_main":
        return candidate.parent.parent
    if candidate.name in {"butler_bot", "scripts"} and candidate.parent.name == "butler_bot_code":
        return candidate.parent.parent.parent
    if candidate.name == "工作区":
        return candidate.parent
    return candidate


def resolve_butler_root(workspace: str | Path | None = None) -> Path:
    base = _normalize_workspace_candidate(workspace)
    candidates = [base, base / "Butler"]
    if workspace is None:
        candidates.append(Path(__file__).resolve().parents[3])
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        if (resolved / "butler_main" / "butler_bot_agent").exists() and (resolved / "butler_main" / "butler_bot_code").exists():
            return resolved
    return base