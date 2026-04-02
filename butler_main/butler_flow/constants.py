from __future__ import annotations

from pathlib import Path

FLOW_ASSET_HOME_REL = Path("butler_main") / "butler_bot_code" / "assets" / "flows"
FLOW_BUILTIN_HOME_REL = FLOW_ASSET_HOME_REL / "builtin"
FLOW_TEMPLATE_HOME_REL = FLOW_ASSET_HOME_REL / "templates"
FLOW_INSTANCE_HOME_REL = FLOW_ASSET_HOME_REL / "instances"
FLOW_BUNDLE_HOME_REL = FLOW_ASSET_HOME_REL / "bundles"
FLOW_AUDIT_LOG_REL = FLOW_ASSET_HOME_REL / "manage_audit.jsonl"
FLOW_RUN_HOME_REL = Path("butler_main") / "butler_bot_code" / "run" / "butler_flow"
FLOW_CATALOG_DIRNAME = "flow_catalog"
SINGLE_GOAL_KIND = "single_goal"
SINGLE_GOAL_PHASE = "free"
PROJECT_LOOP_KIND = "project_loop"
MANAGED_FLOW_KIND = "managed_flow"
PROJECT_PHASES = ("plan", "imp", "review")
DONE_PHASE = "done"

LAUNCH_MODE_SINGLE = "single"
LAUNCH_MODE_FLOW = "flow"

EXECUTION_LEVEL_SIMPLE = "simple"
EXECUTION_LEVEL_MEDIUM = "medium"
EXECUTION_LEVEL_HIGH = "high"

FREE_CATALOG_FLOW_ID = "free"
PROJECT_LOOP_CATALOG_FLOW_ID = "project_loop"

EXECUTION_MODE_SIMPLE = "simple"
EXECUTION_MODE_MEDIUM = "medium"
EXECUTION_MODE_COMPLEX = "complex"

SESSION_STRATEGY_SHARED = "shared"
SESSION_STRATEGY_ROLE_BOUND = "role_bound"
SESSION_STRATEGY_PER_ACTIVATION = "per_activation"

PLANNER_ROLE_ID = "planner"
IMPLEMENTER_ROLE_ID = "implementer"
REVIEWER_ROLE_ID = "reviewer"
FIXER_ROLE_ID = "fixer"
REPORTER_ROLE_ID = "reporter"
RESEARCHER_ROLE_ID = "researcher"
DOCTOR_ROLE_ID = "doctor"

ROLE_PACK_CODING_FLOW = "coding_flow"
ROLE_PACK_RESEARCH_FLOW = "research_flow"

EXECUTION_CONTEXT_REPO_BOUND = "repo_bound"
EXECUTION_CONTEXT_ISOLATED = "isolated"

TASK_ARCHETYPE_GENERAL = "general"
TASK_ARCHETYPE_PRODUCT_DELIVERY = "product_delivery"
TASK_ARCHETYPE_RESEARCH_WRITING = "research_writing"
TASK_ARCHETYPE_REPO_REPAIR = "repo_repair"
TASK_ARCHETYPE_REPO_DELIVERY = "repo_delivery"
TASK_ARCHETYPE_PRODUCT_ITERATION = "product_iteration"

PACKET_SIZE_SMALL = "small"
PACKET_SIZE_MEDIUM = "medium"
PACKET_SIZE_LARGE = "large"
CONTROL_PACKET_SMALL = PACKET_SIZE_SMALL
CONTROL_PACKET_MEDIUM = PACKET_SIZE_MEDIUM
CONTROL_PACKET_LARGE = PACKET_SIZE_LARGE

EVIDENCE_LEVEL_LIGHT = "light"
EVIDENCE_LEVEL_STANDARD = "standard"
EVIDENCE_LEVEL_STRICT = "strict"
EVIDENCE_LEVEL_MINIMAL = "minimal"

GATE_CADENCE_FINAL = "final"
GATE_CADENCE_MILESTONE = "milestone"
GATE_CADENCE_PHASE = "phase"
GATE_CADENCE_RISK_BASED = "risk_based"
GATE_CADENCE_STRICT = "strict"

REPO_BINDING_INHERIT = "inherit_workspace"
REPO_BINDING_EXPLICIT = "explicit"
REPO_BINDING_DETACHED = "disabled"
REPO_BINDING_DISABLED = REPO_BINDING_DETACHED

DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS = 12
DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS = 0
DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS = 10
DEFAULT_PROJECT_MAX_RUNTIME_SECONDS = 12 * 60 * 60
DEFAULT_FLOW_LIST_LIMIT = 10
DEFAULT_FLOW_LAUNCHER_RECENT_LIMIT = 5
DEFAULT_FLOW_LAUNCHER_KIND = PROJECT_LOOP_KIND
DEFAULT_LAUNCH_MODE = LAUNCH_MODE_SINGLE
DEFAULT_EXECUTION_LEVEL = EXECUTION_LEVEL_SIMPLE
DEFAULT_CATALOG_FLOW_ID = PROJECT_LOOP_CATALOG_FLOW_ID

FLOW_CODEX_HOME_DIRNAME = "codex_home"
FLOW_CODEX_HOME_SYNC_FILES = ("config.toml", "auth.json", "version.json")

DEFAULT_DISABLED_FLOW_MCP_SERVERS: dict[str, dict[str, str]] = {
    "stripe": {"transport": "streamable_http", "url": "https://mcp.stripe.com"},
    "supabase": {"transport": "streamable_http", "url": "https://mcp.supabase.com/mcp"},
    "vercel": {"transport": "streamable_http", "url": "https://mcp.vercel.com"},
}


def default_execution_context(*, role_pack_id: str = "", workflow_kind: str = "") -> str:
    normalized_role_pack = str(role_pack_id or "").strip().lower()
    normalized_workflow_kind = str(workflow_kind or "").strip().lower()
    if normalized_role_pack == ROLE_PACK_RESEARCH_FLOW:
        return EXECUTION_CONTEXT_ISOLATED
    if normalized_role_pack == ROLE_PACK_CODING_FLOW:
        return EXECUTION_CONTEXT_REPO_BOUND
    if normalized_workflow_kind in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND, SINGLE_GOAL_KIND}:
        return EXECUTION_CONTEXT_REPO_BOUND
    return EXECUTION_CONTEXT_ISOLATED


def normalize_execution_context(raw: str, *, role_pack_id: str = "", workflow_kind: str = "") -> str:
    token = str(raw or "").strip().lower()
    if token in {EXECUTION_CONTEXT_REPO_BOUND, EXECUTION_CONTEXT_ISOLATED}:
        return token
    return default_execution_context(role_pack_id=role_pack_id, workflow_kind=workflow_kind)
