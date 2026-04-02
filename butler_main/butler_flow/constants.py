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

ROLE_PACK_CODING_FLOW = "coding_flow"
ROLE_PACK_RESEARCH_FLOW = "research_flow"

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
