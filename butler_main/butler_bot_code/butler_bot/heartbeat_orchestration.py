from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import time
import uuid

from registry.agent_capability_registry import load_team_catalog, load_team_definition
from execution.agent_team_executor import AgentTeamExecutor
from butler_paths import SKILLS_HOME_REL, prompt_path_text, resolve_butler_root
from services.bootstrap_loader_service import BootstrapLoaderService
from services.prompt_assembly_service import PlannerPromptContext, PromptAssemblyService
from runtime.runtime_router import RuntimeRouter
from services.task_ledger_service import TaskLedgerService
from standards.protocol_registry import get_protocol_registry


HEARTBEAT_MAX_PARALLEL_DEFAULT = 4
HEARTBEAT_MAX_SERIAL_PER_GROUP_DEFAULT = 3
BEAT_RECENT_POOL = "beat"
HEARTBEAT_PLANNER_MIN_INTERVAL_SECONDS = 60
HEARTBEAT_PLANNER_FAILURE_BACKOFF_MAX_SECONDS = 10 * 60
HEARTBEAT_PLANNER_TIMEOUT_CAP_SECONDS = 240
HEARTBEAT_TELL_USER_MARKDOWN_START = "【heartbeat_tell_user_markdown】"
HEARTBEAT_TELL_USER_MARKDOWN_END = "【/heartbeat_tell_user_markdown】"
UPDATE_EXECUTION_KINDS = {"maintenance", "upgrade", "prompt_update", "code_update", "agent_update"}
UPDATE_CAPABILITY_TYPES = {"agent_maintenance", "prompt_maintenance", "code_maintenance", "self_upgrade"}


@dataclass(frozen=True)
class HeartbeatPlanningContext:
    workspace: str
    now_text: str
    soul_text: str
    role_text: str
    tasks_md_text: str
    task_workspace_text: str
    recent_text: str
    local_memory_text: str
    skills_text: str
    subagents_text: str
    teams_text: str
    public_library_text: str
    context_text: str
    max_parallel: int
    max_serial_per_group: int
    allow_autonomous_explore: bool
    fixed_metabolism_branch: bool
    encourage_background_growth: bool

    @property
    def has_actionable_tasks(self) -> bool:
        return bool((self.tasks_md_text or "").strip())


class HeartbeatOrchestrator:
    def __init__(self, manager) -> None:
        self._manager = manager
        self._team_executor = AgentTeamExecutor(manager._run_model_fn)
        self._prompt_assembly_service = PromptAssemblyService()
        self._bootstrap_loader = BootstrapLoaderService()
        self._runtime_router = RuntimeRouter()
        self._protocol_registry = get_protocol_registry()

    def _bootstrap_text(self, session_type: str, workspace: str, max_chars: int = 900) -> str:
        bundle = self._bootstrap_loader.load_for_session(session_type, workspace, max_chars=max_chars)
        return bundle.render()

    def _extract_tell_user_markdown(self, text: str) -> str:
        raw = str(text or "")
        if not raw:
            return ""
        start = raw.find(HEARTBEAT_TELL_USER_MARKDOWN_START)
        if start < 0:
            return ""
        start += len(HEARTBEAT_TELL_USER_MARKDOWN_START)
        end = raw.find(HEARTBEAT_TELL_USER_MARKDOWN_END, start)
        block = raw[start:] if end < 0 else raw[start:end]
        return str(block or "").strip()

    def _resolve_branch_skill_file(self, workspace: str, branch: dict) -> Path | None:
        root = resolve_butler_root(workspace)
        skill_dir = str(branch.get("skill_dir") or "").strip()
        if skill_dir:
            normalized = skill_dir.replace("\\", "/")
            if normalized.startswith("./"):
                normalized = normalized[2:]
            normalized = normalized.lstrip("/")
            candidate = root / Path(normalized)
            skill_file = candidate if candidate.name.lower() == "skill.md" else candidate / "SKILL.md"
            if skill_file.exists():
                return skill_file

        skill_name = str(branch.get("skill_name") or "").strip().lower()
        if skill_name:
            skills_root = root / SKILLS_HOME_REL
            for skill_file in skills_root.rglob("SKILL.md"):
                if skill_file.parent.name.strip().lower() == skill_name:
                    return skill_file
        return None

    def _load_branch_skill_block(self, workspace: str, branch: dict, max_chars: int = 5000) -> tuple[str, str]:
        if not bool(branch.get("requires_skill_read", False)):
            return "", ""

        branch_id = str(branch.get("branch_id") or "branch").strip() or "branch"
        skill_name = str(branch.get("skill_name") or "").strip()
        skill_dir = str(branch.get("skill_dir") or "").strip()
        skill_file = self._resolve_branch_skill_file(workspace, branch)
        if skill_file is None:
            missing_hint = skill_dir or skill_name or branch_id
            return "", f"branch requires skill read but SKILL.md not found: {missing_hint}"

        skill_text = self._manager._load_markdown_excerpt(skill_file, max_chars=max_chars)
        if not str(skill_text or "").strip():
            return "", f"branch requires skill read but SKILL.md is empty: {skill_file}"

        root = resolve_butler_root(workspace)
        try:
            skill_path = prompt_path_text(skill_file.relative_to(root))
        except Exception:
            skill_path = str(skill_file)
        skill_label = skill_name or skill_file.parent.name
        skill_block = (
            "【本分支指定 skill】\n"
            f"skill_name={skill_label}\n"
            f"skill_path={skill_path}\n"
            "以下 SKILL.md 必须先阅读并严格遵守，再执行本分支任务：\n"
            f"{skill_text}\n\n"
        )
        return skill_block, ""

    def allow_autonomous_explore(self, heartbeat_cfg: dict) -> bool:
        raw = (heartbeat_cfg or {}).get("allow_autonomous_explore")
        if raw is None:
            mode = str((heartbeat_cfg or {}).get("autonomous_mode") or "").strip().lower()
            return mode in {"enabled", "autonomous", "on", "true"}
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(raw)

    def resolve_parallel_limit(self, heartbeat_cfg: dict) -> int:
        raw = (heartbeat_cfg or {}).get("max_parallel_branches", HEARTBEAT_MAX_PARALLEL_DEFAULT)
        try:
            value = int(raw)
        except Exception:
            value = HEARTBEAT_MAX_PARALLEL_DEFAULT
        return min(HEARTBEAT_MAX_PARALLEL_DEFAULT, max(1, value))

    def resolve_serial_limit(self, heartbeat_cfg: dict) -> int:
        raw = (heartbeat_cfg or {}).get("max_serial_branches_per_group")
        if raw is None:
            raw = (heartbeat_cfg or {}).get("max_serial_rounds_per_group", HEARTBEAT_MAX_SERIAL_PER_GROUP_DEFAULT)
        try:
            value = int(raw)
        except Exception:
            value = HEARTBEAT_MAX_SERIAL_PER_GROUP_DEFAULT
        return min(HEARTBEAT_MAX_SERIAL_PER_GROUP_DEFAULT, max(1, value))

    def fixed_metabolism_branch_enabled(self, heartbeat_cfg: dict) -> bool:
        raw = (heartbeat_cfg or {}).get("fixed_metabolism_branch")
        if raw is None:
            return True
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(raw)

    def encourage_background_growth(self, heartbeat_cfg: dict) -> bool:
        raw = (heartbeat_cfg or {}).get("encourage_background_growth")
        if raw is None:
            return True
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(raw)

    def resolve_branch_timeout(self, heartbeat_cfg: dict, agent_timeout: int) -> int:
        raw = (heartbeat_cfg or {}).get("branch_timeout")
        if raw is not None:
            try:
                return max(40, min(1200, int(raw)))
            except Exception:
                pass
        return min(max(40, agent_timeout), 1200)

    def resolve_planner_timeout(self, heartbeat_cfg: dict, agent_timeout: int) -> int:
        raw = (heartbeat_cfg or {}).get("planner_timeout")
        if raw is not None:
            try:
                return max(15, min(int(agent_timeout), int(raw), 1200))
            except Exception:
                pass
        every_seconds = None
        try:
            if (heartbeat_cfg or {}).get("every_seconds") is not None:
                every_seconds = int((heartbeat_cfg or {}).get("every_seconds"))
        except Exception:
            every_seconds = None
        if every_seconds is not None and every_seconds > 0:
            return min(max(15, every_seconds * 4), min(int(agent_timeout), HEARTBEAT_PLANNER_TIMEOUT_CAP_SECONDS))
        return min(max(15, agent_timeout), HEARTBEAT_PLANNER_TIMEOUT_CAP_SECONDS)

    def resolve_planner_min_interval(self, heartbeat_cfg: dict) -> int:
        raw = (heartbeat_cfg or {}).get("planner_min_interval_seconds")
        if raw is not None:
            try:
                return max(15, min(3600, int(raw)))
            except Exception:
                pass
        every_seconds = None
        try:
            if (heartbeat_cfg or {}).get("every_seconds") is not None:
                every_seconds = int((heartbeat_cfg or {}).get("every_seconds"))
        except Exception:
            every_seconds = None
        if every_seconds is not None and every_seconds > 0:
            return max(HEARTBEAT_PLANNER_MIN_INTERVAL_SECONDS, every_seconds * 12)
        return HEARTBEAT_PLANNER_MIN_INTERVAL_SECONDS

    def build_planning_context(self, heartbeat_cfg: dict, workspace: str) -> HeartbeatPlanningContext:
        tasks_md_text = self._manager._load_heartbeat_tasks_md(workspace)
        if not str(tasks_md_text or "").strip():
            tasks_md_text = self._manager._render_legacy_heartbeat_tasks_md(workspace)
        recent_text = self._manager._render_unified_heartbeat_recent_context(workspace)
        context_text = self._manager._load_heartbeat_context_excerpt(workspace, heartbeat_cfg)
        local_memory_query = "\n\n".join(
            part for part in [tasks_md_text, context_text, recent_text[:1200]] if str(part or "").strip()
        )
        local_memory_hits = self._manager._render_heartbeat_local_memory_query_hits(workspace, local_memory_query)
        local_memory_baseline = self._manager._render_heartbeat_local_memory_snippet(workspace)
        local_memory_parts: list[str] = []
        if str(local_memory_hits or "").strip():
            local_memory_parts.append(local_memory_hits.strip())
        if str(local_memory_baseline or "").strip() and local_memory_baseline.strip() not in local_memory_parts:
            local_memory_parts.append(local_memory_baseline.strip())
        local_memory_text = "\n\n".join(local_memory_parts).strip()
        return HeartbeatPlanningContext(
            workspace=workspace,
            now_text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            soul_text=self._manager._load_butler_soul_excerpt(workspace),
            role_text=self._manager._load_heartbeat_role_excerpt(workspace),
            tasks_md_text=tasks_md_text,
            task_workspace_text=self._manager._render_heartbeat_task_workspace_context(workspace),
            recent_text=recent_text,
            local_memory_text=local_memory_text,
            skills_text=self._manager._render_available_skills_prompt(workspace),
            subagents_text=self._manager._render_available_subagents_prompt(workspace),
            teams_text=self._manager._render_available_teams_prompt(workspace),
            public_library_text=self._manager._render_public_agent_library_prompt(workspace),
            context_text=context_text,
            max_parallel=self.resolve_parallel_limit(heartbeat_cfg),
            max_serial_per_group=self.resolve_serial_limit(heartbeat_cfg),
            allow_autonomous_explore=self.allow_autonomous_explore(heartbeat_cfg),
            fixed_metabolism_branch=self.fixed_metabolism_branch_enabled(heartbeat_cfg),
            encourage_background_growth=self.encourage_background_growth(heartbeat_cfg),
        )

    def build_status_only_plan(self, reason: str, user_message: str) -> dict:
        return {
            "chosen_mode": "status",
            "execution_mode": "defer",
            "reason": str(reason or "").strip(),
            "user_message": str(user_message or "").strip(),
            "tell_user": "",
            "tell_user_candidate": "",
            "tell_user_reason": "",
            "tell_user_type": "",
            "tell_user_priority": 0,
            "execute_prompt": "",
            "selected_task_ids": [],
            "deferred_task_ids": [],
            "defer_reason": "",
            "summary_prompt": "",
            "task_groups": [],
            "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
        }

    def _planner_failure_backoff_seconds(self, heartbeat_cfg: dict) -> int:
        min_interval = self.resolve_planner_min_interval(heartbeat_cfg)
        failure_count = max(1, int(getattr(self._manager, "_heartbeat_planner_failure_count", 0) or 0))
        if failure_count <= 1:
            return 0
        scaled = min_interval * min(failure_count - 1, 3)
        return min(HEARTBEAT_PLANNER_FAILURE_BACKOFF_MAX_SECONDS, max(0, scaled))

    def _read_planner_state(self, workspace: str) -> dict:
        state = self._manager._load_planner_state(workspace)
        failure_count = max(0, int(state.get("failure_count") or 0))
        backoff_until = max(0.0, float(state.get("backoff_until_epoch") or 0.0))
        self._manager._heartbeat_planner_failure_count = failure_count
        self._manager._heartbeat_planner_backoff_until = backoff_until
        return {"failure_count": failure_count, "backoff_until_epoch": backoff_until}

    def _write_planner_state(self, workspace: str, failure_count: int, backoff_until_epoch: float) -> None:
        self._manager._save_planner_state(workspace, failure_count, backoff_until_epoch)

    def build_planner_backoff_plan(self, heartbeat_cfg: dict, context: HeartbeatPlanningContext, workspace: str) -> dict | None:
        if bool((heartbeat_cfg or {}).get("force_model_planner")):
            return None
        planner_state = self._read_planner_state(workspace)
        backoff_until = float(planner_state.get("backoff_until_epoch") or 0.0)
        if backoff_until <= 0:
            return None
        remaining = max(0, int(round(backoff_until - time.time())))
        if remaining <= 0:
            return None
        return self._build_local_fallback_task_plan(
            heartbeat_cfg,
            context,
            workspace,
            reason_prefix=f"规划器冷却中，等待 {remaining} 秒后再尝试主动规划；本轮改用本地兜底任务",
        )

    def _build_short_task_branch(self, task: dict) -> dict:
        task_id = str(task.get("task_id") or "fallback-short").strip() or "fallback-short"
        title = str(task.get("title") or task.get("detail") or "执行本地短期任务").strip() or "执行本地短期任务"
        detail = str(task.get("detail") or title).strip() or title
        priority = str(task.get("priority") or "medium").strip() or "medium"
        prompt = (
            "role=heartbeat-executor-agent\n"
            "output_dir=./工作区/manager\n"
            "你作为 heartbeat-executor-agent，执行一条 heartbeat 本地兜底短期任务。\n"
            f"task_id={task_id}\n"
            f"title={title}\n"
            f"priority={priority}\n"
            f"detail={detail}\n"
            "要求：高效率、高质量、尽快推进到可见进展；若能自然收口就直接收口，若不能则至少产出明确的下一步与结果记录。\n"
            "如果需要修改工作区文档或索引，优先做小步、低风险、可解释的改动。"
        )
        return {
            "branch_id": f"short-{task_id}",
            "agent_role": "heartbeat-executor-agent",
            "execution_kind": "task",
            "capability_id": "",
            "capability_type": "",
            "skill_name": "",
            "skill_dir": "",
            "requires_skill_read": False,
            "prompt": prompt,
            "selected_task_ids": [task_id],
            "complete_task_ids": [],
            "defer_task_ids": [],
            "touch_long_task_ids": [],
            "depends_on": [],
            "can_run_parallel": True,
            "expected_output": "产出一条可见进展，并在能完成时收口该短期任务。",
        }

    def _build_long_task_branch(self, task: dict) -> dict:
        task_id = str(task.get("task_id") or "fallback-long").strip() or "fallback-long"
        title = str(task.get("title") or task.get("detail") or "执行本地长期任务").strip() or "执行本地长期任务"
        detail = str(task.get("detail") or title).strip() or title
        prompt = (
            "role=heartbeat-executor-agent\n"
            "output_dir=./工作区/manager\n"
            "你作为 heartbeat-executor-agent，执行一条 heartbeat 本地兜底长期任务。\n"
            f"task_id={task_id}\n"
            f"title={title}\n"
            f"detail={detail}\n"
            "要求：本轮只推进一步清晰、低风险、可解释的阶段性进展；不要把长期任务无限续命。\n"
            "若本轮已达到阶段结束点，应在结果中明确说明可以收口或进入下一阶段。"
        )
        return {
            "branch_id": f"long-{task_id}",
            "agent_role": "heartbeat-executor-agent",
            "execution_kind": "task",
            "capability_id": "",
            "capability_type": "",
            "skill_name": "",
            "skill_dir": "",
            "requires_skill_read": False,
            "prompt": prompt,
            "selected_task_ids": [],
            "complete_task_ids": [],
            "defer_task_ids": [],
            "touch_long_task_ids": [task_id],
            "depends_on": [],
            "can_run_parallel": True,
            "expected_output": "推进一条长期任务的阶段性进展，并刷新其最近结果。",
        }

    def _build_metabolism_branch(self) -> dict:
        prompt = (
            "role=heartbeat-executor-agent\n"
            "output_dir=./工作区/06_governance_ops/metabolism\n"
            "你作为 heartbeat-executor-agent，执行固定的 heartbeat 新陈代谢并行支路。\n"
            "目标：只做当前 still-valid 的轻量治理，优先核对目录 README、索引、任务板和最近升级计划是否过时。\n"
            "允许的小步动作：更新 README、补目录索引、归档过时说明、把旧任务标为 done/deferred/obsolete。\n"
            "禁止继续维护 guardian 旧巡检、self_mind 桥接配额、已经废弃的心跳配额实验等过时任务。\n"
            "不要做大规模清扫，不要用旧文档压过当前运行事实与最近改动。\n"
            "如果本轮未发现需要处理的项，也要返回一句明确结论，说明本轮代谢检查通过。"
        )
        return {
            "branch_id": "heartbeat-metabolism",
            "agent_role": "heartbeat-executor-agent",
            "execution_kind": "metabolism",
            "capability_id": "",
            "capability_type": "",
            "skill_name": "",
            "skill_dir": "",
            "requires_skill_read": False,
            "prompt": prompt,
            "selected_task_ids": [],
            "complete_task_ids": [],
            "defer_task_ids": [],
            "touch_long_task_ids": [],
            "depends_on": [],
            "can_run_parallel": True,
            "expected_output": "输出一条轻量代谢结论，必要时补一小步治理或复核记录。",
        }

    def _build_background_growth_branch(self) -> dict:
        prompt = (
            "role=heartbeat-executor-agent\n"
            "output_dir=./工作区/agent_upgrade\n"
            "你作为 heartbeat-executor-agent，执行一条受控的低风险自我提升支路。\n"
            "前提：本轮没有更高优先级的显式任务需要占满全部精力。\n"
            "从以下方向中选一个能在单轮内形成可见进展的小步：\n"
            "1. 阅读最近与心跳、记忆、智能、守护相关的项目文档，并补一条自我认知或升级建议；\n"
            "2. 扫描可复用 skills，找一个适合当前系统的能力做学习/整理；\n"
            "3. 如运行环境允许，可做一次轻量公开能力检索：优先官方文档、可信 GitHub 仓库、公开技能库；\n"
            "4. 若真发现关键能力缺口，按‘检索公开方案 -> 安全审阅 -> 形成 skill/MCP 落地稿 -> 回到原任务重试’推进，不要只停在调研汇报。\n"
            "要求：优先高效率、高质量、可收口；不要压过显式任务，不要把本轮拖成无限探索。"
        )
        return {
            "branch_id": "heartbeat-background-growth",
            "agent_role": "heartbeat-executor-agent",
            "execution_kind": "growth",
            "capability_id": "",
            "capability_type": "",
            "skill_name": "",
            "skill_dir": "",
            "requires_skill_read": False,
            "prompt": prompt,
            "selected_task_ids": [],
            "complete_task_ids": [],
            "defer_task_ids": [],
            "touch_long_task_ids": [],
            "depends_on": [],
            "can_run_parallel": True,
            "expected_output": "产出一条低风险自我提升进展或明确的学习结论。",
        }

    def _has_branch(self, groups: list[dict], branch_id: str) -> bool:
        target = str(branch_id or "").strip()
        if not target:
            return False
        for group in groups or []:
            branches = group.get("branches") if isinstance(group, dict) else []
            for branch in branches or []:
                if str((branch or {}).get("branch_id") or "").strip() == target:
                    return True
        return False

    def _ensure_fixed_branches(self, plan: dict, context: HeartbeatPlanningContext) -> dict:
        task_groups = plan.get("task_groups") if isinstance(plan.get("task_groups"), list) else []
        normalized_groups = [group for group in task_groups if isinstance(group, dict)]
        if not normalized_groups:
            normalized_groups = [{"group_id": "heartbeat-fixed", "branches": []}]

        first_group = normalized_groups[0]
        first_group.setdefault("group_id", "heartbeat-fixed")
        branches = first_group.get("branches") if isinstance(first_group.get("branches"), list) else []
        branches = [branch for branch in branches if isinstance(branch, dict)]

        if context.fixed_metabolism_branch and not self._has_branch(normalized_groups, "heartbeat-metabolism"):
            branches.insert(0, self._build_metabolism_branch())

        chosen_mode = str(plan.get("chosen_mode") or "").strip().lower()
        has_explicit_tasks = bool(self.sanitize_id_list(plan.get("selected_task_ids"), limit=10))
        if (
            context.encourage_background_growth
            and chosen_mode == "status"
            and not has_explicit_tasks
            and not self._has_branch(normalized_groups, "heartbeat-background-growth")
        ):
            branches.append(self._build_background_growth_branch())

        first_group["branches"] = branches[: context.max_parallel]
        normalized_groups[0] = first_group
        plan["task_groups"] = normalized_groups

        if first_group.get("branches"):
            if chosen_mode == "status":
                plan["chosen_mode"] = "long_task"
                if self._has_branch(normalized_groups, "heartbeat-background-growth"):
                    plan["reason"] = (str(plan.get("reason") or "").strip() + "；本轮执行固定新陈代谢，并在空闲时推进一条受控自我提升小步").strip("；")
                    plan["user_message"] = str(plan.get("user_message") or "").strip() or f"本轮没有更高优先级显式任务，我会固定做一轮新陈代谢检查，并顺手推进一条低风险自我提升小步。时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    plan["reason"] = (str(plan.get("reason") or "").strip() + "；本轮执行固定新陈代谢支路").strip("；")
                    plan["user_message"] = str(plan.get("user_message") or "").strip() or f"本轮没有更高优先级显式任务，我会先做固定的新陈代谢检查。时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            plan["execution_mode"] = "parallel" if len(first_group.get("branches") or []) >= 2 else "single"
        return plan

    def _build_local_fallback_task_plan(
        self,
        heartbeat_cfg: dict,
        context: HeartbeatPlanningContext,
        workspace: str,
        reason_prefix: str,
    ) -> dict:
        short_tasks = self._manager._load_pending_short_heartbeat_tasks(workspace)
        if short_tasks:
            task = short_tasks[0]
            plan = {
                "chosen_mode": "short_task",
                "execution_mode": "single",
                "reason": f"{reason_prefix}，采用本地兜底策略恢复一条短期任务。",
                "user_message": f"规划器未稳定返回，已切换本地兜底。先处理一条短期任务：{str(task.get('title') or task.get('detail') or '未命名任务').strip()}。",
                "tell_user": "",
                "tell_user_candidate": "",
                "tell_user_reason": "",
                "tell_user_type": "",
                "tell_user_priority": 0,
                "execute_prompt": "",
                "selected_task_ids": self.sanitize_id_list([task.get("task_id")], limit=10),
                "deferred_task_ids": [],
                "defer_reason": "",
                "summary_prompt": "",
                "task_groups": [{"group_id": "fallback-short", "branches": [self._build_short_task_branch(task)]}],
                "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
            }
            return self._ensure_fixed_branches(plan, context)

        long_tasks = self._manager._load_due_long_heartbeat_tasks(workspace)
        if long_tasks:
            task = long_tasks[0]
            plan = {
                "chosen_mode": "long_task",
                "execution_mode": "single",
                "reason": f"{reason_prefix}，采用本地兜底策略恢复一条到期长期任务。",
                "user_message": f"规划器未稳定返回，已切换本地兜底。先处理一条到期长期任务：{str(task.get('title') or task.get('detail') or '未命名任务').strip()}。",
                "tell_user": "",
                "tell_user_candidate": "",
                "tell_user_reason": "",
                "tell_user_type": "",
                "tell_user_priority": 0,
                "execute_prompt": "",
                "selected_task_ids": [],
                "deferred_task_ids": [],
                "defer_reason": "",
                "summary_prompt": "",
                "task_groups": [{"group_id": "fallback-long", "branches": [self._build_long_task_branch(task)]}],
                "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": self.sanitize_id_list([task.get("task_id")], limit=10)},
            }
            return self._ensure_fixed_branches(plan, context)

        return self._ensure_fixed_branches(self.build_status_only_plan(reason_prefix, f"本轮没有更高优先级显式任务，我会先执行固定新陈代谢支路。时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"), context)

    def sanitize_id_list(self, values: list | tuple | set | None, limit: int = 20) -> list[str]:
        items = []
        for value in values or []:
            text = str(value).strip()
            if text:
                items.append(text)
        return items[:limit]

    def human_preview_text(self, text: str, limit: int = 140) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if not compact:
            return ""
        if len(compact) <= limit:
            return compact

        sentence_marks = "。！？!?；;"
        best_idx = -1
        for idx, ch in enumerate(compact[:limit]):
            if ch in sentence_marks:
                best_idx = idx
        if best_idx >= max(24, limit // 3):
            return compact[: best_idx + 1].strip()

        space_idx = compact.rfind(" ", 0, limit - 1)
        if space_idx >= max(24, limit // 3):
            return compact[:space_idx].rstrip() + "…"
        return compact[: limit - 1].rstrip() + "…"

    def truncate_message_for_send(self, text: str, limit: int = 4000) -> str:
        compact = str(text or "").strip()
        if len(compact) <= limit:
            return compact
        suffix = "\n\n（消息已截断，完整分支详情请查看最近的心跳执行快照。）"
        head_limit = max(0, limit - len(suffix) - 1)
        trimmed = self.human_preview_text(compact[:head_limit], limit=head_limit) if head_limit else ""
        if not trimmed:
            trimmed = compact[:head_limit].rstrip()
        return (trimmed.rstrip("…") + "…" + suffix).strip()

    def normalize_plan_task_groups(self, plan: dict, max_parallel: int) -> list[dict]:
        groups = plan.get("task_groups") if isinstance(plan.get("task_groups"), list) else []
        normalized_groups: list[dict] = []
        max_groups = 4

        for idx, group in enumerate(groups[:max_groups]):
            if not isinstance(group, dict):
                continue
            branches = group.get("branches") if isinstance(group.get("branches"), list) else []
            normalized_branches: list[dict] = []
            for branch_index, branch in enumerate(branches):
                if not isinstance(branch, dict):
                    continue
                prompt = str(branch.get("prompt") or "").strip()
                if not prompt:
                    continue
                branch_id = str(branch.get("branch_id") or f"g{idx+1}-b{branch_index+1}").strip() or f"g{idx+1}-b{branch_index+1}"
                normalized_branches.append(
                    {
                        "branch_id": branch_id,
                        "agent_role": str(branch.get("agent_role") or "executor").strip() or "executor",
                        "team_id": str(branch.get("team_id") or "").strip(),
                        "process_role": str(branch.get("process_role") or "").strip() or "executor",
                        "execution_kind": str(branch.get("execution_kind") or "task").strip() or "task",
                        "capability_id": str(branch.get("capability_id") or "").strip(),
                        "capability_type": str(branch.get("capability_type") or "").strip(),
                        "skill_name": str(branch.get("skill_name") or "").strip(),
                        "skill_dir": str(branch.get("skill_dir") or "").strip(),
                        "requires_skill_read": bool(branch.get("requires_skill_read", False)),
                        "runtime_profile": dict(branch.get("runtime_profile") or {}) if isinstance(branch.get("runtime_profile"), dict) else {},
                        "prompt": prompt,
                        "selected_task_ids": self.sanitize_id_list(branch.get("selected_task_ids"), limit=10),
                        "complete_task_ids": self.sanitize_id_list(branch.get("complete_task_ids"), limit=10),
                        "defer_task_ids": self.sanitize_id_list(branch.get("defer_task_ids"), limit=10),
                        "touch_long_task_ids": self.sanitize_id_list(branch.get("touch_long_task_ids"), limit=10),
                        "depends_on": self.sanitize_id_list(branch.get("depends_on"), limit=5),
                        "can_run_parallel": bool(branch.get("can_run_parallel", True)),
                        "expected_output": str(branch.get("expected_output") or "").strip(),
                    }
                )
            if normalized_branches:
                normalized_groups.append(
                    {
                        "group_id": str(group.get("group_id") or f"group-{idx+1}").strip() or f"group-{idx+1}",
                        "branches": normalized_branches[:max_parallel],
                    }
                )

        if not normalized_groups:
            legacy_prompt = str(plan.get("execute_prompt") or "").strip()
            if legacy_prompt:
                normalized_groups.append(
                    {
                        "group_id": "legacy-single",
                        "branches": [
                            {
                                "branch_id": "legacy-1",
                                "agent_role": "executor",
                                "team_id": "",
                                "process_role": "executor",
                                "execution_kind": "task",
                                "capability_id": "",
                                "capability_type": "",
                                "skill_name": "",
                                "skill_dir": "",
                                "requires_skill_read": False,
                                "runtime_profile": {},
                                "prompt": legacy_prompt,
                                "selected_task_ids": self.sanitize_id_list(plan.get("selected_task_ids"), limit=10),
                                "complete_task_ids": [],
                                "defer_task_ids": [],
                                "touch_long_task_ids": [],
                                "depends_on": [],
                                "can_run_parallel": False,
                                "expected_output": "",
                            }
                        ],
                    }
                )
        return normalized_groups

    def _build_executor_protocol_block(self) -> str:
        rendered = self._protocol_registry.render_prompt_block("heartbeat_executor", heading="heartbeat 执行协议")
        return rendered or ""

    def _build_update_agent_protocol_block(self) -> str:
        rendered = self._protocol_registry.render_prompt_block("update_agent_maintenance", heading="统一维护入口协议")
        return rendered or ""

    def _build_task_collaboration_protocol_block(self) -> str:
        rendered = self._protocol_registry.render_prompt_block("task_collaboration", heading="任务协作协议")
        return rendered or ""

    def _build_self_update_protocol_block(self) -> str:
        rendered = self._protocol_registry.render_prompt_block("self_update", heading="自我更新协作协议")
        return rendered or ""

    def _resolve_branch_agent_role(self, branch: dict) -> str:
        role_name = str(branch.get("agent_role") or "executor").strip() or "executor"
        execution_kind = str(branch.get("execution_kind") or "").strip().lower()
        capability_type = str(branch.get("capability_type") or "").strip().lower()
        if role_name in {"executor", "heartbeat-executor-agent"} and (
            execution_kind in UPDATE_EXECUTION_KINDS or capability_type in UPDATE_CAPABILITY_TYPES
        ):
            return "update-agent"
        return role_name

    def _resolve_branch_process_role(self, branch: dict) -> str:
        process_role = str(branch.get("process_role") or "").strip().lower()
        if process_role:
            return process_role
        execution_kind = str(branch.get("execution_kind") or "").strip().lower()
        if execution_kind in {"review", "acceptance"}:
            return "acceptance"
        if execution_kind in {"maintenance", "test", "evaluate"}:
            return "test"
        return "executor"

    def _build_process_role_block(self, process_role: str) -> str:
        role = str(process_role or "executor").strip() or "executor"
        return (
            "【流程角色】\n"
            f"- 当前阶段={role}\n"
            "本分支回执至少包含：阶段目标、结果、证据、风险、下一步。\n"
            "如果当前阶段不是执行，而是测试/评估/验收，请显式判断是否通过、未通过原因、返工建议。\n\n"
        )

    def _branch_result_base(self, branch: dict, branch_id: str, role_name: str, team_id: str, duration: float) -> dict:
        return {
            "branch_id": branch_id,
            "agent_role": role_name,
            "team_id": team_id,
            "process_role": self._resolve_branch_process_role(branch),
            "capability_id": str(branch.get("capability_id") or "").strip(),
            "capability_type": str(branch.get("capability_type") or "").strip(),
            "skill_name": str(branch.get("skill_name") or "").strip(),
            "skill_dir": str(branch.get("skill_dir") or "").strip(),
            "requires_skill_read": bool(branch.get("requires_skill_read", False)),
            "runtime_profile": dict(branch.get("runtime_profile") or {}) if isinstance(branch.get("runtime_profile"), dict) else {},
            "duration_seconds": round(duration, 2),
            "selected_task_ids": self.sanitize_id_list(branch.get("selected_task_ids"), limit=10),
            "complete_task_ids": self.sanitize_id_list(branch.get("complete_task_ids"), limit=10),
            "defer_task_ids": self.sanitize_id_list(branch.get("defer_task_ids"), limit=10),
            "touch_long_task_ids": self.sanitize_id_list(branch.get("touch_long_task_ids"), limit=10),
        }

    def run_branch(self, branch: dict, workspace: str, branch_timeout: int, model: str) -> dict:
        started = time.time()
        role_name = self._resolve_branch_agent_role(branch)
        process_role = self._resolve_branch_process_role(branch)
        branch_id = str(branch.get("branch_id") or "").strip() or "branch"
        team_id = str(branch.get("team_id") or "").strip()
        cfg = self._manager._config_provider() if callable(getattr(self._manager, "_config_provider", None)) else {}
        routing = self._runtime_router.route_branch(workspace, branch, model, cfg if isinstance(cfg, dict) else {})
        effective_model = str((routing.runtime_request or {}).get("model") or model).strip() or model
        branch["runtime_profile"] = dict(routing.runtime_profile)
        if team_id:
            definition = load_team_definition(workspace, team_id)
            if definition is None:
                available_team_ids = [item.team_id for item in load_team_catalog(workspace) if str(item.team_id).strip()]
                available_text = ", ".join(available_team_ids[:8]) if available_team_ids else "(none)"
                print(
                    f"[heartbeat-branch] team fallback | branch_id={branch_id} | team_id={team_id} | role={role_name} | registered={available_text}",
                    flush=True,
                )
                branch = dict(branch or {})
                branch.pop("team_id", None)
                branch.setdefault("planner_note", "")
                branch["planner_note"] = (
                    str(branch.get("planner_note") or "").strip() + "\n"
                    + f"[runtime] unregistered team_id={team_id}; fallback to role execution={role_name}; registered teams={available_text}"
                ).strip()
            else:
                with self._manager.runtime_request_scope(routing.runtime_request):
                    result = self._team_executor.execute_team(team_id, str(branch.get("prompt") or "").strip(), workspace, branch_timeout, effective_model)
                duration = time.time() - started
                payload = self._branch_result_base(branch, branch_id, role_name, team_id, duration)
                payload.update(
                    {
                        "ok": bool(result.get("ok")),
                        "output": str(result.get("output") or "").strip(),
                        "tell_user_markdown": self._extract_tell_user_markdown(str(result.get("output") or "")),
                        "error": str(result.get("error") or "").strip(),
                    }
                )
                return payload
        skill_block, skill_error = self._load_branch_skill_block(workspace, branch)
        if skill_error:
            duration = time.time() - started
            payload = self._branch_result_base(branch, branch_id, role_name, team_id, duration)
            payload.update({"ok": False, "output": "", "error": skill_error})
            return payload

        role_excerpt = self._manager._load_subagent_role_excerpt(workspace, role_name)
        bootstrap_text = self._bootstrap_text("heartbeat_executor", workspace, max_chars=700)
        prompt_parts = [self._manager._load_heartbeat_workspace_hint(workspace)]
        if bootstrap_text:
            prompt_parts.append(f"【Bootstrap】\n{bootstrap_text}\n\n")
        if role_excerpt:
            prompt_parts.append(f"【执行角色】\n{role_excerpt}\n\n")
        prompt_parts.append(self._build_process_role_block(process_role))
        if skill_block:
            prompt_parts.append(skill_block)
        prompt_parts.append(self._build_task_collaboration_protocol_block())
        if role_name == "update-agent":
            prompt_parts.append(self._build_update_agent_protocol_block())
            prompt_parts.append(self._build_self_update_protocol_block())
        prompt_parts.append(self._build_executor_protocol_block())
        prompt_parts.append(
            "【运行时路由】\n"
            f"- runtime_profile={json.dumps(routing.runtime_profile, ensure_ascii=False)}\n"
            f"- manager_note={routing.manager_note}\n\n"
        )
        prompt_parts.append(
            "【heartbeat 回执约定】完成任务后，若本分支里有值得发给用户同步的内容，请在输出末尾追加一个 Markdown 区块：\n"
            f"{HEARTBEAT_TELL_USER_MARKDOWN_START}\n"
            "## 本分支可同步\n"
            "- 用 1-4 行清楚写出对用户真正有价值的结果 / 风险 / 下一步。\n"
            f"{HEARTBEAT_TELL_USER_MARKDOWN_END}\n"
            "汇总时会自动加上「分支 id + 角色」标签，你只需写清本分支的可同步要点即可；不要把完整长报告原样塞进去。\n\n"
        )
        prompt_parts.append(str(branch.get("prompt") or "").strip())
        prompt = "".join(prompt_parts).strip()
        output = ""
        ok = False
        error_text = ""
        try:
            with self._manager.runtime_request_scope(routing.runtime_request):
                output, ok = self._manager._run_model_fn(prompt, workspace, branch_timeout, effective_model)
        except Exception as exc:
            error_text = str(exc)
            ok = False
            output = ""
        duration = time.time() - started
        out_text = str(output or "").strip()
        payload = self._branch_result_base(branch, branch_id, role_name, team_id, duration)
        payload.update(
            {
                "ok": bool(ok and out_text),
                "output": out_text,
                "tell_user_markdown": self._extract_tell_user_markdown(out_text),
                "error": error_text,
            }
        )
        return payload

    def render_branch_results_for_user(self, plan: dict, branch_results: list[dict]) -> str:
        if not branch_results:
            return ""
        parallel_count = len([item for item in branch_results if str(item.get("run_mode") or "") == "parallel"])
        serial_count = len([item for item in branch_results if str(item.get("run_mode") or "") != "parallel"])
        success = [item for item in branch_results if bool(item.get("ok"))]
        failed = [item for item in branch_results if not bool(item.get("ok"))]
        lines = [
            "## 本轮心跳",
            f"- 模式：{str(plan.get('chosen_mode') or 'status').strip() or 'status'}",
            f"- 并行：并行 {parallel_count} 路，串行 {serial_count} 路",
            f"- 结果：成功 {len(success)}，失败 {len(failed)}",
        ]

        rendered_blocks = []
        for item in branch_results:
            block = str(item.get("tell_user_markdown") or "").strip()
            if block:
                branch_id = str(item.get("branch_id") or "branch").strip() or "branch"
                agent_role = str(item.get("agent_role") or "").strip() or "执行分支"
                # 去掉块内自带的「## 本分支可同步」，避免多分支时重复且无法区分
                normalized = block
                if normalized.startswith("## 本分支可同步"):
                    normalized = normalized[len("## 本分支可同步"):].lstrip("\n\r")
                elif normalized.startswith("## 值得同步"):
                    normalized = normalized[len("## 值得同步"):].lstrip("\n\r")
                # 每块前加「分支标识」+「角色/能力」，方便用户看出是哪路在说什么
                label = f"【{branch_id}】{agent_role}"
                rendered_blocks.append(f"### {label}\n{normalized}")
        if rendered_blocks:
            lines.extend(["", "## 值得同步"])
            lines.extend(rendered_blocks[:HEARTBEAT_MAX_PARALLEL_DEFAULT])
        else:
            lines.extend(["", "## 执行摘要"])
            for item in branch_results[:HEARTBEAT_MAX_PARALLEL_DEFAULT]:
                branch_id = str(item.get("branch_id") or "branch")
                if bool(item.get("ok")):
                    brief = self.human_preview_text(str(item.get("output") or ""), limit=180)
                    lines.append(f"- {branch_id}：{brief or '已执行。'}")
                else:
                    err = self.human_preview_text(str(item.get("error") or item.get("output") or ""), limit=180)
                    lines.append(f"- {branch_id}：未完成。{err or '执行失败或无输出。'}")

        if failed:
            lines.extend(["", "## 需关注"])
            for item in failed[:HEARTBEAT_MAX_SERIAL_PER_GROUP_DEFAULT]:
                branch_id = str(item.get("branch_id") or "branch")
                err = self.human_preview_text(str(item.get("error") or item.get("output") or ""), limit=180)
                lines.append(f"- {branch_id}：{err or '执行失败或无输出。'}")

        deferred = self.sanitize_id_list(plan.get("deferred_task_ids"), limit=10)
        if deferred:
            defer_reason = str(plan.get("defer_reason") or "").strip()
            lines.extend(["", "## 延后"])
            lines.append(f"- 延后任务数：{len(deferred)}")
            if defer_reason:
                lines.append(f"- 原因：{defer_reason}")
        return "\n".join(lines).strip()

    def summarize_branch_results(self, plan: dict, branch_results: list[dict]) -> str:
        return self.render_branch_results_for_user(plan, branch_results)

    def execute_plan(
        self,
        plan: dict,
        workspace: str,
        timeout: int,
        model: str,
        max_parallel: int,
        branch_timeout: int,
    ) -> tuple[str, list[dict]]:
        task_groups = self.normalize_plan_task_groups(plan, max_parallel=max_parallel)
        branch_results: list[dict] = []
        if not task_groups:
            return "", branch_results

        for group in task_groups:
            branches = group.get("branches") if isinstance(group.get("branches"), list) else []
            if not branches:
                continue
            parallel_ready = [
                branch for branch in branches
                if isinstance(branch, dict)
                and bool(branch.get("can_run_parallel", True))
                and not (branch.get("depends_on") or [])
            ]
            serial_queue = [branch for branch in branches if isinstance(branch, dict) and branch not in parallel_ready]

            if len(parallel_ready) <= 1:
                serial_queue = branches
                parallel_ready = []

            if parallel_ready:
                with ThreadPoolExecutor(max_workers=min(max_parallel, len(parallel_ready))) as pool:
                    future_map = {}
                    limited_parallel = parallel_ready[:max_parallel]
                    for idx, branch in enumerate(limited_parallel):
                        future = pool.submit(self.run_branch, branch, workspace, branch_timeout, model)
                        future_map[future] = branch
                        if idx + 1 < len(limited_parallel):
                            time.sleep(0.5)
                    for future in as_completed(future_map):
                        try:
                            item = future.result()
                            if isinstance(item, dict):
                                item["run_mode"] = "parallel"
                            branch_results.append(item)
                        except Exception as exc:
                            branch = future_map[future]
                            branch_results.append(
                                {
                                    "branch_id": str((branch or {}).get("branch_id") or "branch"),
                                    "ok": False,
                                    "output": "",
                                    "error": str(exc),
                                    "duration_seconds": 0,
                                    "run_mode": "parallel",
                                    "selected_task_ids": self.sanitize_id_list((branch or {}).get("selected_task_ids"), limit=10),
                                    "complete_task_ids": self.sanitize_id_list((branch or {}).get("complete_task_ids"), limit=10),
                                    "defer_task_ids": self.sanitize_id_list((branch or {}).get("defer_task_ids"), limit=10),
                                    "touch_long_task_ids": self.sanitize_id_list((branch or {}).get("touch_long_task_ids"), limit=10),
                                }
                            )

            if serial_queue:
                for branch in serial_queue[:HEARTBEAT_MAX_SERIAL_PER_GROUP_DEFAULT]:
                    item = self.run_branch(branch, workspace, branch_timeout, model)
                    item["run_mode"] = "serial"
                    branch_results.append(item)

        execution_summary = self.summarize_branch_results(plan, branch_results)
        return execution_summary, branch_results

    def persist_snapshot_to_recent(
        self,
        workspace: str,
        plan: dict,
        branch_results: list[dict],
        execution_result: str,
        max_parallel: int,
    ) -> None:
        try:
            parallel_count = len([item for item in (branch_results or []) if str(item.get("run_mode") or "") == "parallel"])
            branch_count = len(branch_results or [])
            parallel_used = parallel_count >= 2
            deferred_ids = self.sanitize_id_list(plan.get("deferred_task_ids"), limit=10)
            with self._manager._memory_lock:
                entries = self._manager._load_recent_entries(workspace, pool=BEAT_RECENT_POOL)
                consolidated = self._manager._subconscious_service.consolidate_heartbeat_run(
                    plan=plan,
                    branch_results=branch_results,
                    execution_result=execution_result,
                    existing_entries=entries,
                    max_parallel=max_parallel,
                )
                entry = consolidated["primary_entry"]
                entries.append(entry)
                entries.extend(consolidated["companion_entries"])
                lt = entry.get("long_term_candidate") if isinstance(entry.get("long_term_candidate"), dict) else {}
                if lt.get("should_write") and lt.get("summary") and self._manager._govern_memory_write(
                    target_path="./butler_main/butler_bot_agent/agents/local_memory",
                    action_type="memory-write",
                    summary=str(lt.get("title") or "心跳阶段结论"),
                ):
                    action = self._manager._upsert_local_memory(
                        workspace,
                        str(lt.get("title") or "心跳阶段结论"),
                        str(lt.get("summary") or ""),
                        [str(x) for x in (lt.get("keywords") or [])],
                        source_type="heartbeat",
                        source_reason="planner-execution-closure",
                        source_topic=str(entry.get("topic") or "心跳规划与执行"),
                        source_entry=entry,
                    )
                    if action in {"write-new", "append-existing", "append-similar", "duplicate-skip"}:
                        self._manager._mark_recent_entry_local_promoted(entry, action, source="heartbeat")
                entries, _ = self._manager._compact_recent_entries_if_needed(entries, workspace, 0, "", reason="heartbeat-snapshot", pool=BEAT_RECENT_POOL)
                self._manager._save_recent_entries(workspace, entries, pool=BEAT_RECENT_POOL)
            print(
                f"[heartbeat-snapshot] parallel={'yes' if parallel_used else 'no'} | branches={branch_count} | deferred={len(deferred_ids)}",
                flush=True,
            )
        except Exception as exc:
            print(f"[heartbeat-snapshot] 持久化失败: {exc}", flush=True)

    def build_planning_prompt(self, cfg: dict, heartbeat_cfg: dict, workspace: str) -> str:
        context = self.build_planning_context(heartbeat_cfg, workspace)
        bootstrap_text = self._bootstrap_text("heartbeat_planner", workspace)
        template = self._manager._load_heartbeat_prompt_template(workspace)
        if "{json_schema}" not in template:
            template = template.rstrip() + "\n\n## JSON Schema\n\n{json_schema}\n"
        # 兼容历史模板里把“长期记忆候选”写成字面量占位符的旧写法。
        if "{local_memory_text}" not in template and "{长期记忆候选}" in template:
            template = template.replace("{长期记忆候选}", "{长期记忆候选}\n\n{local_memory_text}")
        if "{tasks_context}" not in template and "{short_tasks_json}" not in template and "{long_tasks_json}" not in template:
            template = template.rstrip() + "\n\n## 任务与上下文（heartbeat_tasks.md）\n\n{tasks_context}\n"
        if "{context_text}" not in template and "{agent_prompt}" not in template:
            template = template.rstrip() + "\n\n## 额外上下文\n\n{context_text}\n"
        json_schema = (
            '{"chosen_mode":"short_task|long_task|explore|status","execution_mode":"single|parallel|defer",'
            '"reason":"","user_message":"","tell_user":"","tell_user_candidate":"","tell_user_reason":"","tell_user_type":"result_share|risk_share|thought_share|light_chat|growth_share","tell_user_priority":0,"execute_prompt":"","selected_task_ids":[],"deferred_task_ids":[],'
            '"defer_reason":"","summary_prompt":"","task_groups":[{"group_id":"","branches":[{"branch_id":"",'
            '"agent_role":"","team_id":"","process_role":"executor|test|acceptance|manager","execution_kind":"task","capability_id":"","capability_type":"","skill_name":"","skill_dir":"","requires_skill_read":false,'
            '"runtime_profile":{"cli":"cursor|codex","model":"auto|gpt-5|gpt-5.2","reasoning_effort":"low|medium|high","why":""},"prompt":"","selected_task_ids":[],"complete_task_ids":[], '
            '"defer_task_ids":[],"touch_long_task_ids":[],"depends_on":[],"can_run_parallel":true,"expected_output":""}]}],'
            '"updates":{"complete_task_ids":[],"defer_task_ids":[],"touch_long_task_ids":[]}}'
        )
        autonomous_mode_text = "允许自主探索" if context.allow_autonomous_explore else "仅显式任务驱动（默认不自主探索）"
        fixed_metabolism_text = "开启：每轮固定占用一路并行支路" if context.fixed_metabolism_branch else "关闭"
        background_growth_text = "开启：显式任务稀少或已收口时，可追加一条受控自我提升小步" if context.encourage_background_growth else "关闭"
        tasks_context = (context.tasks_md_text or "").strip() or "(空)"
        maintenance_entry_text = (
            "若本轮目标是修改 role/prompt/code/config、收敛提示词漂移、准备升级或重启，优先把 branch 设为 `agent_role=update-agent`，"
            "并尽量使用 `execution_kind=maintenance` 或 `capability_type=agent_maintenance`。\n"
            "经理型 planner 负责拆出 `process_role`，例如 executor / test / acceptance；update-agent 负责先找单一真源、收敛重复规则、生成 patch plan、说明验证与风险；若需要身体目录改动或重启，走统一 upgrade_request 入口。"
        )
        assembled = self._prompt_assembly_service.assemble_planner_prompt(
            PlannerPromptContext(
                base_prompt_text=template,
                json_schema=json_schema,
                now_text=context.now_text,
                soul_text=context.soul_text or "(空)",
                role_text=context.role_text or "(空)",
                max_parallel=str(context.max_parallel),
                max_serial_per_group=str(context.max_serial_per_group),
                autonomous_mode_text=autonomous_mode_text,
                fixed_metabolism_text=fixed_metabolism_text,
                background_growth_text=background_growth_text,
                tasks_context=tasks_context,
                recent_memory_text=context.recent_text or "(空)",
                local_memory_text=context.local_memory_text or "(空)",
                skills_text=context.skills_text or "(空)",
                task_workspace_context=context.task_workspace_text or "(空)",
                subagents_text=context.subagents_text or "(空)",
                teams_text=context.teams_text or "(空)",
                public_library_text=context.public_library_text or "(空)",
                maintenance_entry_text=maintenance_entry_text,
                runtime_context_text=context.context_text,
            )
        )
        if not bootstrap_text:
            return assembled
        return f"【Bootstrap】\n{bootstrap_text}\n\n{assembled}".strip()

    def default_plan(self, workspace: str) -> dict:
        return self.build_status_only_plan(
            reason="当前无结构化任务队列，由决策模型自行判断",
            user_message=f"管家bot 心跳正常。任务来源已改为 heartbeat_tasks.md，由规划器自行解读与决策。时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

    def planner_fallback_status_plan(self) -> dict:
        return {
            "chosen_mode": "status",
            "execution_mode": "defer",
            "reason": "规划器超时或未返回有效结果，本轮降级为状态心跳",
            "user_message": f"管家bot 心跳正常，但本轮规划器未及时返回，先跳过执行。时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "execute_prompt": "",
            "selected_task_ids": [],
            "deferred_task_ids": [],
            "defer_reason": "planner fallback",
            "summary_prompt": "",
            "task_groups": [],
            "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
        }

    def _record_planner_success(self, workspace: str) -> None:
        self._write_planner_state(workspace, failure_count=0, backoff_until_epoch=0.0)

    def _record_planner_failure(self, heartbeat_cfg: dict, workspace: str) -> int:
        planner_state = self._read_planner_state(workspace)
        self._manager._heartbeat_planner_failure_count = int(planner_state.get("failure_count") or 0) + 1
        backoff_seconds = self._planner_failure_backoff_seconds(heartbeat_cfg)
        self._write_planner_state(
            workspace,
            failure_count=self._manager._heartbeat_planner_failure_count,
            backoff_until_epoch=time.time() + backoff_seconds,
        )
        return backoff_seconds

    def _planner_fallback_plan(self, heartbeat_cfg: dict, workspace: str, preview: str, timeout_seconds: int, reason: str) -> dict:
        backoff_seconds = self._record_planner_failure(heartbeat_cfg, workspace)
        print(
            f"[心跳服务] 规划器未成功返回 | timeout={timeout_seconds}s | backoff={backoff_seconds}s | preview={preview}",
            flush=True,
        )
        context = self.build_planning_context(heartbeat_cfg, workspace)
        return self._build_local_fallback_task_plan(
            heartbeat_cfg,
            context,
            workspace,
            reason_prefix="规划器未成功返回，改用本地兜底策略",
        )

    def plan_action(self, cfg: dict, heartbeat_cfg: dict, workspace: str, timeout: int, model: str, planner_timeout: int | None = None) -> dict:
        context = self.build_planning_context(heartbeat_cfg, workspace)
        backoff_plan = self.build_planner_backoff_plan(heartbeat_cfg, context, workspace)
        if backoff_plan is not None:
            return backoff_plan

        prompt = self.build_planning_prompt(cfg, heartbeat_cfg, workspace)
        out = ""
        ok = False
        effective_timeout = max(15, int(planner_timeout or self.resolve_planner_timeout(heartbeat_cfg, timeout)))
        self._manager._heartbeat_last_planner_started_at = time.time()
        try:
            out, ok = self._manager._run_model_fn(prompt, workspace, effective_timeout, model)
        except Exception as exc:
            print(f"[心跳服务] 规划调用失败: {exc}", flush=True)
        data = self._manager._extract_json_block(out if ok else "") or {}
        plan = self.default_plan(workspace)
        preview = re.sub(r"\s+", " ", str(out or "")).strip()[:160]
        if not ok:
            return self._planner_fallback_plan(heartbeat_cfg, workspace, preview, effective_timeout, reason="not-ok")
        if not data:
            return self._planner_fallback_plan(heartbeat_cfg, workspace, preview, effective_timeout, reason="invalid-json")

        self._record_planner_success(workspace)

        plan["chosen_mode"] = str(data.get("chosen_mode") or plan.get("chosen_mode") or "status").strip()
        plan["execution_mode"] = str(data.get("execution_mode") or plan.get("execution_mode") or "single").strip()
        plan["reason"] = str(data.get("reason") or plan.get("reason") or "").strip()
        plan["user_message"] = str(data.get("user_message") or plan.get("user_message") or "").strip()
        plan["tell_user"] = str(data.get("tell_user") or plan.get("tell_user") or "").strip()
        plan["tell_user_candidate"] = str(data.get("tell_user_candidate") or plan.get("tell_user") or plan.get("tell_user_candidate") or "").strip()
        plan["tell_user_reason"] = str(data.get("tell_user_reason") or plan.get("tell_user_reason") or "").strip()
        plan["tell_user_type"] = str(data.get("tell_user_type") or plan.get("tell_user_type") or "").strip()
        try:
            plan["tell_user_priority"] = max(0, min(100, int(data.get("tell_user_priority") or plan.get("tell_user_priority") or 0)))
        except Exception:
            plan["tell_user_priority"] = 0
        plan["execute_prompt"] = str(data.get("execute_prompt") or plan.get("execute_prompt") or "").strip()
        plan["defer_reason"] = str(data.get("defer_reason") or plan.get("defer_reason") or "").strip()
        plan["summary_prompt"] = str(data.get("summary_prompt") or plan.get("summary_prompt") or "").strip()
        selected_task_ids = data.get("selected_task_ids") if isinstance(data.get("selected_task_ids"), list) else plan.get("selected_task_ids")
        deferred_task_ids = data.get("deferred_task_ids") if isinstance(data.get("deferred_task_ids"), list) else plan.get("deferred_task_ids")
        plan["selected_task_ids"] = self.sanitize_id_list(selected_task_ids, limit=10)
        plan["deferred_task_ids"] = self.sanitize_id_list(deferred_task_ids, limit=10)
        if isinstance(data.get("task_groups"), list):
            plan["task_groups"] = data.get("task_groups")
        updates = data.get("updates") if isinstance(data.get("updates"), dict) else {}
        plan["updates"] = {
            "complete_task_ids": self.sanitize_id_list(updates.get("complete_task_ids"), limit=10),
            "defer_task_ids": self.sanitize_id_list(updates.get("defer_task_ids"), limit=10),
            "touch_long_task_ids": self.sanitize_id_list(updates.get("touch_long_task_ids"), limit=10),
        }

        if str(plan.get("chosen_mode") or "").strip() == "explore" and not context.allow_autonomous_explore:
            fallback_plan = self.default_plan(workspace)
            if str(fallback_plan.get("chosen_mode") or "status") != "status":
                fallback_plan["reason"] = "当前默认关闭自主探索，忽略规划器 explore 结果，回退到显式任务"
                fallback_plan["defer_reason"] = "autonomous explore disabled"
                return fallback_plan
            return self.build_status_only_plan(
                reason="当前默认关闭自主探索，忽略规划器 explore 结果",
                user_message=(
                    "管家bot 心跳正常；当前未开启自主探索模式，且本轮没有明确任务注入，"
                    f"因此忽略 explore 计划。时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
            )
        return self._ensure_fixed_branches(plan, context)

    def apply_plan(self, workspace: str, plan: dict, execution_result: str, branch_results: list[dict] | None = None) -> None:
        branch_results = [item for item in (branch_results or []) if isinstance(item, dict)]

        short_store = self._manager._load_heartbeat_memory(workspace)
        long_store = self._manager._load_heartbeat_long_tasks(workspace)
        short_tasks = short_store.get("tasks") if isinstance(short_store, dict) else []
        long_tasks = long_store.get("tasks") if isinstance(long_store, dict) else []

        ledger = TaskLedgerService(workspace)
        ledger.ensure_bootstrapped(short_tasks=short_tasks, long_tasks=long_tasks)
        payload = ledger.apply_heartbeat_result(plan, execution_result, branch_results)

        legacy_short, legacy_long = ledger.export_legacy_payloads(payload)

        if isinstance(short_store, dict):
            legacy_short["notes"] = short_store.get("notes") if isinstance(short_store.get("notes"), list) else []
            planner_state = short_store.get("planner_state") if isinstance(short_store.get("planner_state"), dict) else {}
            if planner_state:
                legacy_short["planner_state"] = planner_state
            last_sent = str(short_store.get("last_heartbeat_sent_at") or "").strip()
            if last_sent:
                legacy_short["last_heartbeat_sent_at"] = last_sent

        self._manager._save_heartbeat_memory(workspace, legacy_short)
        self._manager._save_heartbeat_long_tasks(workspace, legacy_long)
        if not self._manager._legacy_heartbeat_markdown_mirrors_enabled():
            for mirror_path in (
                self._manager._heartbeat_memory_mirror_path(workspace),
                self._manager._heartbeat_long_tasks_mirror_path(workspace),
            ):
                try:
                    if mirror_path.exists():
                        mirror_path.unlink()
                except Exception:
                    pass

