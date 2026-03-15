# -*- coding: utf-8 -*-
"""
【Memory 模块】butler_bot 记忆层

职责：
- recent memory 读写与 prompt 注入
- 回复后短期记忆持久化
- 长期记忆 upsert 与文件数限制
- 启动/定时维护 + 启动完成飞书私聊通知

与 agent（消息层）分离，由 butler_bot 组合调用。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import sys
import multiprocessing
import os
from pathlib import Path
import locale
import random
import re
import shutil
import threading
import time
import traceback
import subprocess
from contextlib import contextmanager
from typing import Callable
import uuid

import requests
from heartbeat_orchestration import HeartbeatOrchestrator, HeartbeatPlanningContext
from governor import GovernedAction, Governor
from services.local_memory_index_service import LocalMemoryIndexService, LocalMemoryQueryParams
from services.memory_backend import build_default_memory_backend
from services.memory_service import TurnMemoryExtractionService
from services.subconscious_service import SubconsciousConsolidationService
from services.task_ledger_service import TaskLedgerService

from registry.agent_capability_registry import (
    load_team_catalog,
    render_public_capability_catalog_for_prompt,
    render_subagent_catalog_for_prompt,
    render_team_catalog_for_prompt,
)
from butler_paths import (
    BEAT_RECENT_MEMORY_DIR_REL,
    BODY_HOME_REL,
    BUTLER_MAIN_AGENT_ROLE_FILE_REL,
    BUTLER_SOUL_FILE_REL,
    CURRENT_USER_PROFILE_FILE_REL,
    CURRENT_USER_PROFILE_TEMPLATE_FILE_REL,
    COMPANY_HOME_REL,
    FEISHU_AGENT_ROLE_FILE_REL,
    FILE_MANAGER_AGENT_ROLE_FILE_REL,
    GUARDIAN_REQUESTS_DIR_REL,
    HEARTBEAT_EXECUTOR_AGENT_ROLE_FILE_REL,
    HEARTBEAT_EXECUTOR_WORKSPACE_HINT_FILE_REL,
    HEARTBEAT_PLANNER_AGENT_ROLE_FILE_REL,
    HEARTBEAT_PLANNER_CONTEXT_FILE_REL,
    HEARTBEAT_PROMPT_REL,
    HEARTBEAT_UPGRADE_REQUEST_JSON_REL,
    LOCAL_MEMORY_DIR_REL,
    RECENT_MEMORY_DIR_REL,
    RESTART_REQUEST_JSON_REL,
    RUN_DIR_REL,
    SELF_MIND_DIR_REL,
    STATE_DIR_REL,
    prompt_path_text,
    resolve_butler_root,
)
from runtime.runtime_logging import install_print_hook, set_runtime_log_config
from registry.skill_registry import render_skill_catalog_for_prompt

install_print_hook(default_level=os.environ.get("BUTLER_LOG_LEVEL", "info"))

RECENT_MEMORY_FILE = "recent_memory.json"
RECENT_ARCHIVE_FILE = "recent_archive.md"
RECENT_SUMMARY_POOL_FILE = "recent_summary_pool.json"
RECENT_SUMMARY_ARCHIVE_FILE = "recent_summary_archive.jsonl"
RECENT_SUMMARY_LADDER_FILE = "recent_summary_ladder.json"
RECENT_STARTUP_STATUS_FILE = "startup_maintenance_status.json"
TALK_RECENT_POOL = "talk"
BEAT_RECENT_POOL = "beat"
LONG_MAINTENANCE_STATUS_FILE = "long_memory_maintenance_status.json"
HEARTBEAT_MEMORY_FILE = "heart_beat_memory.json"
HEARTBEAT_MEMORY_MIRROR_FILE = "heart_beat_memory.md"
HEARTBEAT_LAST_SENT_FILE = "heartbeat_last_sent.json"
HEARTBEAT_LONG_TASKS_FILE = "heartbeat_long_tasks.json"
HEARTBEAT_LONG_TASKS_MIRROR_FILE = "heartbeat_long_tasks.md"
HEARTBEAT_TASKS_MD_FILE = "heartbeat_tasks.md"
HEARTBEAT_TASK_BOARD_DIR_NAME = "heartbeat_tasks"
HEARTBEAT_TASK_CHANGE_LOG_FILE = "task_change_log.jsonl"
HEARTBEAT_PLANNER_STATE_FILE = "heartbeat_planner_state.json"
LOCAL_WRITE_JOURNAL_FILE = "local_memory_write_journal.jsonl"
RESTART_REQUESTED_FLAG_NAME = "restart_requested.flag"
HEARTBEAT_PID_FILE_NAME = "butler_bot_heartbeat.pid"
HEARTBEAT_WATCHDOG_STATE_FILE_NAME = "heartbeat_watchdog_state.json"
MAIN_PROCESS_STATE_FILE_NAME = "butler_bot_main_state.json"
HEARTBEAT_RUN_STATE_FILE_NAME = "heartbeat_run_state.json"
SELF_MIND_RAW_FILE_NAME = "raw_thoughts.json"
SELF_MIND_REVIEW_FILE_NAME = "thought_reviews.json"
SELF_MIND_BEHAVIOR_MIRROR_FILE_NAME = "behavior_mirror.md"
SELF_MIND_PERCEPTION_FILE_NAME = "perception_snapshot.md"
SELF_MIND_STATE_FILE_NAME = "mind_loop_state.json"
SELF_MIND_BRIDGE_FILE_NAME = "mind_body_bridge.json"
SELF_MIND_COGNITION_INDEX_FILE_NAME = "L0_index.json"
SELF_MIND_COGNITION_L1_DIR_NAME = "L1_summaries"
SELF_MIND_COGNITION_L2_DIR_NAME = "L2_details"
GUARDIAN_REQUEST_SCHEMA_VERSION = 1

COMPANY_ROOT_TEXT = prompt_path_text(COMPANY_HOME_REL)
BODY_ROOT_TEXT = prompt_path_text(BODY_HOME_REL)
UPGRADE_REQUEST_TEXT = prompt_path_text(HEARTBEAT_UPGRADE_REQUEST_JSON_REL)

# 心跳执行时注入的工作区约定（除非用户显式指定，产出一律写入公司目录）
HEARTBEAT_WORKSPACE_HINT_FALLBACK_TEMPLATE = (
    "【心跳任务·工作区约定】除非用户显式指定，默认把本轮产出写到 {company_root} 下的合适子目录。\n"
    "【工作区自维护】允许顺手做轻量归位、合并同主题文件、补索引，但不要让整理吞掉本轮主任务。\n"
    "【自我升级审批】若判断 {body_root} 下代码/配置必须改动或需要重启，不能直接修改；只可把升级方案写入 {upgrade_request}，等待聊天主进程在用户批准后接管执行。\n\n"
)

TALK_RECENT_MAX_ITEMS = 15
BEAT_RECENT_MAX_ITEMS = 15
TALK_RECENT_MAX_CHARS = 15000
BEAT_RECENT_MAX_CHARS = 20000
RECENT_STALE_DIR_NAME = "过时"
RECENT_STALE_KEEP_TALK_TURNS = 4
RECENT_STALE_COMPANION_MAX_AGE_SECONDS = 45 * 60
RECENT_STALE_INTERRUPTED_MAX_AGE_SECONDS = 2 * 60 * 60
RECENT_STALE_PROMOTED_MAX_AGE_SECONDS = 30 * 60
PENDING_FOLLOWUP_MAX_AGE_SECONDS = 10 * 60

LOCAL_MAX_CLASSIFIED_FILES = 10
LOCAL_OVERFLOW_FILE = "未分类_临时存放.md"
LOCAL_MAX_FILES = LOCAL_MAX_CLASSIFIED_FILES + 1
LOCAL_MAX_FILE_CHARS = 8000
LOCAL_README_FILE = "readme.md"
LOCAL_INDEX_FILE = "L0_index.json"
LOCAL_RELATIONS_FILE = ".relations.json"
LOCAL_L1_SUMMARY_DIR_NAME = "L1_summaries"
LOCAL_L2_DETAIL_DIR_NAME = "L2_details"
LOCAL_L1_MAX_FILES = 100
LOCAL_L2_DETAIL_TRIGGER_CHARS = 320
LOCAL_L2_SUMMARY_PREVIEW_CHARS = 200
LOCAL_CATEGORY_NAMES = (
    "identity",
    "preferences",
    "rules",
    "projects",
    "research",
    "operations",
    "relationships",
    "references",
    "reflections",
    "misc",
)
LONG_MAINTENANCE_MIN_INTERVAL_SECONDS = 30 * 60

MAINTENANCE_TIMES = ((0, 0), (18, 0))

STARTUP_NOTIFY_OPEN_ID_KEY = "startup_notify_open_id"
STARTUP_NOTIFY_RECEIVE_ID_TYPE_KEY = "startup_notify_receive_id_type"
HEARTBEAT_RECEIVE_ID_KEY = "receive_id"
HEARTBEAT_RECEIVE_ID_TYPE_KEY = "receive_id_type"
TELL_USER_RECEIVE_ID_KEY = "tell_user_receive_id"
TELL_USER_RECEIVE_ID_TYPE_KEY = "tell_user_receive_id_type"

NEW_TASK_HINTS = [
    "新任务", "全新任务", "全新情景", "重新开始", "从头开始", "切换话题",
    "忽略之前", "new task", "start over", "new topic", "reset context",
]
LONG_TERM_HINTS = [
    "记住", "以后", "默认", "偏好", "必须", "统一", "固定", "长期", "沿用",
    "约定", "习惯", "风格", "希望", "尽量", "不要", "记下来", "后续",
    "always", "default", "remember", "preference", "must",
]
HEARTBEAT_TASK_HINTS = [
    "后台", "心跳", "提醒", "以后每天", "每天", "定时", "工作时间", "后台完成", "后台继续", "自动提醒",
]
HEARTBEAT_ACTION_HINTS = [
    "提醒", "整理", "检查", "汇报", "完成", "跟进", "推进", "继续", "记录", "发送", "复盘", "查看",
]

HEARTBEAT_MAX_PARALLEL_DEFAULT = 3
LOG_MAX_LINES_PER_FILE = 1000
HEARTBEAT_RESTART_BURST_LIMIT = 2
HEARTBEAT_RESTART_BURST_WINDOW_SECONDS = 5 * 60
HEARTBEAT_RESTART_COOLDOWN_SECONDS = 10 * 60
HEARTBEAT_RESTART_HANDOVER_SECONDS = 90
MAIN_PROCESS_STATE_HEARTBEAT_SECONDS = 15
HEARTBEAT_PLANNER_MIN_INTERVAL_SECONDS = 60
EXTERNAL_HEARTBEAT_ENV_NAME = "BUTLER_EXTERNAL_HEARTBEAT"


def _configured_cursor_api_keys(cfg: dict | None) -> list[str]:
    snapshot = cfg if isinstance(cfg, dict) else {}
    raw_keys = snapshot.get("cursor_api_keys") if isinstance(snapshot, dict) else None
    if isinstance(raw_keys, str):
        raw_keys = [raw_keys]
    if not isinstance(raw_keys, list):
        raw_keys = []

    keys: list[str] = []
    seen: set[str] = set()
    for raw in raw_keys:
        key = str(raw or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def build_cursor_cli_env(cfg: dict | None = None, base_env: dict | None = None) -> dict:
    env = dict(base_env or os.environ.copy())
    env.pop("NO_PROXY", None)
    for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY", "NO_PROXY"):
        raw_value = str(env.get(proxy_key) or "").strip()
        if raw_value and any(marker in raw_value for marker in ("127.0.0.1:9", "localhost:9")):
            env.pop(proxy_key, None)

    workspace_root = resolve_butler_root(str((cfg or {}).get("workspace_root") or os.getcwd()))
    runtime_root = workspace_root / "butler_main" / "butler_bot_code" / "run" / "cursor_runtime_env"
    session_root = runtime_root / "sessions" / f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    roaming_root = session_root / "Roaming"
    local_root = session_root / "Local"
    profile_root = session_root / "Profile"
    temp_root = session_root / "Temp"
    _cleanup_cursor_runtime_sessions(runtime_root)
    roaming_root.mkdir(parents=True, exist_ok=True)
    local_root.mkdir(parents=True, exist_ok=True)
    profile_root.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    env["APPDATA"] = str(roaming_root)
    env["LOCALAPPDATA"] = str(local_root)
    env["USERPROFILE"] = str(profile_root)
    env["HOME"] = str(profile_root)
    env["TMP"] = str(temp_root)
    env["TEMP"] = str(temp_root)
    env["XDG_CONFIG_HOME"] = str(roaming_root)
    env["CURSOR_CONFIG_HOME"] = str(roaming_root)

    key_pool = _configured_cursor_api_keys(cfg)
    if not key_pool:
        return env
    env["CURSOR_API_KEY"] = random.choice(key_pool)
    return env


def _cleanup_cursor_runtime_sessions(runtime_root: Path, *, max_age_seconds: int = 12 * 60 * 60) -> None:
    sessions_root = runtime_root / "sessions"
    if not sessions_root.exists():
        return
    cutoff = time.time() - max(600, int(max_age_seconds or 0))
    for child in sessions_root.iterdir():
        if not child.is_dir():
            continue
        try:
            if child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
        except Exception:
            continue


def resolve_cursor_cli_cmd_path(cfg: dict | None = None) -> str:
    """解析 Cursor CLI 可执行路径：支持配置覆盖、兼容 dist-package 与版本号子目录。"""
    # 1) 配置显式路径
    if isinstance(cfg, dict):
        path = (cfg.get("cursor_cli_path") or "").strip()
        if path and os.path.isfile(path):
            return path
    # 2) 旧版固定路径
    base = os.environ.get("LOCALAPPDATA", "")
    legacy = os.path.join(base, "cursor-agent", "versions", "dist-package", "cursor-agent.cmd")
    if os.path.isfile(legacy):
        return legacy
    # 3) 新版版本号子目录：取 versions 下最新版本目录中的 cursor-agent.cmd
    versions_dir = os.path.join(base, "cursor-agent", "versions")
    if os.path.isdir(versions_dir):
        try:
            subs = [
                d for d in os.listdir(versions_dir)
                if os.path.isdir(os.path.join(versions_dir, d))
            ]
            subs.sort(reverse=True)
            for ver in subs:
                cand = os.path.join(versions_dir, ver, "cursor-agent.cmd")
                if os.path.isfile(cand):
                    return cand
        except OSError:
            pass
    return legacy

DEFAULT_HEARTBEAT_PROMPT_TEMPLATE = """# 心跳规划器

你是管家bot的心跳规划器。你的任务是在每次心跳时基于当前上下文独立思考，并输出一份可执行的 JSON 计划。

只输出 JSON，不要解释，不要输出 Markdown 代码块。

## JSON Schema

{json_schema}

## 当前运行上下文

- 当前时间：{now_text}
- 并行上限：最多 {max_parallel} 路
- 自主探索模式：{autonomous_mode_text}

## 额外上下文

{context_text}

## 短期任务

{short_tasks_json}

## 长期/定时任务

{long_tasks_json}

## 最近上下文

{recent_text}

## 任务看板与调度协议

{tasks_context}

## 可复用 Skills

{skills_text}

## 决策原则

1. 你需要自己判断优先级，而不是机械套规则；在短期任务、长期/定时任务、自主探索与最近运行事实之间做取舍。
2. 如果确实没有值得执行的任务，可以返回 `status`，但 `user_message` 仍要告诉用户你为什么这样判断。
3. 如果要执行任务，优先输出 `task_groups` + `branches`，让执行器可以按组串行、组内并行地推进。
4. `user_message` 是发给心跳窗的自然语言说明，要清楚说明本轮准备做什么。
5. `tell_user_candidate` / `tell_user_reason` / `tell_user_type` 用来留下“下一轮可能继续心理活动并主动开口”的候选意图，不要把 planner 写成直接给用户发 final 文案的层；真正要不要开口、怎么组织语言，由下一轮的 Feishu 对话人格继续承接后决定。`tell_user_type` 可用 `result_share / risk_share / thought_share / light_chat / growth_share`。
6. branch 的 `prompt` 必须写清楚角色、自身目标、预期产出路径；默认公司目录是 `./工作区`。
7. 只有互不依赖的任务才能并行；有依赖关系的放到下一组，或延后到下一轮。
8. 任务一步的粒度由你自己判断，但要能在单轮内形成可见进展，不要把整轮都浪费在空泛规划上。
8.1 **少做碎片化微操**：除非任务高风险、强依赖、易出错，否则不要把 executor 可自己判断的动作拆成一串过细步骤。更优先给“目标 + 边界 + 验收标准 + 产出路径”，把微观执行权交给 executor。
8.2 **把验收写进 branch**：branch prompt 至少要让 executor 看见四件事：本轮目标、边界/禁区、验收标准、失败后的诊断与迭代预期。遇到外部调用失败、权限码、ID 不匹配等可恢复问题时，默认要求 executor 先诊断、换路、复试，再决定是否报阻塞。
8.3 **缺能力时补能力闭环**：若任务卡在缺 skill / MCP / 外部能力，不要只返回“无法完成”。先判断现有能力能否换路完成；若仍不足，则规划“检索公开方案 -> 安全审阅 -> 落 skill/MCP -> 回到原任务重试”的闭环，并把来源、风险、回退与重试结果写进 branch 或结果。
9. 如果发现任务信息脏乱、重复或过时，可以在计划里顺手做轻量治理，但不要偏离本轮主目标。
10. 除非运行上下文明确允许自主探索，或用户通过短期/紧急任务显式注入新目标，否则不要输出 `chosen_mode=explore`，应返回 `status` 或显式任务计划。
11. 身体运行、灵魂、记忆、心跳属于 DNA 核心，不要把这些基础运转拆成 skill。
12. 若发现某个外部能力可复用、非 DNA、且应长期维护，优先沉淀到 `./butler_main/butler_bot_agent/skills/分类目录/技能名/`，并在本轮中把它当作可调用 skill 使用或维护。
13. 决策时优先相信当前运行事实和最近变化，其次统一 recent，再其次长期记忆，最后才是静态说明文档；同一来源内越新权重越高。
14. 如果近期信号、运行事实或现有规则提示某些说明文档疑似过时，而本轮没有更高优先级任务，你可以安排一次轻量核对、更新 README/说明或归档旧文档，但不要做大规模清扫。
14. 任务入口默认来自分类任务看板；外部对话、潜意识整理和心跳自修正都可以写入看板，但不要绕过看板各写各的临时入口。
15. 调度时要把时间、用户当前是否在活跃聊天、是否睡眠时段、任务紧迫度/DDL 一起看；这是动态权衡，不是死板 if-else。
17. 分类只是帮助你看清来源与节奏，不是刚性动作空间。必要时你可以跨类取舍，但要在 reason 里说清楚为什么。
18. 若工作区或单主题目录出现明显碎片化、过程文件堆积、真源不清或自己都难以读完，应优先安排整理清洁分支，不要继续扩张新文件。
19. 整理清洁分支默认执行这套协议：按“内容 / 时间 / 有效性”分诊；过时无用移到 `./工作区/temp`；完成成果合并为带 `[Final]` 的主文件；未完成事项统一改为 `[Working n/m]` 并写明估计进度、下一步和阻塞。
20. 未来产出要主动控量：优先追加到已有索引、主文件、阶段总结或单一目录入口，避免为同一主题反复生成难以阅读的过程文件。
21. 若本轮为治理去学习项目管理、信息架构、归档方法，最终必须把有效方法沉淀为 Butler 可执行的目录规则、模板或命名约束，而不是只留下阅读痕迹。
22. **升级不要只停在死知识**：自我升级结论不能只沉在 local_memory / 文档里。若它改变了稳定行为，应下沉到 role / prompt；若它多轮验证后已经属于长期稳定的人格与判断底色，再考虑进入 Soul。
23. 若本轮真的形成了用户可感知的新技能、新 MCP 接入或新的稳定能力边界，可把它作为 `growth_share` 候选；不要空泛播报“我成长了”，要明确新会了什么、能用来干什么。
"""

class MemoryManager:
    def __init__(
        self,
        config_provider: Callable[[], dict],
        run_model_fn: Callable[[str, str, int, str], tuple[str, bool]],
    ) -> None:
        self._config_provider = config_provider
        self._run_model_fn = run_model_fn
        self._memory_lock = threading.Lock()
        self._maintenance_lock = threading.Lock()
        self._maintenance_started = False
        self._startup_subprocess_started = False
        self._heartbeat_lock = threading.Lock()
        self._heartbeat_task_board_io_lock = threading.Lock()
        self._heartbeat_started = False
        self._heartbeat_process_started = False
        self._heartbeat_bootstrap_done = False
        self._heartbeat_process: multiprocessing.Process | None = None
        self._heartbeat_watchdog_started = False
        self._heartbeat_restart_times: list[float] = []
        self._heartbeat_restart_cooldown_until = 0.0
        self._main_process_state_started = False
        self._heartbeat_last_planner_started_at = 0.0
        self._heartbeat_planner_failure_count = 0
        self._heartbeat_planner_backoff_until = 0.0
        self._self_mind_started = False
        self._self_mind_lock = threading.Lock()
        self._self_mind_loop_token = 0
        self._latest_runtime_cfg: dict = {}
        self._heartbeat_orchestrator = HeartbeatOrchestrator(self)
        self._governor = Governor()
        self._turn_memory_service = TurnMemoryExtractionService(
            run_model_fn=self._run_model_fn,
            json_extractor=self._extract_json_block,
            heuristic_task_extractor=self._extract_heartbeat_candidates,
            heuristic_long_term_candidate=self._heuristic_long_term_candidate,
            normalize_heartbeat_tasks=self._normalize_heartbeat_tasks,
        )
        self._subconscious_service = SubconsciousConsolidationService()
        self._memory_backend_lock = threading.Lock()
        self._memory_backend_cache: dict[str, object] = {}
        self._runtime_request_local = threading.local()

    def get_runtime_request_override(self) -> dict:
        override = getattr(self._runtime_request_local, "runtime_request", None)
        return dict(override or {})

    @contextmanager
    def runtime_request_scope(self, runtime_request: dict | None):
        previous = getattr(self._runtime_request_local, "runtime_request", None)
        self._runtime_request_local.runtime_request = dict(runtime_request or {})
        try:
            yield
        finally:
            if previous is None:
                if hasattr(self._runtime_request_local, "runtime_request"):
                    delattr(self._runtime_request_local, "runtime_request")
            else:
                self._runtime_request_local.runtime_request = previous

    def _get_memory_backend(self, workspace: str | None = None):
        cfg = self._config_provider() or {}
        selected_workspace = str(workspace or cfg.get("workspace_root") or os.getcwd())
        root_path = resolve_butler_root(selected_workspace)
        cache_key = str(root_path.resolve())
        with self._memory_backend_lock:
            backend = self._memory_backend_cache.get(cache_key)
            if backend is None:
                backend = build_default_memory_backend(root_path)
                self._memory_backend_cache[cache_key] = backend
            return backend

    def _sync_memory_backend_recent_event(self, workspace: str, entry: dict, companion_entries: list[dict]) -> None:
        try:
            backend = self._get_memory_backend(workspace)
            primary_payload = {
                "record_id": str(entry.get("memory_id") or uuid.uuid4()),
                "record_type": "recent_turn",
                "scope": "recent",
                "status": str(entry.get("status") or "completed"),
                "topic": str(entry.get("topic") or "")[:160],
                "summary": str(entry.get("summary") or "")[:320],
                "has_long_term_candidate": bool((entry.get("long_term_candidate") or {}).get("should_write")),
                "source": "memory_manager._finalize_recent_and_local_memory",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            backend.episodic.append(primary_payload)

            for item in companion_entries or []:
                if not isinstance(item, dict):
                    continue
                backend.episodic.append(
                    {
                        "record_id": str(item.get("memory_id") or uuid.uuid4()),
                        "record_type": "recent_companion",
                        "scope": "recent",
                        "status": str(item.get("status") or "completed"),
                        "topic": str(item.get("topic") or "")[:160],
                        "summary": str(item.get("summary") or "")[:320],
                        "source": "memory_manager._finalize_recent_and_local_memory",
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
        except Exception as e:
            print(f"[memory-backend] recent event sync failed: {e}", flush=True)

    def _sync_memory_backend_semantic_event(self, local_dir: Path, payload: dict) -> None:
        try:
            backend = self._get_memory_backend(str(resolve_butler_root(local_dir)))
            source_memory_id = str(payload.get("source_memory_id") or "").strip()
            summary_path = str(payload.get("summary_path") or "").strip()
            action = str(payload.get("action") or "").strip()
            title = str(payload.get("title") or "").strip() or "untitled"
            entry_id = summary_path or source_memory_id or f"{action}:{title}:{uuid.uuid4()}"
            backend.semantic.upsert(
                entry_id,
                {
                    "entry_id": entry_id,
                    "record_type": "semantic_write_event",
                    "scope": "semantic",
                    "status": "completed",
                    "title": title,
                    "summary": str(payload.get("summary_preview") or "")[:320],
                    "action": action,
                    "keywords": list(payload.get("keywords") or []),
                    "source_type": str(payload.get("source_type") or ""),
                    "source_reason": str(payload.get("source_reason") or ""),
                    "source_topic": str(payload.get("source_topic") or ""),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
        except Exception as e:
            print(f"[memory-backend] semantic event sync failed: {e}", flush=True)

    def prepare_user_prompt_with_recent(
        self,
        user_prompt: str,
        exclude_memory_id: str | None = None,
        previous_pending: dict | None = None,
    ) -> str:
        cfg = self._config_provider() or {}
        workspace = cfg.get("workspace_root") or os.getcwd()
        if self._is_new_task_prompt(user_prompt):
            return user_prompt
        recent_entries = self._load_recent_entries(workspace)
        if exclude_memory_id:
            recent_entries = [
                item for item in recent_entries
                if str((item or {}).get("memory_id") or "") != str(exclude_memory_id)
            ]
        recent_text = self._render_recent_context(recent_entries, max_chars=self._recent_max_chars(TALK_RECENT_POOL))
        summary_text = self._render_recent_summary_context(
            self._select_recent_summaries_for_prompt(workspace, user_prompt, pool=TALK_RECENT_POOL),
            max_chars=max(600, self._recent_max_chars(TALK_RECENT_POOL) // 3),
        )
        summary_history_text = self._render_recent_summary_ladder_context(
            self._load_recent_summary_ladder(workspace, pool=TALK_RECENT_POOL),
            max_chars=max(500, self._recent_max_chars(TALK_RECENT_POOL) // 3),
        )
        talk_recent_limit = self._recent_max_items(TALK_RECENT_POOL)
        followup_text = self._render_pending_followup_context(previous_pending, user_prompt)
        if followup_text:
            print(f"[recent-followup] {re.sub(r'\s+', ' ', followup_text)[:160]}", flush=True)
        if not recent_text and not summary_text and not summary_history_text:
            return (followup_text + "\n\n" + user_prompt).strip() if followup_text else user_prompt
        followup_block = f"{followup_text}\n\n" if followup_text else ""
        summary_block = (
            f"【recent_summary（窗口外的小结，按相关性抽取）】\n{summary_text}\n\n"
            if summary_text else ""
        )
        summary_history_block = (
            f"【recent_summary_archive（10天/4个月/年阶梯小结）】\n{summary_history_text}\n\n"
            if summary_history_text else ""
        )
        return (
            f"【recent_memory（最近{talk_recent_limit}轮窗口摘要，供上下文续接）】\n"
            f"{recent_text}\n\n"
            f"{summary_block}"
            f"{summary_history_block}"
            "【使用规则】若用户未明确说明“全新任务/全新情景”，请优先沿用 recent_memory；"
            "若用户明确开启新任务，则忽略 recent_memory。\n\n"
            f"{followup_block}"
            f"{user_prompt}"
        )

    def begin_pending_turn(self, user_prompt: str, workspace: str) -> tuple[str, dict | None]:
        entry_id = str(uuid.uuid4())
        pending_entry = self._build_provisional_recent_entry(entry_id, user_prompt, "")
        previous_pending = None
        with self._memory_lock:
            entries = self._load_recent_entries(workspace)
            self._expire_stale_pending_entries(entries)
            previous_pending = self._find_latest_pending_entry(entries)
            entries.append(pending_entry)
            entries, _ = self._compact_recent_entries_if_needed(entries, workspace, 0, "", reason="per-turn-pending")
            self._save_recent_entries(workspace, entries)
        print(
            f"[recent-pending] memory_id={entry_id} | current={str(pending_entry.get('topic') or '')[:60]}"
            + (f" | previous_pending={str((previous_pending or {}).get('topic') or '')[:60]}" if previous_pending else ""),
            flush=True,
        )
        return entry_id, previous_pending

    def on_reply_sent_async(
        self,
        user_prompt: str,
        assistant_reply: str,
        memory_id: str | None = None,
        model_override: str | None = None,
        suppress_task_merge: bool = False,
    ) -> None:
        cfg = self._config_provider() or {}
        workspace = cfg.get("workspace_root") or os.getcwd()
        timeout = int(cfg.get("agent_timeout", 300))
        model = str(model_override or cfg.get("agent_model", "auto") or "auto")
        self._write_recent_completion_fallback(memory_id, user_prompt, assistant_reply, workspace)
        print(f"[记忆] 收到 on_reply_sent，启动短期记忆持久化线程 (workspace={workspace[:50]}...)", flush=True)
        threading.Thread(
            target=self._finalize_recent_and_local_memory,
            args=(memory_id, user_prompt, assistant_reply, workspace, timeout, model, suppress_task_merge),
            daemon=True,
            name="recent-memory-writer",
        ).start()

    def start_background_services(self) -> None:
        if self._maintenance_started:
            return
        with self._maintenance_lock:
            if self._maintenance_started:
                return
            cfg = self._config_provider() or {}
            workspace = cfg.get("workspace_root") or os.getcwd()
            timeout = int(cfg.get("agent_timeout", 300))
            model = cfg.get("agent_model", "auto")

            # 启动时先修复上一次可能遗留的“正在回复中”记录，避免记忆断片。
            try:
                self._recover_pending_recent_entries_on_startup(workspace)
            except Exception as e:
                print(f"[recent-recover] 启动时修复 pending 记忆失败: {e}", flush=True)

            self._write_main_process_state(workspace, state="running")
            if not self._main_process_state_started:
                threading.Thread(
                    target=self._main_process_state_loop,
                    args=(workspace,),
                    daemon=True,
                    name="butler-main-state-heartbeat",
                ).start()
                self._main_process_state_started = True

            # 启动期长期+短期记忆维护改由心跳/潜意识链路统一调度；
            # 这里不再单独拉起 startup-maintenance 子进程，仅保留定时维护线程。
            threading.Thread(
                target=self._maintenance_loop,
                args=(workspace, timeout, model),
                daemon=True,
                name="memory-maintenance-scheduler",
            ).start()
            self._ensure_self_mind_loop_started()
            if not self._use_external_heartbeat_process(cfg):
                with self._heartbeat_lock:
                    self._start_heartbeat_service_locked(cfg)
                if not self._heartbeat_watchdog_started:
                    threading.Thread(
                        target=self._heartbeat_process_watchdog_loop,
                        args=(workspace,),
                        daemon=True,
                        name="butler-heartbeat-watchdog",
                    ).start()
                    self._heartbeat_watchdog_started = True
                    print("[心跳服务·看门狗] 已启动", flush=True)
            self._maintenance_started = True
            print("[记忆维护线程] 已启动（定时 00:00 / 18:00）", flush=True)
            print("[后台服务] Butler 主进程已接管 heartbeat / self_mind，本轮起不再依赖 guardian", flush=True)

    def _use_external_heartbeat_process(self, cfg: dict | None = None) -> bool:
        return False

    def _ensure_self_mind_loop_started(self) -> None:
        if not self._self_mind_enabled():
            return
        with self._self_mind_lock:
            if self._self_mind_started:
                return
            self._self_mind_loop_token += 1
            loop_token = self._self_mind_loop_token
            threading.Thread(
                target=self._self_mind_loop,
                args=(loop_token,),
                daemon=True,
                name="butler-self-mind",
            ).start()
            self._self_mind_started = True
            print("[self-mind] 独立意识循环已启动", flush=True)

    def _stop_heartbeat_service_locked(self, workspace: str, reason: str = "") -> bool:
        proc = self._heartbeat_process
        stopped = False
        if proc is not None:
            try:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=8)
                    if proc.is_alive():
                        proc.kill()
                        proc.join(timeout=3)
                stopped = True
            except Exception as exc:
                print(f"[心跳服务] 停止子进程失败: {exc}", flush=True)
        self._heartbeat_process = None
        self._heartbeat_started = False
        self._heartbeat_process_started = False
        self._clear_heartbeat_pid_file(workspace)
        self._write_heartbeat_watchdog_state(
            workspace,
            state="stopped",
            note=(reason or "heartbeat stopped by talk control")[:160],
        )
        return stopped

    def restart_heartbeat_service(self, workspace: str, reason: str = "") -> tuple[bool, str]:
        cfg = self._config_provider() or {}
        heartbeat_cfg = (cfg or {}).get("heartbeat") or {}
        if not isinstance(heartbeat_cfg, dict) or not heartbeat_cfg.get("enabled"):
            return False, "heartbeat 当前未启用。"
        with self._heartbeat_lock:
            self._stop_heartbeat_service_locked(workspace, reason=reason or "manual restart")
            self._start_heartbeat_service_locked(cfg)
            ok = bool(self._heartbeat_process and self._heartbeat_process.is_alive())
        if ok:
            return True, "已重启 heartbeat。"
        return False, "heartbeat 重启失败，请查看日志。"

    def restart_self_mind_loop(self) -> tuple[bool, str]:
        if not self._self_mind_enabled():
            return False, "self_mind 当前未启用。"
        with self._self_mind_lock:
            self._self_mind_loop_token += 1
            loop_token = self._self_mind_loop_token
            threading.Thread(
                target=self._self_mind_loop,
                args=(loop_token,),
                daemon=True,
                name="butler-self-mind",
            ).start()
            self._self_mind_started = True
        return True, "已重启意识循环。"

    def handle_runtime_control_command(self, workspace: str, user_prompt: str) -> dict | None:
        text = str(user_prompt or "").strip()
        if not text:
            return None
        normalized = text.lower()
        if re.search(r"(?:^|\s)(?:重启|重新启动)(?:全部后台|后台|后台服务)(?:$|\s)", text, re.IGNORECASE):
            heartbeat_ok, heartbeat_msg = self.restart_heartbeat_service(workspace, reason="talk-restart-background")
            self_ok, self_msg = self.restart_self_mind_loop()
            return {
                "handled": True,
                "reply": "\n".join([
                    "已按对话指令重启后台。",
                    f"- heartbeat: {heartbeat_msg}",
                    f"- self_mind: {self_msg}",
                ]),
                "suppress_task_merge": True,
            }
        if re.search(r"(?:^|\s)(?:重启|重新启动)(?:心跳|heartbeat)(?:$|\s)", text, re.IGNORECASE):
            ok, msg = self.restart_heartbeat_service(workspace, reason="talk-restart-heartbeat")
            return {"handled": True, "reply": msg, "suppress_task_merge": True}
        if re.search(r"(?:^|\s)(?:重启|重新启动)(?:意识循环|self[_\s-]?mind)(?:$|\s)", text, re.IGNORECASE):
            ok, msg = self.restart_self_mind_loop()
            return {"handled": True, "reply": msg, "suppress_task_merge": True}
        if re.search(r"(?:^|\s)(?:停止|关闭)(?:心跳|heartbeat)(?:$|\s)", text, re.IGNORECASE):
            with self._heartbeat_lock:
                self._stop_heartbeat_service_locked(workspace, reason="talk-stop-heartbeat")
            return {"handled": True, "reply": "已停止 heartbeat。", "suppress_task_merge": True}
        return None

    def _start_heartbeat_service_locked(self, cfg: dict) -> None:
        heartbeat_cfg = (cfg or {}).get("heartbeat") or {}
        if not isinstance(heartbeat_cfg, dict) or not heartbeat_cfg.get("enabled"):
            return
        if self._heartbeat_started:
            return
        try:
            workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
            p = multiprocessing.Process(
                target=run_heartbeat_service_subprocess,
                args=(dict(cfg),),
                daemon=True,
                name="butler-heartbeat-service",
            )
            p.start()
            self._heartbeat_started = True
            self._heartbeat_process_started = True
            self._heartbeat_process = p
            self._write_heartbeat_pid_file(workspace, int(p.pid or 0))
            self._write_heartbeat_watchdog_state(
                workspace,
                state="running",
                heartbeat_pid=int(p.pid or 0),
                note="heartbeat sidecar started; main process owns recovery",
            )
            print(f"[心跳服务] 已启动独立子进程 PID={p.pid}（启动即首跳，后续单次计时器重挂）", flush=True)
        except Exception as e:
            print(f"[心跳服务] 启动子进程失败: {e}", flush=True)

    def _heartbeat_pid_file(self, workspace: str) -> Path:
        root = resolve_butler_root(workspace)
        return root / RUN_DIR_REL / HEARTBEAT_PID_FILE_NAME

    def _write_heartbeat_pid_file(self, workspace: str, pid: int) -> None:
        if pid <= 0:
            return
        path = self._heartbeat_pid_file(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(pid), encoding="utf-8")

    def _clear_heartbeat_pid_file(self, workspace: str) -> None:
        path = self._heartbeat_pid_file(workspace)
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass

    def _heartbeat_watchdog_state_file(self, workspace: str) -> Path:
        root = resolve_butler_root(workspace)
        return root / RUN_DIR_REL / HEARTBEAT_WATCHDOG_STATE_FILE_NAME

    def _heartbeat_run_state_file(self, workspace: str) -> Path:
        root = resolve_butler_root(workspace)
        return root / RUN_DIR_REL / HEARTBEAT_RUN_STATE_FILE_NAME

    def _main_process_state_file(self, workspace: str) -> Path:
        root = resolve_butler_root(workspace)
        return root / RUN_DIR_REL / MAIN_PROCESS_STATE_FILE_NAME

    def _write_main_process_state(self, workspace: str, state: str = "running") -> None:
        path = self._main_process_state_file(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old_payload: dict = {}
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    old_payload = raw
            except Exception:
                old_payload = {}
        payload = {
            "updated_at": now_str,
            "started_at": str(old_payload.get("started_at") or now_str),
            "state": str(state or "running").strip() or "running",
            "pid": int(os.getpid()),
        }
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _main_process_state_loop(self, workspace: str) -> None:
        while True:
            try:
                self._write_main_process_state(workspace, state="running")
            except Exception:
                pass
            time.sleep(MAIN_PROCESS_STATE_HEARTBEAT_SECONDS)

    def _write_heartbeat_run_state(
        self,
        workspace: str,
        run_id: str,
        state: str,
        phase: str,
        note: str = "",
        error: str = "",
        traceback_text: str = "",
    ) -> None:
        path = self._heartbeat_run_state_file(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_id": str(run_id or "").strip(),
            "state": str(state or "unknown").strip() or "unknown",
            "phase": str(phase or "unknown").strip() or "unknown",
            "heartbeat_pid": int(os.getpid()),
            "note": str(note or "").strip()[:500],
            "error": str(error or "").strip()[:1000],
            "traceback": str(traceback_text or "").strip()[:6000],
        }
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _write_heartbeat_watchdog_state(
        self,
        workspace: str,
        state: str,
        heartbeat_pid: int = 0,
        cooldown_until_epoch: float = 0.0,
        restart_inhibit_until_epoch: float = 0.0,
        last_exit_code: int | None = None,
        note: str = "",
    ) -> None:
        path = self._heartbeat_watchdog_state_file(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "state": str(state or "unknown").strip() or "unknown",
            "heartbeat_pid": int(heartbeat_pid or 0),
            "cooldown_until_epoch": float(cooldown_until_epoch or 0.0),
            "cooldown_until": datetime.fromtimestamp(cooldown_until_epoch).strftime("%Y-%m-%d %H:%M:%S") if cooldown_until_epoch and cooldown_until_epoch > 0 else "",
            "restart_inhibit_until_epoch": float(restart_inhibit_until_epoch or 0.0),
            "restart_inhibit_until": datetime.fromtimestamp(restart_inhibit_until_epoch).strftime("%Y-%m-%d %H:%M:%S") if restart_inhibit_until_epoch and restart_inhibit_until_epoch > 0 else "",
        }
        if last_exit_code is not None:
            payload["last_exit_code"] = int(last_exit_code)
        if note:
            payload["note"] = str(note).strip()[:300]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_heartbeat_watchdog_state(self, workspace: str) -> dict:
        return self._load_json_store(self._heartbeat_watchdog_state_file(workspace), lambda: {})

    def _heartbeat_restart_handover_deadline(self, watchdog_state: dict) -> float:
        try:
            return float((watchdog_state or {}).get("restart_inhibit_until_epoch") or 0.0)
        except Exception:
            return 0.0

    def _heartbeat_restart_handover_active(self, watchdog_state: dict, now: float | None = None) -> bool:
        mode = str((watchdog_state or {}).get("state") or "").strip().lower()
        current = time.time() if now is None else float(now)
        return mode == "restart-requested" and current < self._heartbeat_restart_handover_deadline(watchdog_state)

    def _mark_heartbeat_restart_handover(self, workspace: str, reason: str = "") -> float:
        handover_until = time.time() + HEARTBEAT_RESTART_HANDOVER_SECONDS
        self._write_heartbeat_watchdog_state(
            workspace,
            state="restart-requested",
            heartbeat_pid=int(os.getpid()),
            restart_inhibit_until_epoch=handover_until,
            note=(reason or "heartbeat requested restart")[:160],
        )
        return handover_until

    def _heartbeat_process_watchdog_loop(self, workspace: str) -> None:
        while True:
            time.sleep(10)
            cfg = self._config_provider() or {}
            heartbeat_cfg = (cfg or {}).get("heartbeat") or {}
            if not isinstance(heartbeat_cfg, dict) or not heartbeat_cfg.get("enabled"):
                continue

            now = time.time()
            watchdog_state = self._read_heartbeat_watchdog_state(workspace)
            restart_handover_active = self._heartbeat_restart_handover_active(watchdog_state, now)
            restart_inhibit_until = self._heartbeat_restart_handover_deadline(watchdog_state)

            proc = self._heartbeat_process
            if proc is not None and proc.is_alive():
                try:
                    self._write_heartbeat_watchdog_state(workspace, state="running", heartbeat_pid=int(proc.pid or 0))
                except Exception:
                    pass
                continue

            if proc is not None and not proc.is_alive():
                try:
                    exit_code = proc.exitcode
                except Exception:
                    exit_code = None
                self._heartbeat_process = None
                self._heartbeat_started = False
                self._clear_heartbeat_pid_file(workspace)
                if restart_handover_active:
                    self._write_heartbeat_watchdog_state(
                        workspace,
                        state="restart-requested",
                        last_exit_code=exit_code,
                        restart_inhibit_until_epoch=restart_inhibit_until,
                        note="restart handover in progress",
                    )
                else:
                    self._write_heartbeat_watchdog_state(workspace, state="crashed", last_exit_code=exit_code)
                crash_hint = ""
                try:
                    run_state = self._load_json_store(self._heartbeat_run_state_file(workspace), lambda: {})
                    if isinstance(run_state, dict):
                        last_state = str(run_state.get("state") or "").strip()
                        last_phase = str(run_state.get("phase") or "").strip()
                        last_error = str(run_state.get("error") or "").strip()
                        if last_state or last_phase or last_error:
                            crash_hint = f" | last_state={last_state or 'unknown'} phase={last_phase or 'unknown'}"
                            if last_error:
                                crash_hint += f" error={last_error[:160]}"
                except Exception:
                    crash_hint = ""
                print(f"[心跳服务·看门狗] 检测到心跳子进程退出，exit={exit_code}，准备自动拉起{crash_hint}", flush=True)

            with self._heartbeat_lock:
                if not self._heartbeat_started:
                    if restart_handover_active:
                        self._write_heartbeat_watchdog_state(
                            workspace,
                            state="restart-requested",
                            restart_inhibit_until_epoch=restart_inhibit_until,
                            note="skip auto-respawn during restart handover",
                        )
                        continue
                    self._heartbeat_restart_times = [
                        t for t in self._heartbeat_restart_times
                        if now - t <= HEARTBEAT_RESTART_BURST_WINDOW_SECONDS
                    ]
                    if now < self._heartbeat_restart_cooldown_until:
                        remaining = int(self._heartbeat_restart_cooldown_until - now)
                        self._write_heartbeat_watchdog_state(
                            workspace,
                            state="cooldown",
                            cooldown_until_epoch=self._heartbeat_restart_cooldown_until,
                        )
                        print(f"[心跳服务·看门狗] 已进入冷却期，{remaining}s 后再尝试拉起", flush=True)
                        continue
                    if len(self._heartbeat_restart_times) >= HEARTBEAT_RESTART_BURST_LIMIT:
                        self._heartbeat_restart_cooldown_until = now + HEARTBEAT_RESTART_COOLDOWN_SECONDS
                        self._write_heartbeat_watchdog_state(
                            workspace,
                            state="cooldown",
                            cooldown_until_epoch=self._heartbeat_restart_cooldown_until,
                        )
                        print(
                            f"[心跳服务·看门狗] {HEARTBEAT_RESTART_BURST_WINDOW_SECONDS}s 内已重启 {len(self._heartbeat_restart_times)} 次，暂停自动拉起 {HEARTBEAT_RESTART_COOLDOWN_SECONDS}s",
                            flush=True,
                        )
                        continue
                    self._write_heartbeat_watchdog_state(workspace, state="restarting", note="main watchdog is respawning heartbeat")
                    self._start_heartbeat_service_locked(cfg)
                    self._heartbeat_restart_times.append(now)

    # ---------- startup / scheduler ----------

    def _run_startup_maintenance_once(self, config_snapshot: dict) -> None:
        workspace = (config_snapshot or {}).get("workspace_root") or os.getcwd()
        timeout = int((config_snapshot or {}).get("agent_timeout", 300))
        model = (config_snapshot or {}).get("agent_model", "auto")
        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        try:
            self._write_startup_status(workspace, {"state": "running", "run_id": run_id, "runner": "subprocess"})
            print("[启动维护子进程] 开始执行长期+短期记忆维护", flush=True)

            long_info = self._run_local_memory_maintenance_once(workspace, timeout, model, reason="startup-subprocess")
            recent_info = self._run_recent_memory_maintenance_once(workspace, timeout, model, reason="startup-subprocess")

            msg = "管家bot 已就绪，记忆维护服务已完成。"
            self._write_startup_status(
                workspace,
                {
                    "state": "completed",
                    "run_id": run_id,
                    "runner": "subprocess",
                    "notified": False,
                    "long_summary": str(long_info.get("model_summary") or "")[:200],
                    "long_files": int(long_info.get("files", 0)),
                    "long_compressed": int(long_info.get("compressed", 0)),
                    "recent_before": recent_info.get("before_count", 0),
                    "recent_after": recent_info.get("after_count", 0),
                    "compacted": bool(recent_info.get("compacted")),
                    "reflections": int(recent_info.get("reflections_count", 0)),
                },
            )
            print("[启动维护子进程] 完成，准备发送私聊总结", flush=True)
            notified = self._send_startup_private_notification(config_snapshot, msg)
            self._write_startup_status(workspace, {"notified": bool(notified)})
            print(f"[启动维护子进程] 私聊通知={'成功' if notified else '未发送/失败'}", flush=True)
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception as e:
            self._write_startup_status(workspace, {"state": "failed", "runner": "subprocess", "error": str(e)[:300]})
            print(f"[启动维护子进程失败] {e}", flush=True)
            sys.stdout.flush()
            sys.stderr.flush()


    def _startup_watchdog(self, workspace: str, timeout: int, model: str, wait_seconds: int = 45) -> None:
        time.sleep(max(5, wait_seconds))
        status = self._read_startup_status(workspace)
        if str(status.get("state") or "") == "completed":
            return
        print("[启动维护看门狗] 子进程未完成，主进程补跑长期+短期维护", flush=True)
        try:
            self._write_startup_status(workspace, {"state": "running", "runner": "watchdog"})
            long_info = self._run_local_memory_maintenance_once(workspace, timeout, model, reason="startup-watchdog")
            recent_info = self._run_recent_memory_maintenance_once(workspace, timeout, model, reason="startup-watchdog")
            cfg = self._config_provider() or {}
            msg = "管家bot 已就绪，记忆维护服务已完成。"
            self._write_startup_status(
                workspace,
                {
                    "state": "completed",
                    "runner": "watchdog",
                    "notified": False,
                    "long_summary": str(long_info.get("model_summary") or "")[:200],
                    "long_files": int(long_info.get("files", 0)),
                    "long_compressed": int(long_info.get("compressed", 0)),
                    "recent_before": recent_info.get("before_count", 0),
                    "recent_after": recent_info.get("after_count", 0),
                    "compacted": bool(recent_info.get("compacted")),
                    "reflections": int(recent_info.get("reflections_count", 0)),
                },
            )
            print("[启动维护看门狗] 补跑完成，准备发送私聊总结", flush=True)
            notified = self._send_startup_private_notification(cfg, msg)
            self._write_startup_status(workspace, {"notified": bool(notified)})
            print(f"[启动维护看门狗] 私聊通知={'成功' if notified else '未发送/失败'}", flush=True)
        except Exception as e:
            self._write_startup_status(workspace, {"state": "failed", "runner": "watchdog", "error": str(e)[:300]})
            print(f"[启动维护看门狗失败] {e}", flush=True)

    def _maintenance_loop(self, workspace: str, timeout: int, model: str) -> None:
        while True:
            try:
                time.sleep(self._seconds_to_next_maintenance(datetime.now()))
                self._run_local_memory_maintenance_once(workspace, timeout, model, reason="scheduled")
                self._run_recent_memory_maintenance_once(workspace, timeout, model, reason="scheduled")
            except Exception as e:
                print(f"[记忆维护失败] scheduled: {e}", flush=True)

    def _format_heartbeat_interval(self, heartbeat_cfg: dict) -> str:
        """返回可读的跳动频率描述，如「每5秒」「每1分钟」"""
        cfg = heartbeat_cfg or {}
        every_seconds = cfg.get("every_seconds")
        if every_seconds is not None:
            sec = max(1, int(every_seconds))
            if sec < 60:
                return f"每{sec}秒"
            return f"每{sec // 60}分{sec % 60}秒" if sec % 60 else f"每{sec // 60}分钟"
        every_minutes = max(1, int(cfg.get("every_minutes", 180)))
        return f"每{every_minutes}分钟"

    def _send_heartbeat_start_notification(self, cfg: dict, heartbeat_cfg: dict) -> None:
        """心跳启动时推送「开始跳动」初始化消息，含跳动频率。"""
        interval_text = self._format_heartbeat_interval(heartbeat_cfg)
        msg = f"** heartbeat 开始跳动 **\n\n跳动频率：{interval_text}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        receive_id = str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_KEY) or "").strip()
        receive_id_type = str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id"
        ok = self._send_private_message(
            cfg,
            msg,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            fallback_to_startup_target=True,
            heartbeat_cfg=heartbeat_cfg,
        )
        if ok:
            print(f"[心跳服务] 已发送「开始跳动」初始化消息（{interval_text}）", flush=True)
        else:
            print(f"[心跳服务] 初始化消息发送失败（不影响后续跳动）", flush=True)

    def _heartbeat_loop(self, run_immediately: bool = False) -> None:
        if run_immediately:
            cfg = self._config_provider() or {}
            heartbeat_cfg = (cfg or {}).get("heartbeat") or {}
            if isinstance(heartbeat_cfg, dict) and heartbeat_cfg.get("enabled"):
                # 推送「开始跳动」初始化消息（含跳动频率），然后立即执行首次跳动
                try:
                    self._send_heartbeat_start_notification(cfg, heartbeat_cfg)
                except Exception as e:
                    print(f"[心跳服务] 初始化消息发送异常: {e}（不影响后续）", flush=True)
                self._heartbeat_bootstrap_done = True
                try:
                    self._run_heartbeat_once(cfg, heartbeat_cfg)
                    workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
                    self._write_heartbeat_watchdog_state(
                        workspace,
                        state="running",
                        heartbeat_pid=int(os.getpid()),
                        note="heartbeat bootstrap completed",
                    )
                except Exception as e:
                    workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
                    print(f"[心跳服务] 首次立即触发失败: {e}", flush=True)
                    try:
                        self._write_heartbeat_watchdog_state(
                            workspace,
                            state="degraded",
                            heartbeat_pid=int(os.getpid()),
                            note=f"heartbeat bootstrap failed: {type(e).__name__}",
                        )
                    except Exception:
                        pass
                    try:
                        self._write_heartbeat_run_state(
                            workspace,
                            run_id=datetime.now().strftime("%Y%m%d%H%M%S") + "-bootstrap-failed",
                            state="failed",
                            phase="bootstrap",
                            note="heartbeat immediate bootstrap failed (exception caught in _heartbeat_loop)",
                            error=f"{type(e).__name__}: {e}",
                            traceback_text=traceback.format_exc(),
                        )
                    except Exception:
                        pass
                    try:
                        traceback.print_exc()
                    except Exception:
                        pass
        while True:
            cfg = self._config_provider() or {}
            heartbeat_cfg = (cfg or {}).get("heartbeat") or {}
            if not isinstance(heartbeat_cfg, dict) or not heartbeat_cfg.get("enabled"):
                time.sleep(60)
                continue
            wait_seconds = self._seconds_to_next_heartbeat(datetime.now(), heartbeat_cfg)
            print(f"[心跳服务] 下一次触发将在 {int(wait_seconds)} 秒后", flush=True)
            time.sleep(wait_seconds)
            try:
                self._run_heartbeat_once(cfg, heartbeat_cfg)
                workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
                self._write_heartbeat_watchdog_state(
                    workspace,
                    state="running",
                    heartbeat_pid=int(os.getpid()),
                    note="heartbeat round completed",
                )
            except Exception as e:
                print(f"[心跳服务] 执行失败: {e}", flush=True)
                try:
                    workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
                    self._write_heartbeat_watchdog_state(
                        workspace,
                        state="degraded",
                        heartbeat_pid=int(os.getpid()),
                        note=f"heartbeat round failed: {type(e).__name__}",
                    )
                except Exception:
                    pass
                try:
                    traceback.print_exc()
                except Exception:
                    pass

    def _run_heartbeat_once(self, cfg: dict, heartbeat_cfg: dict) -> None:
        heartbeat_start = time.perf_counter()
        t_after_plan = t_after_execute = t_after_apply = t_after_snapshot = heartbeat_start
        workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
        self._latest_runtime_cfg = dict(cfg or {})
        run_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
        phase = "bootstrap"
        self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="heartbeat round started")
        try:
            self._write_heartbeat_last_sent(workspace, sent=None)
            timeout = int((cfg or {}).get("agent_timeout", 300))
            from runtime import cli_runtime as cli_runtime_service

            planner_cli = self._heartbeat_planner_cli(heartbeat_cfg)
            planner_requested_model = str((heartbeat_cfg or {}).get("planner_model") or (heartbeat_cfg or {}).get("model") or (cfg or {}).get("agent_model", "auto") or "auto")
            planner_runtime_request = cli_runtime_service.resolve_runtime_request(
                cfg,
                {"cli": planner_cli, "source": "heartbeat_planner"},
                model_override=planner_requested_model,
            )
            planner_model = str(planner_runtime_request.get("model") or "auto")
            planner_cli = str(planner_runtime_request.get("cli") or planner_cli).strip() or planner_cli
            executor_cli = self._heartbeat_executor_cli(heartbeat_cfg)
            executor_requested_model = str((heartbeat_cfg or {}).get("executor_model") or planner_requested_model or "auto")
            executor_runtime_request = cli_runtime_service.resolve_runtime_request(
                cfg,
                {"cli": executor_cli, "source": "heartbeat_executor"},
                model_override=executor_requested_model,
            )
            executor_model = str(executor_runtime_request.get("model") or "auto")
            executor_cli = str(executor_runtime_request.get("cli") or executor_cli).strip() or executor_cli
            message = str((heartbeat_cfg or {}).get("message") or "").strip()

            phase = "plan"
            planner_timeout = self._resolve_heartbeat_planner_timeout(heartbeat_cfg, timeout)
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note=f"planner_cli={planner_cli}, planner_model={planner_model}, planner_timeout={planner_timeout}")
            if self._debug_receipts_enabled(cfg, scope="heartbeat"):
                planning_notice = self._build_heartbeat_planning_receipt_text(planner_timeout)
                self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase="notify-start", note="send heartbeat planning receipt")
                planning_notified = self._send_private_message(
                    cfg,
                    planning_notice,
                    receive_id=str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_KEY) or "").strip(),
                    receive_id_type=str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id",
                    fallback_to_startup_target=True,
                    heartbeat_cfg=heartbeat_cfg,
                )
                self._write_heartbeat_last_sent(workspace, sent=bool(planning_notified))
                print(f"[心跳服务] 规划起始回执{'成功' if planning_notified else '失败/跳过'}", flush=True)
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note=f"planner_cli={planner_cli}, planner_model={planner_model}, planner_timeout={planner_timeout}")
            plan = self._plan_heartbeat_action(cfg, heartbeat_cfg, workspace, timeout, planner_model, planner_timeout)
            t_after_plan = time.perf_counter()
            max_parallel = self._resolve_heartbeat_parallel_limit(heartbeat_cfg)
            branch_timeout = self._resolve_heartbeat_branch_timeout(heartbeat_cfg, timeout)

            if self._debug_receipts_enabled(cfg, scope="heartbeat") and self._should_emit_heartbeat_progress_receipt(plan):
                progress_message = self._build_heartbeat_progress_receipt_text(
                    plan,
                    planner_seconds=t_after_plan - heartbeat_start,
                    max_parallel=max_parallel,
                    branch_timeout=branch_timeout,
                )
                phase = "notify-progress"
                self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="send heartbeat progress receipt")
                progress_notified = self._send_private_message(
                    cfg,
                    progress_message,
                    receive_id=str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_KEY) or "").strip(),
                    receive_id_type=str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id",
                    fallback_to_startup_target=True,
                    heartbeat_cfg=heartbeat_cfg,
                )
                self._write_heartbeat_last_sent(workspace, sent=bool(progress_notified))
                print(f"[心跳服务] 规划进度回执{'成功' if progress_notified else '失败/跳过'}", flush=True)

            phase = "execute"
            self._write_heartbeat_run_state(
                workspace,
                run_id=run_id,
                state="running",
                phase=phase,
                note=f"executor_cli={executor_cli}, executor_model={executor_model}, max_parallel={max_parallel}, branch_timeout={branch_timeout}",
            )
            execution_result, branch_results = self._execute_heartbeat_plan(
                plan,
                workspace,
                timeout,
                executor_model,
                max_parallel,
                branch_timeout,
            )
            t_after_execute = time.perf_counter()

            phase = "apply"
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="apply heartbeat plan")
            self._apply_heartbeat_plan(workspace, plan, execution_result, branch_results)
            t_after_apply = time.perf_counter()

            phase = "snapshot"
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="persist heartbeat snapshot")
            self._persist_heartbeat_snapshot_to_recent(workspace, plan, branch_results, execution_result, max_parallel)
            t_after_snapshot = time.perf_counter()

            plan_message = str(plan.get("user_message") or "").strip()
            if plan_message:
                message = plan_message
            if execution_result.strip():
                message = (message + "\n\n" + execution_result.strip()).strip() if message else execution_result.strip()
            if not message:
                message = f"管家bot 心跳正常，时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            total_seconds = time.perf_counter() - heartbeat_start
            t_after_build = time.perf_counter()
            seg_plan = t_after_plan - heartbeat_start
            seg_exec = t_after_execute - t_after_plan
            seg_apply = t_after_apply - t_after_execute
            seg_snapshot = t_after_snapshot - t_after_apply
            seg_build = t_after_build - t_after_snapshot
            timing_line = (
                "⏱ **本轮回执**：总 {total:.1f}s | 规划 {plan:.1f}s → 执行 {exec:.1f}s → 应用 {apply:.1f}s → 持久化快照 {snap:.1f}s → 拼消息 {build:.1f}s".format(
                    total=total_seconds, plan=seg_plan, exec=seg_exec, apply=seg_apply, snap=seg_snapshot, build=seg_build
                )
            )
            message = (message + "\n\n" + timing_line).strip()

            phase = "notify"
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="send heartbeat private message")
            receive_id = str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_KEY) or "").strip()
            receive_id_type = str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id"
            notified = self._send_private_message(
                cfg,
                message,
                receive_id=receive_id,
                receive_id_type=receive_id_type,
                fallback_to_startup_target=True,
                heartbeat_cfg=heartbeat_cfg,
            )
            self._write_heartbeat_last_sent(workspace, sent=bool(notified))
            if notified:
                payload = self._load_heartbeat_memory(workspace)
                payload["last_heartbeat_sent_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_heartbeat_memory(workspace, payload)
            print(f"[心跳服务] 本次触发{'成功' if notified else '失败/跳过'}", flush=True)

            phase = "restart-check"
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="check restart markers")
            self._check_and_perform_restart(workspace)
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="completed", phase="done", note=f"notified={bool(notified)}")
        except BaseException as exc:
            self._write_heartbeat_run_state(
                workspace,
                run_id=run_id,
                state="failed",
                phase=phase,
                error=f"{type(exc).__name__}: {exc}",
                traceback_text=traceback.format_exc(),
            )
            raise

    def _resolve_heartbeat_parallel_limit(self, heartbeat_cfg: dict) -> int:
        return self._heartbeat_orchestrator.resolve_parallel_limit(heartbeat_cfg)

    def _resolve_heartbeat_branch_timeout(self, heartbeat_cfg: dict, agent_timeout: int) -> int:
        return self._heartbeat_orchestrator.resolve_branch_timeout(heartbeat_cfg, agent_timeout)

    def _resolve_heartbeat_planner_timeout(self, heartbeat_cfg: dict, agent_timeout: int) -> int:
        return self._heartbeat_orchestrator.resolve_planner_timeout(heartbeat_cfg, agent_timeout)

    def _resolve_heartbeat_planner_min_interval(self, heartbeat_cfg: dict) -> int:
        return self._heartbeat_orchestrator.resolve_planner_min_interval(heartbeat_cfg)

    def _heartbeat_prompt_path(self, workspace: str) -> Path:
        return resolve_butler_root(workspace or os.getcwd()) / HEARTBEAT_PROMPT_REL

    def _load_heartbeat_prompt_template(self, workspace: str) -> str:
        path = self._heartbeat_prompt_path(workspace)
        try:
            content = path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            pass
        return DEFAULT_HEARTBEAT_PROMPT_TEMPLATE

    def _load_markdown_excerpt(self, path: Path, max_chars: int) -> str:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n..."

    def _load_butler_soul_excerpt(self, workspace: str, max_chars: int = 2200) -> str:
        return self._load_markdown_excerpt(resolve_butler_root(workspace or os.getcwd()) / BUTLER_SOUL_FILE_REL, max_chars=max_chars)

    def _load_butler_main_agent_excerpt(self, workspace: str, max_chars: int = 2200) -> str:
        return self._load_markdown_excerpt(resolve_butler_root(workspace or os.getcwd()) / BUTLER_MAIN_AGENT_ROLE_FILE_REL, max_chars=max_chars)

    def _load_current_user_profile_excerpt(self, workspace: str, max_chars: int = 1400) -> str:
        root = resolve_butler_root(workspace or os.getcwd())
        for rel_path in (CURRENT_USER_PROFILE_FILE_REL, CURRENT_USER_PROFILE_TEMPLATE_FILE_REL):
            text = self._load_markdown_excerpt(root / rel_path, max_chars=max_chars)
            if text:
                return text
        return ""

    def _load_heartbeat_role_excerpt(self, workspace: str, max_chars: int = 1800) -> str:
        root = resolve_butler_root(workspace or os.getcwd())
        base_role = self._load_markdown_excerpt(root / HEARTBEAT_PLANNER_AGENT_ROLE_FILE_REL, max_chars=max_chars)
        if not base_role:
            return ""
        return base_role[:max_chars]

    def _load_heartbeat_context_excerpt(self, workspace: str, heartbeat_cfg: dict | None = None, max_chars: int = 1800) -> str:
        root = resolve_butler_root(workspace or os.getcwd())
        context_text = self._load_markdown_excerpt(root / HEARTBEAT_PLANNER_CONTEXT_FILE_REL, max_chars=max_chars)
        if context_text:
            return context_text[:max_chars]

        legacy_text = ""
        if isinstance(heartbeat_cfg, dict):
            legacy_text = str(heartbeat_cfg.get("context_prompt") or heartbeat_cfg.get("agent_prompt") or "").strip()
        if not legacy_text:
            return "(无)"
        if len(legacy_text) <= max_chars:
            return legacy_text
        return legacy_text[:max_chars].rstrip() + "\n..."

    def _load_heartbeat_workspace_hint(self, workspace: str, max_chars: int = 2200) -> str:
        root = resolve_butler_root(workspace or os.getcwd())
        path = root / HEARTBEAT_EXECUTOR_WORKSPACE_HINT_FILE_REL
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            raw = ""
        template = raw.strip() if raw.strip() else HEARTBEAT_WORKSPACE_HINT_FALLBACK_TEMPLATE.strip()
        rendered = template.format(
            company_root=COMPANY_ROOT_TEXT,
            body_root=BODY_ROOT_TEXT,
            upgrade_request=UPGRADE_REQUEST_TEXT,
        ).strip()
        if len(rendered) <= max_chars:
            return rendered + "\n\n"
        return rendered[:max_chars].rstrip() + "\n...\n\n"

    def _load_subagent_role_excerpt(self, workspace: str, agent_role: str, max_chars: int = 1400) -> str:
        role_name = str(agent_role or "").strip()
        if not role_name or role_name == "executor":
            rel_path = HEARTBEAT_EXECUTOR_AGENT_ROLE_FILE_REL
        else:
            if role_name.endswith(".md"):
                relative = role_name
            elif role_name.endswith("-agent"):
                relative = f"sub-agents/{role_name}.md"
            else:
                relative = f"sub-agents/{role_name}-agent.md"
            rel_path = Path("butler_main") / "butler_bot_agent" / "agents" / relative
        return self._load_markdown_excerpt(resolve_butler_root(workspace or os.getcwd()) / rel_path, max_chars=max_chars)

    def _parse_datetime_text(self, text: str) -> datetime | None:
        value = str(text or "").strip()
        if not value:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue
        return None

    def _load_pending_short_heartbeat_tasks(self, workspace: str) -> list[dict]:
        ledger_items = self._load_pending_heartbeat_tasks_from_ledger(workspace, long_term=False)
        if ledger_items:
            return ledger_items
        short_store = self._load_heartbeat_memory(workspace)
        tasks = short_store.get("tasks") if isinstance(short_store.get("tasks"), list) else []
        pending: list[dict] = []
        for item in tasks:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "pending").strip() or "pending"
            if status == "pending":
                pending.append(item)
        return pending

    def _load_due_long_heartbeat_tasks(self, workspace: str) -> list[dict]:
        ledger_items = self._load_pending_heartbeat_tasks_from_ledger(workspace, long_term=True)
        if ledger_items:
            return ledger_items
        now = datetime.now()
        long_store = self._load_heartbeat_long_tasks(workspace)
        tasks = long_store.get("tasks") if isinstance(long_store.get("tasks"), list) else []
        due_items: list[tuple[datetime, dict]] = []
        for item in tasks:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("enabled", True)):
                continue
            due_at = self._parse_datetime_text(str(item.get("next_due_at") or ""))
            if due_at is None or due_at > now:
                continue
            due_items.append((due_at, item))
        due_items.sort(key=lambda pair: pair[0])
        return [item for _, item in due_items]

    def _load_pending_heartbeat_tasks_from_ledger(self, workspace: str, long_term: bool) -> list[dict]:
        payload = TaskLedgerService(workspace).load()
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        now = datetime.now()
        results: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            task_type = str(item.get("task_type") or "short").strip()
            if long_term != (task_type == "long"):
                continue
            if long_term:
                if not bool(item.get("enabled", True)):
                    continue
                due_at = self._parse_datetime_text(str(item.get("next_due_at") or ""))
                if due_at is None or due_at > now:
                    continue
            else:
                status = str(item.get("status") or "pending").strip() or "pending"
                if status not in {"pending", "deferred", "in_progress"}:
                    continue
            results.append(dict(item))
        if long_term:
            results.sort(key=lambda value: str(value.get("next_due_at") or ""))
        return results[:10]

    def _build_heartbeat_planning_context(self, heartbeat_cfg: dict, workspace: str) -> HeartbeatPlanningContext:
        return self._heartbeat_orchestrator.build_planning_context(heartbeat_cfg, workspace)

    def _build_status_only_heartbeat_plan(self, reason: str, user_message: str) -> dict:
        return self._heartbeat_orchestrator.build_status_only_plan(reason, user_message)

    def _build_idle_heartbeat_status_plan(self, heartbeat_cfg: dict, context: HeartbeatPlanningContext) -> dict | None:
        return self._heartbeat_orchestrator.build_idle_status_plan(heartbeat_cfg, context)

    def _sanitize_id_list(self, values: list | tuple | set | None, limit: int = 20) -> list[str]:
        return self._heartbeat_orchestrator.sanitize_id_list(values, limit=limit)

    def _human_preview_text(self, text: str, limit: int = 140) -> str:
        return self._heartbeat_orchestrator.human_preview_text(text, limit=limit)

    def _truncate_heartbeat_message_for_send(self, text: str, limit: int = 4000) -> str:
        return self._heartbeat_orchestrator.truncate_message_for_send(text, limit=limit)

    def _normalize_plan_task_groups(self, plan: dict, max_parallel: int) -> list[dict]:
        return self._heartbeat_orchestrator.normalize_plan_task_groups(plan, max_parallel=max_parallel)

    def _run_heartbeat_branch(self, branch: dict, workspace: str, branch_timeout: int, model: str) -> dict:
        return self._heartbeat_orchestrator.run_branch(branch, workspace, branch_timeout, model)

    def _summarize_heartbeat_branch_results(self, plan: dict, branch_results: list[dict]) -> str:
        return self._heartbeat_orchestrator.summarize_branch_results(plan, branch_results)

    def _execute_heartbeat_plan(
        self,
        plan: dict,
        workspace: str,
        timeout: int,
        model: str,
        max_parallel: int,
        branch_timeout: int,
    ) -> tuple[str, list[dict]]:
        return self._heartbeat_orchestrator.execute_plan(plan, workspace, timeout, model, max_parallel, branch_timeout)

    def _persist_heartbeat_snapshot_to_recent(
        self,
        workspace: str,
        plan: dict,
        branch_results: list[dict],
        execution_result: str,
        max_parallel: int,
    ) -> None:
        self._heartbeat_orchestrator.persist_snapshot_to_recent(workspace, plan, branch_results, execution_result, max_parallel)

    # ---------- deterministic maintenance ----------

    def _build_file_manager_memory_prompt(self, local_dir: Path, reason: str) -> str:
        """构建调用 file-manager-agent 进行记忆整理的 prompt"""
        files = self._local_memory_files(local_dir)
        inventory = "\n".join(f"- {p.name} ({len(self._file_text(p))} 字符)" for p in files)
        index_path, l1_dir, l2_dir = self._local_layer_paths(local_dir)
        return (
            "你正在以 file-manager-agent 的身份执行记忆整理任务。\n\n"
            f"【角色】@{prompt_path_text(FILE_MANAGER_AGENT_ROLE_FILE_REL)}\n\n"
            "【目的】记忆整理、分类维护与追加原则：\n"
            "- 分类维护：能合并的优先合并（同主题、同类型合并到同一文件）\n"
            "- 追加原则：新的、未维护的内容优先写入 L1_summaries；特别长的原文放到 L2_details，并在 L1 留摘要与引用\n"
            "- 不要破坏 L0_index.json 的 JSON 结构；若只做轻量整理，优先整理 L1 摘要文件与未分类文件\n\n"
            f"【目标目录】{prompt_path_text(LOCAL_MEMORY_DIR_REL)}\n"
            f"【L0 索引】./{LOCAL_MEMORY_DIR_REL.as_posix()}/{index_path.name}\n"
            f"【L1 摘要目录】./{LOCAL_MEMORY_DIR_REL.as_posix()}/{l1_dir.name}\n"
            f"【L2 详情目录】./{LOCAL_MEMORY_DIR_REL.as_posix()}/{l2_dir.name}\n"
            f"【当前文件清单】\n{inventory or '(空)'}\n\n"
            f"【触发原因】{reason}\n\n"
            "请直接对上述目录内的文件执行整理操作，完成后简要回报变更摘要。"
        )

    def _run_local_memory_maintenance_once(self, workspace: str, timeout: int, model: str, reason: str) -> dict:
        with self._maintenance_lock:
            skip, status = self._should_skip_long_maintenance(workspace)
            if skip:
                remaining_seconds = max(0, int(status.get("remaining_seconds", 0)))
                remaining_minutes = max(1, (remaining_seconds + 59) // 60)
                summary = f"距离上次长期记忆整理未满 30 分钟，本次跳过，约 {remaining_minutes} 分钟后可再次执行"
                print(f"[长期记忆维护跳过] reason={reason}, remaining_seconds={remaining_seconds}", flush=True)
                return {
                    "model_ok": True,
                    "model_summary": summary,
                    "files": len(self._local_memory_files(self._ensure_memory_dirs(workspace)[2])),
                    "compressed": 0,
                    "skipped": True,
                }

            print(f"[长期记忆维护开始] reason={reason}", flush=True)
            _, _, local_dir = self._ensure_memory_dirs(workspace)
            model_summary = ""
            model_ok = False

            try:
                prompt = self._build_file_manager_memory_prompt(local_dir, reason)
                if str(reason or "").startswith("startup-"):
                    maint_timeout = min(45, max(20, timeout // 10))
                else:
                    maint_timeout = min(120, max(45, timeout // 3))
                out, ok = self._run_model_fn(prompt, workspace, maint_timeout, model)
                out_text = (out or "").strip()
                if "Aborting operation" in out_text:
                    out_text = ""
                    ok = False
                model_ok = bool(ok and out_text)
                if model_ok:
                    model_summary = out_text[:300]
                    print(f"[长期记忆维护] file-manager-agent 回报: {model_summary}", flush=True)
                else:
                    print(f"[长期记忆维护] file-manager-agent 未成功: {out_text[:200] if out_text else '无输出'}", flush=True)
            except Exception as e:
                print(f"[长期记忆维护] file-manager-agent 调用异常: {e}", flush=True)

            # 2. 兜底：强制文件数限制与超长截断
            self._enforce_local_memory_file_count(local_dir)
            compressed = 0
            for p in self._local_memory_files(local_dir):
                try:
                    txt = self._file_text(p)
                    if len(txt) > LOCAL_MAX_FILE_CHARS:
                        p.write_text(txt[:LOCAL_MAX_FILE_CHARS], encoding="utf-8")
                        compressed += 1
                except Exception as e:
                    print(f"[长期记忆维护] 压缩文件失败 {p}: {e}", flush=True)
            self._enforce_local_memory_file_count(local_dir)
            print(
                f"[长期记忆维护完成] reason={reason}, files={len(self._local_memory_files(local_dir))}, compressed={compressed}",
                flush=True,
            )
            self._write_long_maintenance_status(
                workspace,
                {
                    "state": "completed",
                    "last_completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": str(reason or ""),
                    "files": len(self._local_memory_files(local_dir)),
                    "compressed": compressed,
                },
            )
            effective_summary = model_summary or f"已完成文件数治理，当前 {len(self._local_memory_files(local_dir))} 个文件，压缩 {compressed} 个超长文件"
            return {
                "model_ok": model_ok,
                "model_summary": effective_summary,
                "files": len(self._local_memory_files(local_dir)),
                "compressed": compressed,
                "skipped": False,
            }

    def _run_recent_memory_maintenance_once(self, workspace: str, timeout: int, model: str, reason: str) -> dict:
        with self._memory_lock:
            entries = self._load_recent_entries(workspace)
            active_entries, stale_entries = self._split_stale_recent_entries(entries)
            archive_path = ""
            if stale_entries:
                archive_path = self._archive_stale_recent_entries(workspace, stale_entries, reason=f"{reason}-stale", pool=TALK_RECENT_POOL)
                entries = active_entries
            compacted_entries, info = self._compact_recent_entries_if_needed(entries, workspace, timeout, model, reason)
            info["stale_count"] = len(stale_entries)
            if archive_path:
                info["stale_archive_path"] = archive_path
            promoted_count = self._promote_recent_long_term_candidates(
                compacted_entries,
                workspace,
                reason=f"recent-maintenance:{reason}",
                max_promotions=3,
            )
            if promoted_count > 0:
                info["promoted_count"] = promoted_count
            if info.get("compacted"):
                self._save_recent_entries(workspace, compacted_entries)
            elif promoted_count > 0:
                self._save_recent_entries(workspace, compacted_entries)
            return info

    # ---------- per-turn memory ----------

    def _finalize_recent_and_local_memory(
        self,
        memory_id: str | None,
        user_prompt: str,
        assistant_reply: str,
        workspace: str,
        timeout: int,
        model: str,
        suppress_task_merge: bool = False,
    ) -> None:
        try:
            entry_id = str(memory_id or uuid.uuid4())
            provisional_entry = self._build_provisional_recent_entry(entry_id, user_prompt, assistant_reply)

            # 直接落盘后再做精炼；若当前没有 result_text，则明确走一次模型摘要覆盖。
            entry = self._summarize_turn_to_recent(user_prompt, assistant_reply, workspace, timeout, model)
            entry["memory_id"] = entry_id
            entry["status"] = "completed"
            if not assistant_reply.strip():
                entry_summary = str(entry.get("summary") or "").strip()
                if not entry_summary or entry_summary == re.sub(r"\s+", " ", (user_prompt or "").strip())[:120]:
                    entry["summary"] = str(provisional_entry.get("summary") or "").strip()[:160]
                else:
                    entry["summary"] = entry_summary[:160]

            with self._memory_lock:
                entries = self._load_recent_entries(workspace)
                consolidated = self._subconscious_service.consolidate_turn(
                    memory_id=entry_id,
                    candidate=entry,
                    user_prompt=user_prompt,
                    assistant_reply=assistant_reply,
                    existing_entries=entries,
                )
                entry = consolidated["primary_entry"]
                companion_entries = consolidated["companion_entries"]
                self._promote_entry_into_self_mind_cognition(workspace, entry, source="turn")
                replaced = self._replace_recent_entry(entries, entry_id, entry)
                if not replaced:
                    entries.append(entry)
                entries.extend(companion_entries)

                lt = entry.get("long_term_candidate") if isinstance(entry.get("long_term_candidate"), dict) else {}
                if lt.get("should_write") and lt.get("summary") and self._govern_memory_write(
                    target_path=prompt_path_text(LOCAL_MEMORY_DIR_REL / "semantic_memory.md"),
                    action_type="memory-write",
                    summary=str(lt.get("title") or "对话沉淀"),
                ):
                    action = self._upsert_local_memory(
                        workspace,
                        str(lt.get("title") or "对话沉淀"),
                        str(lt.get("summary") or ""),
                        [str(x) for x in (lt.get("keywords") or [])],
                        source_type="per-turn",
                        source_memory_id=entry_id,
                        source_reason="long_term_candidate",
                        source_topic=str(entry.get("topic") or ""),
                        source_entry=entry,
                    )
                    if action in {"write-new", "append-existing", "append-similar", "duplicate-skip"}:
                        self._mark_recent_entry_local_promoted(entry, action, source="per-turn")

                if (not suppress_task_merge) and self._govern_memory_write(
                    target_path=prompt_path_text(STATE_DIR_REL / "task_ledger.json"),
                    action_type="task-ledger-write",
                    summary=str(entry.get("topic") or "本轮任务候选"),
                ):
                    self._merge_heartbeat_tasks_from_entry(workspace, entry)

                promoted_count = self._promote_recent_long_term_candidates(
                    entries,
                    workspace,
                    reason="per-turn-sweep",
                    max_promotions=2,
                )
                entries, _ = self._compact_recent_entries_if_needed(entries, workspace, timeout, model, reason="per-turn")
                self._save_recent_entries(workspace, entries)
                self._sync_memory_backend_recent_event(workspace, entry, companion_entries)
                if promoted_count > 0:
                    print(f"[recent-promote] promoted should_write entries: {promoted_count}", flush=True)
                print(
                    f"[记忆] 短期记忆已更新，当前 {len(entries)} 条, result_text={'有' if assistant_reply.strip() else '无'}",
                    flush=True,
                )
                print(
                    f"[recent-finalized] memory_id={entry_id} | topic={str(entry.get('topic') or '')[:60]} | summary={str(entry.get('summary') or '')[:120]}",
                    flush=True,
                )
        except Exception as e:
            print(f"[记忆] 短期记忆更新失败: {e}", flush=True)

    def _write_recent_completion_fallback(
        self,
        memory_id: str | None,
        user_prompt: str,
        assistant_reply: str,
        workspace: str,
    ) -> None:
        entry_id = str(memory_id or uuid.uuid4())
        fallback_entry = self._build_provisional_recent_entry(entry_id, user_prompt, assistant_reply)
        fallback_entry["status"] = "completed"
        with self._memory_lock:
            entries = self._load_recent_entries(workspace)
            replaced = self._replace_recent_entry(entries, entry_id, fallback_entry)
            if not replaced:
                entries.append(fallback_entry)
            entries, _ = self._compact_recent_entries_if_needed(entries, workspace, 0, "", reason="per-turn-fallback")
            self._save_recent_entries(workspace, entries)
        print(
            f"[recent-fallback] memory_id={entry_id} | summary={str(fallback_entry.get('summary') or '')[:120]}",
            flush=True,
        )

    def _recover_pending_recent_entries_on_startup(self, workspace: str) -> None:
        """启动时修复可能遗留的“正在回复中”轮次，标记为中断，避免追问时误判为仍在回复。"""
        with self._memory_lock:
            entries = self._load_recent_entries(workspace)
            changed = False
            for item in entries or []:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status") or "").strip()
                if status != "replying":
                    continue
                topic = str(item.get("topic") or item.get("raw_user_prompt") or "本轮对话").strip()
                summary = str(item.get("summary") or "").strip()
                # 标记为中断状态，并补一条更可读的摘要，避免只看到“正在回复中”却不知道发生了什么。
                item["status"] = "interrupted"
                if not summary or "正在回复中" in summary:
                    item["summary"] = f"状态：上一轮对话在回复写回过程中被中断（可能是守护重启或进程退出），主题：{topic[:40]}".strip()[:160]
                next_actions = item.get("next_actions")
                if not isinstance(next_actions, list):
                    next_actions = []
                hint = "若本轮追问依赖上一轮，请简要复述上一轮的关键结论，避免记忆断片。"
                if hint not in [str(x) for x in next_actions]:
                    next_actions.append(hint)
                item["next_actions"] = next_actions
                changed = True
            if changed:
                entries, _ = self._compact_recent_entries_if_needed(
                    entries,
                    workspace,
                    0,
                    "",
                    reason="startup-recover-pending",
                )
                self._save_recent_entries(workspace, entries)
                print(f"[recent-recover] 启动时已修复 pending 记忆，共 {len(entries)} 条", flush=True)

    def _persist_recent_and_local_memory(
        self,
        user_prompt: str,
        assistant_reply: str,
        workspace: str,
        timeout: int,
        model: str,
    ) -> None:
        self._finalize_recent_and_local_memory(None, user_prompt, assistant_reply, workspace, timeout, model)

    # ---------- summarization ----------

    def _summarize_turn_to_recent(self, user_prompt: str, assistant_reply: str, workspace: str, timeout: int, model: str) -> dict:
        try:
            return self._turn_memory_service.extract_turn_candidates(user_prompt, assistant_reply, workspace, timeout, model)
        except Exception as e:
            print(f"[记忆] 提炼服务异常，使用 fallback 摘要: {e}", flush=True)
            heuristic_short_tasks, heuristic_long_tasks = self._extract_heartbeat_candidates(user_prompt, assistant_reply)
            heuristic_lt = self._heuristic_long_term_candidate(user_prompt, assistant_reply)
            summary = (assistant_reply or user_prompt or "").strip().replace("\n", " ")[:120]
            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "topic": "本轮对话",
                "summary": summary,
                "next_actions": [],
                "heartbeat_tasks": self._normalize_heartbeat_tasks([], user_prompt, heuristic_short_tasks, long_term=False),
                "heartbeat_long_term_tasks": self._normalize_heartbeat_tasks([], user_prompt, heuristic_long_tasks, long_term=True),
                "mental_notes": [],
                "relationship_signals": [],
                "context_tags": [],
                "relation_signal": {},
                "salience": 0.4,
                "active_window": "current",
                "long_term_candidate": {
                    "should_write": bool(heuristic_lt.get("should_write")),
                    "title": str(heuristic_lt.get("title") or "").strip()[:40],
                    "summary": str(heuristic_lt.get("summary") or "").strip()[:220],
                    "keywords": [str(x).strip()[:20] for x in (heuristic_lt.get("keywords") or []) if str(x).strip()][:8],
                },
            }

    def _build_provisional_recent_entry(self, entry_id: str, user_prompt: str, assistant_reply: str) -> dict:
        prompt_text = re.sub(r"\s+", " ", (user_prompt or "").strip())
        reply_text = re.sub(r"\s+", " ", (assistant_reply or "").strip())
        topic_source = prompt_text or reply_text or "本轮对话"
        if reply_text:
            summary = f"用户：{prompt_text[:60]}；助手：{reply_text[:90]}"
        else:
            summary = "状态：正在回复中"
        return {
            "memory_id": entry_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": topic_source[:18] or "本轮对话",
            "summary": summary[:160],
            "memory_scope": TALK_RECENT_POOL,
            "memory_stream": "talk",
            "event_type": "conversation_turn",
            "raw_user_prompt": prompt_text[:500],
            "status": "replying" if not reply_text else "completed",
            "next_actions": [],
            "heartbeat_tasks": [],
            "heartbeat_long_term_tasks": [],
            "salience": 0.2,
            "confidence": 0.2 if not reply_text else 0.5,
            "derived_from": ["pending-turn"],
            "context_tags": [],
            "mental_notes": [],
            "relationship_signals": [],
            "relation_signal": {},
            "active_window": "current",
            "subconscious": {"trigger_level": 0},
            "long_term_candidate": {
                "should_write": False,
                "title": "",
                "summary": "",
                "keywords": [],
            },
        }

    def _replace_recent_entry(self, entries: list[dict], entry_id: str, new_entry: dict) -> bool:
        for idx, item in enumerate(entries):
            if isinstance(item, dict) and str(item.get("memory_id") or "") == entry_id:
                entries[idx] = new_entry
                return True
        return False

    def _find_latest_pending_entry(self, entries: list[dict]) -> dict | None:
        for item in reversed(entries or []):
            if isinstance(item, dict) and str(item.get("status") or "") == "replying":
                return item
        return None

    def _expire_stale_pending_entries(self, entries: list[dict]) -> None:
        now = datetime.now()
        for item in entries or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").strip() != "replying":
                continue
            entry_time = self._parse_entry_time(item)
            if not entry_time:
                continue
            if (now - entry_time).total_seconds() < self._pending_followup_max_age_seconds(TALK_RECENT_POOL):
                continue
            topic = str(item.get("topic") or item.get("raw_user_prompt") or "本轮对话").strip()
            summary = str(item.get("summary") or "").strip()
            item["status"] = "interrupted"
            if not summary or "正在回复中" in summary:
                item["summary"] = f"状态：上一轮对话未完成并已按超时中断处理，主题：{topic[:40]}"[:160]

    def _render_pending_followup_context(self, previous_pending: dict | None, user_prompt: str) -> str:
        if not previous_pending:
            return ""
        pending_title = str(previous_pending.get("topic") or previous_pending.get("raw_user_prompt") or "").strip()
        if not pending_title:
            return ""
        current_text = re.sub(r"\s+", " ", (user_prompt or "").strip())
        return (
            "【追问上下文】上一问仍在回复中。\n"
            f"- 上一个问题：{pending_title[:120]}\n"
            f"- 用户又追问：{current_text[:160]}\n"
            "请优先回答当前追问；若当前追问依赖上一问，请带上必要衔接。"
        )

    def _heuristic_long_term_candidate(self, user_prompt: str, assistant_reply: str) -> dict:
        text = f"{user_prompt}\n{assistant_reply}"
        compact = re.sub(r"\s+", " ", (text or "").strip())
        if not compact:
            return {"should_write": False, "title": "", "summary": "", "keywords": []}
        low = compact.lower()
        if not any(h in low for h in [x.lower() for x in LONG_TERM_HINTS]):
            return {"should_write": False, "title": "", "summary": "", "keywords": []}

        title = "对话长期约束"
        if "研究管理" in compact and "工作区" in compact:
            title = "研究管理输出路径偏好"
        elif "TransferRecovery" in compact or "179" in compact:
            title = "TransferRecovery执行约束"

        kws = []
        for k in ["研究管理", "工作区", "偏好", "默认", "TransferRecovery", "179", "路径", "规则"]:
            if k.lower() in low and k not in kws:
                kws.append(k)

        return {"should_write": True, "title": title, "summary": compact[:220], "keywords": kws[:8]}

    # ---------- recent compact ----------

    def _coerce_int(self, value, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
        try:
            resolved = int(value)
        except Exception:
            resolved = int(default)
        if minimum is not None:
            resolved = max(int(minimum), resolved)
        if maximum is not None:
            resolved = min(int(maximum), resolved)
        return resolved

    def _memory_settings(self) -> dict:
        cfg = self._config_provider() or {}
        raw = cfg.get("memory")
        return raw if isinstance(raw, dict) else {}

    def _recent_settings(self, pool: str = TALK_RECENT_POOL) -> dict:
        memory_cfg = self._memory_settings()
        normalized_pool = self._normalize_recent_pool(pool)
        key = "beat_recent" if normalized_pool == BEAT_RECENT_POOL else "talk_recent"
        raw = memory_cfg.get(key)
        section = raw if isinstance(raw, dict) else {}
        if normalized_pool == BEAT_RECENT_POOL:
            defaults = {
                "prompt_visible_items": BEAT_RECENT_MAX_ITEMS,
                "prompt_max_chars": BEAT_RECENT_MAX_CHARS,
                "storage_items": 40,
                "storage_max_chars": 50000,
                "summary_chunk_size": 8,
                "max_active_summaries": 6,
                "summary_prompt_injection_limit": 2,
                "summary_history_prompt_injection_limit": 2,
                "summary_entry_char_limit": 360,
                "summary_history_windows": [
                    {"key": "10d", "label": "最近10天", "days": 10},
                    {"key": "4m", "label": "最近4个月", "days": 120},
                    {"key": "1y", "label": "最近1年", "days": 365},
                ],
                "stale_keep_talk_turns": RECENT_STALE_KEEP_TALK_TURNS,
                "stale_companion_max_age_seconds": RECENT_STALE_COMPANION_MAX_AGE_SECONDS,
                "stale_interrupted_max_age_seconds": RECENT_STALE_INTERRUPTED_MAX_AGE_SECONDS,
                "stale_promoted_max_age_seconds": RECENT_STALE_PROMOTED_MAX_AGE_SECONDS,
                "pending_followup_max_age_seconds": PENDING_FOLLOWUP_MAX_AGE_SECONDS,
            }
        else:
            defaults = {
                "prompt_visible_items": 20,
                "prompt_max_chars": 18000,
                "storage_items": 100,
                "storage_max_chars": 80000,
                "summary_chunk_size": 10,
                "max_active_summaries": 10,
                "summary_prompt_injection_limit": 3,
                "summary_history_prompt_injection_limit": 3,
                "summary_entry_char_limit": 420,
                "summary_history_windows": [
                    {"key": "10d", "label": "最近10天", "days": 10},
                    {"key": "4m", "label": "最近4个月", "days": 120},
                    {"key": "1y", "label": "最近1年", "days": 365},
                ],
                "stale_keep_talk_turns": RECENT_STALE_KEEP_TALK_TURNS,
                "stale_companion_max_age_seconds": RECENT_STALE_COMPANION_MAX_AGE_SECONDS,
                "stale_interrupted_max_age_seconds": RECENT_STALE_INTERRUPTED_MAX_AGE_SECONDS,
                "stale_promoted_max_age_seconds": RECENT_STALE_PROMOTED_MAX_AGE_SECONDS,
                "pending_followup_max_age_seconds": PENDING_FOLLOWUP_MAX_AGE_SECONDS,
            }
        return {**defaults, **section}

    def _self_mind_settings(self) -> dict:
        memory_cfg = self._memory_settings()
        raw = memory_cfg.get("self_mind")
        section = raw if isinstance(raw, dict) else {}
        defaults = {
            "enabled": True,
            "context_max_chars": 1800,
            "raw_thought_max_items": 30,
            "review_max_items": 8,
            "review_chunk_size": 4,
            "review_prompt_injection_limit": 3,
            "raw_prompt_injection_limit": 6,
            "behavior_mirror_prompt_injection_limit": 4,
            "behavior_mirror_max_chars": 1600,
            "behavior_mirror_digest_limit": 3,
            "perception_max_chars": 1800,
            "queue_max_items": 12,
            "cognition_max_chars": 1800,
            "cognition_prompt_injection_limit": 4,
            "cognition_signal_limit_per_category": 12,
            "cycle_interval_seconds": 10,
            "cycle_timeout_seconds": 180,
            "cycle_model": "auto",
            "bridge_prompt_injection_limit": 3,
            "bridge_max_items": 8,
            "bridge_review_interval_seconds": 6 * 60 * 60,
            "bridge_expire_seconds": 3 * 24 * 60 * 60,
            "direct_talk_enabled": True,
            "direct_talk_min_interval_seconds": 180,
            "direct_talk_priority_threshold": 0,
            "direct_talk_recent_talk_defer_seconds": 45,
            "heartbeat_handoff_priority_threshold": 55,
            "cognitive_categories": [
                {
                    "slug": "values",
                    "title": "价值观",
                    "description": "较稳定的判断底色、取舍方式与长期相信的东西。",
                    "keywords": ["价值", "判断", "原则", "相信", "长期", "底色", "排序"],
                },
                {
                    "slug": "habits",
                    "title": "习惯",
                    "description": "反复出现的节律、偏好的做事方式与惯性行为。",
                    "keywords": ["习惯", "经常", "总是", "每天", "晚上", "节律", "惯性"],
                },
                {
                    "slug": "preferences",
                    "title": "喜好",
                    "description": "对用户、表达、互动、环境与体验的偏好。",
                    "keywords": ["喜欢", "偏好", "更想", "倾向", "风格", "语气", "喜好"],
                },
                {
                    "slug": "skills",
                    "title": "技能树",
                    "description": "已经掌握、正在学习或明显缺失的能力结构。",
                    "keywords": ["技能", "能力", "学会", "掌握", "skill", "mcp", "工具"],
                },
                {
                    "slug": "risk_boundaries",
                    "title": "风险边界",
                    "description": "不该做什么、何时要停、要申请审批或提醒风险的边界。",
                    "keywords": ["风险", "边界", "不能", "不要", "审批", "禁止", "高风险"],
                },
                {
                    "slug": "user_model",
                    "title": "用户模型",
                    "description": "对当前用户节奏、偏好、关系温度与协作方式的抽象理解。",
                    "keywords": ["用户", "你", "对方", "偏好", "关系", "期待", "画像"],
                },
                {
                    "slug": "self_model",
                    "title": "自我模型",
                    "description": "对自己当前状态、成长方向、主线与自我理解的抽象化总结。",
                    "keywords": ["我", "自己", "self", "主线", "成长", "自我", "意识"],
                },
            ],
        }
        return {**defaults, **section}

    def _local_memory_settings(self) -> dict:
        memory_cfg = self._memory_settings()
        raw = memory_cfg.get("local_memory")
        section = raw if isinstance(raw, dict) else {}
        defaults = {
            "maintenance_min_interval_seconds": LONG_MAINTENANCE_MIN_INTERVAL_SECONDS,
            "l1_max_files": LOCAL_L1_MAX_FILES,
            "l2_detail_trigger_chars": LOCAL_L2_DETAIL_TRIGGER_CHARS,
            "l2_summary_preview_chars": LOCAL_L2_SUMMARY_PREVIEW_CHARS,
        }
        return {**defaults, **section}

    def _recent_storage_max_items(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        prompt_items = self._coerce_int(settings.get("prompt_visible_items"), TALK_RECENT_MAX_ITEMS, minimum=1, maximum=200)
        return self._coerce_int(settings.get("storage_items"), max(prompt_items, 40), minimum=prompt_items, maximum=500)

    def _recent_max_items(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = BEAT_RECENT_MAX_ITEMS if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else TALK_RECENT_MAX_ITEMS
        return self._coerce_int(settings.get("prompt_visible_items"), default, minimum=1, maximum=200)

    def _recent_max_chars(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = BEAT_RECENT_MAX_CHARS if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else TALK_RECENT_MAX_CHARS
        return self._coerce_int(settings.get("prompt_max_chars"), default, minimum=800, maximum=200000)

    def _recent_storage_max_chars(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = 50000 if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else 80000
        prompt_chars = self._recent_max_chars(pool)
        return self._coerce_int(settings.get("storage_max_chars"), default, minimum=prompt_chars, maximum=500000)

    def _recent_summary_chunk_size(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = 8 if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else 10
        return self._coerce_int(settings.get("summary_chunk_size"), default, minimum=2, maximum=30)

    def _recent_summary_max_active(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = 6 if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else 10
        return self._coerce_int(settings.get("max_active_summaries"), default, minimum=1, maximum=50)

    def _recent_summary_prompt_limit(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = 2 if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else 3
        return self._coerce_int(settings.get("summary_prompt_injection_limit"), default, minimum=0, maximum=10)

    def _recent_summary_entry_char_limit(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = 360 if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else 420
        return self._coerce_int(settings.get("summary_entry_char_limit"), default, minimum=120, maximum=2000)

    def _recent_summary_history_prompt_limit(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        default = 2 if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else 3
        return self._coerce_int(settings.get("summary_history_prompt_injection_limit"), default, minimum=0, maximum=10)

    def _recent_summary_history_windows(self, pool: str = TALK_RECENT_POOL) -> list[dict]:
        raw_windows = self._recent_settings(pool).get("summary_history_windows")
        defaults = [
            {"key": "10d", "label": "最近10天", "days": 10},
            {"key": "4m", "label": "最近4个月", "days": 120},
            {"key": "1y", "label": "最近1年", "days": 365},
        ]
        windows = raw_windows if isinstance(raw_windows, list) else defaults
        normalized = []
        for index, item in enumerate(windows):
            if not isinstance(item, dict):
                continue
            days = self._coerce_int(item.get("days"), defaults[min(index, len(defaults) - 1)].get("days", 30), minimum=1, maximum=3650)
            label = str(item.get("label") or f"最近{days}天").strip() or f"最近{days}天"
            key = str(item.get("key") or f"window_{index + 1}").strip() or f"window_{index + 1}"
            normalized.append({"key": key[:24], "label": label[:24], "days": days})
        return normalized or defaults

    def _pending_followup_max_age_seconds(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        return self._coerce_int(settings.get("pending_followup_max_age_seconds"), PENDING_FOLLOWUP_MAX_AGE_SECONDS, minimum=60, maximum=86400)

    def _recent_stale_keep_talk_turns(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        return self._coerce_int(settings.get("stale_keep_talk_turns"), RECENT_STALE_KEEP_TALK_TURNS, minimum=1, maximum=50)

    def _recent_stale_companion_max_age_seconds(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        return self._coerce_int(settings.get("stale_companion_max_age_seconds"), RECENT_STALE_COMPANION_MAX_AGE_SECONDS, minimum=60, maximum=604800)

    def _recent_stale_interrupted_max_age_seconds(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        return self._coerce_int(settings.get("stale_interrupted_max_age_seconds"), RECENT_STALE_INTERRUPTED_MAX_AGE_SECONDS, minimum=60, maximum=604800)

    def _recent_stale_promoted_max_age_seconds(self, pool: str = TALK_RECENT_POOL) -> int:
        settings = self._recent_settings(pool)
        return self._coerce_int(settings.get("stale_promoted_max_age_seconds"), RECENT_STALE_PROMOTED_MAX_AGE_SECONDS, minimum=60, maximum=604800)

    def _self_mind_context_max_chars(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("context_max_chars"), 1800, minimum=400, maximum=12000)

    def _self_mind_raw_max_items(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("raw_thought_max_items"), 30, minimum=5, maximum=200)

    def _self_mind_review_max_items(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("review_max_items"), 8, minimum=1, maximum=50)

    def _self_mind_review_chunk_size(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("review_chunk_size"), 4, minimum=2, maximum=20)

    def _self_mind_review_prompt_limit(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("review_prompt_injection_limit"), 3, minimum=0, maximum=10)

    def _self_mind_raw_prompt_limit(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("raw_prompt_injection_limit"), 6, minimum=0, maximum=20)

    def _self_mind_behavior_mirror_prompt_limit(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("behavior_mirror_prompt_injection_limit"), 4, minimum=0, maximum=10)

    def _self_mind_behavior_mirror_max_chars(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("behavior_mirror_max_chars"), 1600, minimum=300, maximum=12000)

    def _self_mind_behavior_mirror_digest_limit(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("behavior_mirror_digest_limit"), 3, minimum=0, maximum=10)

    def _self_mind_perception_max_chars(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("perception_max_chars"), 1800, minimum=400, maximum=12000)

    def _self_mind_queue_max_items(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("queue_max_items"), 12, minimum=3, maximum=100)

    def _self_mind_cognition_max_chars(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("cognition_max_chars"), 1800, minimum=400, maximum=12000)

    def _self_mind_cognition_prompt_limit(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("cognition_prompt_injection_limit"), 4, minimum=1, maximum=12)

    def _self_mind_cognition_signal_limit_per_category(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("cognition_signal_limit_per_category"), 12, minimum=3, maximum=50)

    def _self_mind_cognitive_categories(self) -> list[dict]:
        raw = self._self_mind_settings().get("cognitive_categories")
        candidates = raw if isinstance(raw, list) else []
        normalized: list[dict] = []
        for index, item in enumerate(candidates):
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or f"category_{index + 1}").strip().lower()
            title = str(item.get("title") or slug).strip() or slug
            description = str(item.get("description") or "").strip()
            keywords = [
                str(value).strip().lower()
                for value in (item.get("keywords") or [])
                if str(value).strip()
            ][:12]
            normalized.append(
                {
                    "slug": slug[:40],
                    "title": title[:40],
                    "description": description[:120],
                    "keywords": keywords,
                }
            )
        return normalized

    def _self_mind_enabled(self) -> bool:
        raw = self._self_mind_settings().get("enabled")
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(raw)

    def _self_mind_cycle_interval_seconds(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("cycle_interval_seconds"), 10, minimum=10, maximum=86400)

    def _self_mind_cycle_timeout_seconds(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("cycle_timeout_seconds"), 180, minimum=20, maximum=1200)

    def _self_mind_cycle_model(self) -> str:
        value = str(self._self_mind_settings().get("cycle_model") or "auto").strip()
        return value or "auto"

    def _self_mind_cycle_cli(self) -> str:
        value = str(self._self_mind_settings().get("cycle_cli") or "cursor").strip().lower()
        return "codex" if value in {"codex", "codex-cli"} else "cursor"

    def _heartbeat_planner_cli(self, heartbeat_cfg: dict | None = None) -> str:
        value = str(((heartbeat_cfg or {}).get("planner_cli")) or "cursor").strip().lower()
        return "codex" if value in {"codex", "codex-cli"} else "cursor"

    def _heartbeat_executor_cli(self, heartbeat_cfg: dict | None = None) -> str:
        value = str(((heartbeat_cfg or {}).get("executor_cli")) or "cursor").strip().lower()
        return "codex" if value in {"codex", "codex-cli"} else "cursor"

    def _self_mind_body_loop_enabled(self) -> bool:
        raw = self._self_mind_settings().get("body_loop_enabled")
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(raw)

    def _debug_receipts_enabled(self, cfg: dict | None = None, scope: str = "") -> bool:
        payload = cfg if isinstance(cfg, dict) else (self._config_provider() or {})
        features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
        keys = ["debug_receipts"]
        if str(scope or "").strip():
            keys.insert(0, f"{str(scope).strip()}_debug_receipts")
        for key in keys:
            raw = features.get(key)
            if raw is None:
                continue
            if isinstance(raw, str):
                return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
            return bool(raw)
        return False

    def _self_mind_bridge_prompt_limit(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("bridge_prompt_injection_limit"), 3, minimum=0, maximum=10)

    def _self_mind_bridge_max_items(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("bridge_max_items"), 8, minimum=1, maximum=50)

    def _self_mind_bridge_review_interval_seconds(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("bridge_review_interval_seconds"), 6 * 60 * 60, minimum=300, maximum=30 * 24 * 60 * 60)

    def _self_mind_bridge_expire_seconds(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("bridge_expire_seconds"), 3 * 24 * 60 * 60, minimum=3600, maximum=180 * 24 * 60 * 60)

    def _self_mind_direct_talk_enabled(self) -> bool:
        raw = self._self_mind_settings().get("direct_talk_enabled")
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(raw)

    def _self_mind_direct_talk_min_interval_seconds(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("direct_talk_min_interval_seconds"), 1800, minimum=0, maximum=86400)

    def _self_mind_direct_talk_priority_threshold(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("direct_talk_priority_threshold"), 72, minimum=0, maximum=100)

    def _self_mind_direct_talk_recent_talk_defer_seconds(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("direct_talk_recent_talk_defer_seconds"), 45, minimum=0, maximum=3600)

    def _self_mind_heartbeat_handoff_priority_threshold(self) -> int:
        return self._coerce_int(self._self_mind_settings().get("heartbeat_handoff_priority_threshold"), 55, minimum=0, maximum=100)

    def _long_maintenance_min_interval_seconds(self) -> int:
        settings = self._local_memory_settings()
        return self._coerce_int(settings.get("maintenance_min_interval_seconds"), LONG_MAINTENANCE_MIN_INTERVAL_SECONDS, minimum=60, maximum=86400)

    def _local_l1_max_files(self) -> int:
        settings = self._local_memory_settings()
        return self._coerce_int(settings.get("l1_max_files"), LOCAL_L1_MAX_FILES, minimum=10, maximum=500)

    def _local_l2_detail_trigger_chars(self) -> int:
        settings = self._local_memory_settings()
        return self._coerce_int(settings.get("l2_detail_trigger_chars"), LOCAL_L2_DETAIL_TRIGGER_CHARS, minimum=80, maximum=10000)

    def _local_l2_summary_preview_chars(self) -> int:
        settings = self._local_memory_settings()
        return self._coerce_int(settings.get("l2_summary_preview_chars"), LOCAL_L2_SUMMARY_PREVIEW_CHARS, minimum=60, maximum=2000)

    def _recent_stale_archive_dir(self, workspace: str, pool: str = TALK_RECENT_POOL) -> Path:
        recent_dir, _ = self._recent_pool_paths(workspace, pool)
        return recent_dir / RECENT_STALE_DIR_NAME / datetime.now().strftime("%Y-%m")

    def _is_recent_entry_stale(self, item: dict, keep_source_ids: set[str], now: datetime) -> bool:
        if not isinstance(item, dict):
            return False
        status = str(item.get("status") or "").strip().lower()
        if status == "replying":
            return False
        entry_time = self._parse_entry_time(item)
        if not entry_time:
            return False
        age_seconds = (now - entry_time).total_seconds()
        stream = str(item.get("memory_stream") or "talk").strip()
        active_window = str(item.get("active_window") or "recent").strip().lower()
        derived_from = {str(value).strip() for value in (item.get("derived_from") or []) if str(value).strip()}
        long_term_candidate = item.get("long_term_candidate") if isinstance(item.get("long_term_candidate"), dict) else {}
        promoted_at = self._parse_datetime_text(str(long_term_candidate.get("promoted_to_local_at") or ""))

        if status == "interrupted" and age_seconds >= self._recent_stale_interrupted_max_age_seconds(TALK_RECENT_POOL):
            return True

        if stream in {"mental", "relationship_signal", "task_signal"}:
            if keep_source_ids & derived_from:
                return False
            if promoted_at:
                return True
            companion_age = self._recent_stale_companion_max_age_seconds(TALK_RECENT_POOL)
            if active_window != "current" and age_seconds >= companion_age:
                return True
            if age_seconds >= companion_age * 2:
                return True

        promoted_age = self._recent_stale_promoted_max_age_seconds(TALK_RECENT_POOL)
        if stream == "talk" and promoted_at and age_seconds >= promoted_age * 2:
            return True

        return False

    def _split_stale_recent_entries(self, entries: list[dict]) -> tuple[list[dict], list[dict]]:
        now = datetime.now()
        keep_source_ids: set[str] = set()
        kept_talk_turns = 0
        for item in reversed(entries or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("memory_stream") or "talk").strip() != "talk":
                continue
            if str(item.get("event_type") or "").strip() != "conversation_turn":
                continue
            memory_id = str(item.get("memory_id") or "").strip()
            if memory_id:
                keep_source_ids.add(memory_id)
            kept_talk_turns += 1
            if kept_talk_turns >= self._recent_stale_keep_talk_turns(TALK_RECENT_POOL):
                break

        active_entries: list[dict] = []
        stale_entries: list[dict] = []
        for item in entries or []:
            if self._is_recent_entry_stale(item, keep_source_ids, now):
                stale_entries.append(item)
            else:
                active_entries.append(item)
        return active_entries, stale_entries

    def _archive_stale_recent_entries(self, workspace: str, stale_entries: list[dict], reason: str, pool: str = TALK_RECENT_POOL) -> str:
        if not stale_entries:
            return ""
        archive_dir = self._recent_stale_archive_dir(workspace, pool)
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"recent_memory_stale_{self._normalize_recent_pool(pool)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        payload = {
            "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": str(reason or "stale-recent-cleanup").strip() or "stale-recent-cleanup",
            "pool": self._normalize_recent_pool(pool),
            "count": len(stale_entries),
            "entries": stale_entries,
        }
        archive_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        preview_lines = []
        for item in stale_entries[:12]:
            ts = str(item.get("timestamp") or "").strip()
            topic = str(item.get("topic") or item.get("memory_stream") or "未命名条目").strip()
            summary = str(item.get("summary") or "").strip()
            preview_lines.append(f"- [{ts}] {topic}: {summary[:100]}")
        preview_lines.append(f"- 归档文件: {archive_path.name}")
        self._append_recent_archive(workspace, f"过时 recent 归档({self._normalize_recent_pool(pool)}/{reason})", "\n".join(preview_lines), pool=pool)
        return str(archive_path)

    def _recent_summary_pool_path(self, workspace: str, pool: str = TALK_RECENT_POOL) -> Path:
        recent_dir, _ = self._recent_pool_paths(workspace, pool)
        return recent_dir / RECENT_SUMMARY_POOL_FILE

    def _recent_summary_archive_path(self, workspace: str, pool: str = TALK_RECENT_POOL) -> Path:
        recent_dir, _ = self._recent_pool_paths(workspace, pool)
        return recent_dir / RECENT_SUMMARY_ARCHIVE_FILE

    def _recent_summary_ladder_path(self, workspace: str, pool: str = TALK_RECENT_POOL) -> Path:
        recent_dir, _ = self._recent_pool_paths(workspace, pool)
        return recent_dir / RECENT_SUMMARY_LADDER_FILE

    def _load_recent_summary_pool(self, workspace: str, pool: str = TALK_RECENT_POOL) -> list[dict]:
        path = self._recent_summary_pool_path(workspace, pool)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            pass
        return []

    def _save_recent_summary_pool(self, workspace: str, summaries: list[dict], pool: str = TALK_RECENT_POOL) -> None:
        path = self._recent_summary_pool_path(workspace, pool)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([item for item in summaries if isinstance(item, dict)], ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_recent_summary_archive(self, workspace: str, archived_items: list[dict], *, reason: str, pool: str = TALK_RECENT_POOL) -> None:
        if not archived_items:
            return
        path = self._recent_summary_archive_path(workspace, pool)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": str(reason or "summary-pool-rollover").strip() or "summary-pool-rollover",
            "pool": self._normalize_recent_pool(pool),
            "count": len(archived_items),
            "items": archived_items,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_recent_summary_archive_items(self, workspace: str, pool: str = TALK_RECENT_POOL) -> list[dict]:
        path = self._recent_summary_archive_path(workspace, pool)
        if not path.exists():
            return []
        items: list[dict] = []
        try:
            with path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    chunk = record.get("items") if isinstance(record, dict) else None
                    if isinstance(chunk, list):
                        items.extend(item for item in chunk if isinstance(item, dict))
        except Exception:
            return []
        return items

    def _load_recent_summary_ladder(self, workspace: str, pool: str = TALK_RECENT_POOL) -> list[dict]:
        return self._load_json_list_file(self._recent_summary_ladder_path(workspace, pool))

    def _save_recent_summary_ladder(self, workspace: str, payload: list[dict], pool: str = TALK_RECENT_POOL) -> None:
        self._save_json_list_file(self._recent_summary_ladder_path(workspace, pool), payload)

    def _summary_item_time(self, item: dict) -> datetime | None:
        if not isinstance(item, dict):
            return None
        return (
            self._parse_datetime_text(str(item.get("end_timestamp") or ""))
            or self._parse_datetime_text(str(item.get("updated_at") or ""))
            or self._parse_datetime_text(str(item.get("start_timestamp") or ""))
        )

    def _build_recent_summary_history_bucket(self, label: str, key: str, days: int, items: list[dict]) -> dict | None:
        if not items:
            return None
        ordered = sorted(
            [item for item in items if isinstance(item, dict)],
            key=lambda item: str(item.get("end_timestamp") or item.get("start_timestamp") or item.get("updated_at") or ""),
        )
        if not ordered:
            return None
        titles = []
        detail_points = []
        unresolved = []
        self_mind_cues = []
        keywords = []
        scene_modes = []
        for item in ordered:
            title = str(item.get("title") or "").strip()
            if title and title not in titles:
                titles.append(title)
            scene_mode = str(item.get("scene_mode") or "mixed").strip() or "mixed"
            if scene_mode not in scene_modes:
                scene_modes.append(scene_mode)
            for value in (item.get("detail_points") or []):
                text = str(value).strip()
                if text and text not in detail_points:
                    detail_points.append(text)
            for value in (item.get("unresolved_points") or []):
                text = str(value).strip()
                if text and text not in unresolved:
                    unresolved.append(text)
            for value in (item.get("self_mind_cues") or []):
                text = str(value).strip()
                if text and text not in self_mind_cues:
                    self_mind_cues.append(text)
            for value in (item.get("keywords") or []):
                text = str(value).strip()
                if text and text not in keywords:
                    keywords.append(text)
        summary_parts = []
        if titles:
            summary_parts.append("主线:" + "；".join(titles[:3]))
        if detail_points:
            summary_parts.append("反复出现:" + "；".join(detail_points[:3]))
        if unresolved:
            summary_parts.append("持续未收口:" + "；".join(unresolved[:2]))
        if self_mind_cues:
            summary_parts.append("值得回想:" + "；".join(self_mind_cues[:2]))
        summary = " | ".join(summary_parts).strip() or f"{label} 内累计 {len(ordered)} 个 recent summary 窗口。"
        first = ordered[0]
        last = ordered[-1]
        return {
            "bucket_key": key,
            "label": label,
            "days": int(days),
            "summary": summary[:700],
            "titles": titles[:6],
            "detail_points": detail_points[:6],
            "unresolved_points": unresolved[:4],
            "self_mind_cues": self_mind_cues[:4],
            "keywords": keywords[:10],
            "scene_modes": scene_modes[:5],
            "window_count": len(ordered),
            "start_timestamp": str(first.get("start_timestamp") or first.get("end_timestamp") or "").strip(),
            "end_timestamp": str(last.get("end_timestamp") or last.get("start_timestamp") or "").strip(),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _refresh_recent_summary_ladder(self, workspace: str, pool: str = TALK_RECENT_POOL) -> list[dict]:
        summary_map: dict[str, dict] = {}
        for item in self._load_recent_summary_archive_items(workspace, pool=pool) + self._load_recent_summary_pool(workspace, pool=pool):
            if not isinstance(item, dict):
                continue
            summary_id = str(item.get("summary_id") or "").strip() or str(uuid.uuid4())
            summary_map[summary_id] = item
        all_items = list(summary_map.values())
        now = datetime.now()
        buckets = []
        for window in self._recent_summary_history_windows(pool):
            cutoff = now - timedelta(days=int(window.get("days") or 0))
            matched = []
            for item in all_items:
                item_time = self._summary_item_time(item)
                if item_time and item_time >= cutoff:
                    matched.append(item)
            built = self._build_recent_summary_history_bucket(
                str(window.get("label") or "历史小结").strip(),
                str(window.get("key") or "window").strip(),
                int(window.get("days") or 0),
                matched,
            )
            if built:
                buckets.append(built)
        self._save_recent_summary_ladder(workspace, buckets, pool=pool)
        return buckets

    def _infer_recent_summary_scene_mode(self, talk_entries: list[dict], companion_entries: list[dict]) -> str:
        text_parts = []
        for item in talk_entries + companion_entries:
            if not isinstance(item, dict):
                continue
            text_parts.extend([
                str(item.get("topic") or "").strip(),
                str(item.get("summary") or "").strip(),
                " ".join(str(x).strip() for x in (item.get("context_tags") or []) if str(x).strip()),
                str(item.get("scene_mode") or "").strip(),
            ])
        text = "\n".join(part for part in text_parts if part).lower()
        if any(keyword in text for keyword in ("工作", "任务", "实现", "修复", "测试", "代码", "文档", "heartbeat", "planner")):
            if any(keyword in text for keyword in ("关系", "情绪", "聊天", "陪伴", "心声", "歌")):
                return "mixed"
            return "work"
        if any(keyword in text for keyword in ("聊天", "关系", "情绪", "陪伴", "喜欢", "氛围", "心声", "投射")):
            return "chat"
        if any(keyword in text for keyword in ("自我", "升级", "进化", "反思", "认知", "self", "soul")):
            return "self_growth"
        return "mixed"

    def _build_recent_window_summary(self, talk_entries: list[dict], companion_entries: list[dict], pool: str = TALK_RECENT_POOL) -> dict | None:
        if not talk_entries:
            return None
        first = talk_entries[0]
        last = talk_entries[-1]
        topics = []
        for item in talk_entries:
            topic = str(item.get("topic") or "").strip()
            if topic and topic not in topics:
                topics.append(topic)
            if len(topics) >= 3:
                break
        detail_points = []
        unresolved = []
        self_mind_cues = []
        local_candidates = []
        keywords = []
        for item in talk_entries + companion_entries:
            if not isinstance(item, dict):
                continue
            for value in (item.get("detail_points") or []):
                text = str(value).strip()
                if text and text not in detail_points:
                    detail_points.append(text)
            summary = str(item.get("summary") or "").strip()
            if summary and summary not in detail_points and len(detail_points) < 6:
                detail_points.append(summary)
            for value in ((item.get("unresolved_points") if isinstance(item.get("unresolved_points"), list) else None) or item.get("next_actions") or []):
                text = str(value).strip()
                if text and text not in unresolved:
                    unresolved.append(text)
            cue_sources = []
            for key in ("self_mind_cues", "mental_notes", "relationship_signals"):
                values = item.get(key) if isinstance(item.get(key), list) else []
                cue_sources.extend(values)
            for value in cue_sources:
                text = str(value).strip()
                if text and text not in self_mind_cues:
                    self_mind_cues.append(text)
            lt = item.get("long_term_candidate") if isinstance(item.get("long_term_candidate"), dict) else {}
            title = str(lt.get("title") or "").strip()
            if bool(lt.get("should_write")) and title and title not in local_candidates:
                local_candidates.append(title)
            for value in (item.get("context_tags") or []):
                text = str(value).strip()
                if text and text not in keywords:
                    keywords.append(text)
        scene_mode = self._infer_recent_summary_scene_mode(talk_entries, companion_entries)
        summary_parts = []
        if detail_points:
            summary_parts.append("主要发生：" + "；".join(detail_points[:3]))
        if unresolved:
            summary_parts.append("未收口：" + "；".join(unresolved[:2]))
        if self_mind_cues:
            summary_parts.append("值得续思：" + "；".join(self_mind_cues[:2]))
        summary_text = " | ".join(summary_parts).strip() or ("；".join(detail_points[:3]) if detail_points else "近期窗口整理")
        return {
            "summary_id": str(uuid.uuid4()),
            "pool": self._normalize_recent_pool(pool),
            "scene_mode": scene_mode,
            "title": " / ".join(topics[:2]) or "近期窗口整理",
            "summary": summary_text[:self._recent_summary_entry_char_limit(pool)],
            "detail_points": detail_points[:6],
            "unresolved_points": unresolved[:4],
            "self_mind_cues": self_mind_cues[:4],
            "local_memory_candidates": local_candidates[:3],
            "keywords": keywords[:8],
            "source_memory_ids": [str(item.get("memory_id") or "").strip() for item in talk_entries if str(item.get("memory_id") or "").strip()],
            "evidence_refs": [
                {
                    "memory_id": str(item.get("memory_id") or "").strip(),
                    "timestamp": str(item.get("timestamp") or "").strip(),
                    "topic": str(item.get("topic") or "").strip()[:40],
                }
                for item in talk_entries[:10]
                if str(item.get("memory_id") or "").strip()
            ],
            "start_timestamp": str(first.get("timestamp") or "").strip(),
            "end_timestamp": str(last.get("timestamp") or "").strip(),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _rebuild_recent_summary_pool(self, workspace: str, entries: list[dict], pool: str = TALK_RECENT_POOL, *, reason: str = "") -> dict:
        talk_entries = [
            item for item in (entries or [])
            if isinstance(item, dict)
            and str(item.get("memory_stream") or "talk").strip() == "talk"
            and str(item.get("event_type") or "").strip() == "conversation_turn"
        ]
        prompt_visible = self._recent_max_items(pool)
        source_entries = talk_entries[:-prompt_visible] if len(talk_entries) > prompt_visible else []
        chunk_size = self._recent_summary_chunk_size(pool)
        active_max = self._recent_summary_max_active(pool)
        companion_entries = [item for item in (entries or []) if isinstance(item, dict) and str(item.get("memory_stream") or "talk").strip() != "talk"]
        summaries = []
        for index in range(0, len(source_entries), chunk_size):
            group = source_entries[index:index + chunk_size]
            source_ids = {str(item.get("memory_id") or "").strip() for item in group if str(item.get("memory_id") or "").strip()}
            related = []
            for item in companion_entries:
                derived_from = {str(value).strip() for value in (item.get("derived_from") or []) if str(value).strip()}
                if source_ids & derived_from:
                    related.append(item)
            built = self._build_recent_window_summary(group, related, pool=pool)
            if built:
                summaries.append(built)
        archived = []
        if len(summaries) > active_max:
            archived = summaries[:-active_max]
            summaries = summaries[-active_max:]
        self._save_recent_summary_pool(workspace, summaries, pool=pool)
        if archived:
            self._append_recent_summary_archive(workspace, archived, reason=reason or "summary-pool-rollover", pool=pool)
        ladders = self._refresh_recent_summary_ladder(workspace, pool=pool)
        return {"summary_count": len(summaries), "archived_summary_count": len(archived), "history_bucket_count": len(ladders)}

    def _select_recent_summaries_for_prompt(self, workspace: str, user_prompt: str, pool: str = TALK_RECENT_POOL) -> list[dict]:
        summaries = self._load_recent_summary_pool(workspace, pool=pool)
        limit = self._recent_summary_prompt_limit(pool)
        if not summaries or limit <= 0:
            return []
        query_tokens = self._tokenize(user_prompt)
        scored = []
        total = len(summaries)
        for idx, item in enumerate(summaries):
            keywords = {str(value).strip().lower() for value in (item.get("keywords") or []) if str(value).strip()}
            text_tokens = self._tokenize(f"{item.get('title') or ''} {item.get('summary') or ''} {' '.join(item.get('detail_points') or [])}")
            overlap = len(query_tokens & (keywords | text_tokens)) if query_tokens else 0
            recency = (idx + 1) / max(1, total)
            score = overlap * 10 + recency
            if not query_tokens and idx >= total - limit:
                score += 5
            scored.append((score, idx, item))
        selected = [item for _, _, item in sorted(scored, key=lambda entry: (entry[0], entry[1]), reverse=True)[:limit]]
        return sorted(selected, key=lambda item: str(item.get("end_timestamp") or item.get("start_timestamp") or ""))

    def _render_recent_summary_context(self, summaries: list[dict], max_chars: int) -> str:
        lines = []
        for item in summaries or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "近期窗口整理").strip()
            scene_mode = str(item.get("scene_mode") or "mixed").strip()
            summary = str(item.get("summary") or "").strip()
            details = [str(value).strip() for value in (item.get("detail_points") or []) if str(value).strip()][:2]
            unresolved = [str(value).strip() for value in (item.get("unresolved_points") or []) if str(value).strip()][:1]
            line = f"- [{scene_mode}] {title}: {summary}"
            if details:
                line += f" | 细节：{'；'.join(details)}"
            if unresolved:
                line += f" | 未决：{'；'.join(unresolved)}"
            lines.append(line)
        text = "\n".join(lines).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _render_recent_summary_ladder_context(self, buckets: list[dict], max_chars: int) -> str:
        lines = []
        for item in (buckets or [])[:self._recent_summary_history_prompt_limit(TALK_RECENT_POOL)]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "历史小结").strip()
            summary = str(item.get("summary") or "").strip()
            unresolved = [str(value).strip() for value in (item.get("unresolved_points") or []) if str(value).strip()][:1]
            line = f"- [{label}] {summary}"
            if unresolved:
                line += f" | 仍在延伸：{'；'.join(unresolved)}"
            lines.append(line)
        text = "\n".join(lines).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def prune_stale_recent_entries(self, workspace: str, pool: str = TALK_RECENT_POOL, reason: str = "manual-cleanup") -> dict:
        with self._memory_lock:
            entries = self._load_recent_entries(workspace, pool=pool)
            active_entries, stale_entries = self._split_stale_recent_entries(entries)
            archive_path = ""
            if stale_entries:
                archive_path = self._archive_stale_recent_entries(workspace, stale_entries, reason=reason, pool=pool)
                self._save_recent_entries(workspace, active_entries, pool=pool)
            return {
                "pool": self._normalize_recent_pool(pool),
                "before_count": len(entries),
                "after_count": len(active_entries),
                "stale_count": len(stale_entries),
                "archive_path": archive_path,
            }

    def _compact_recent_entries_if_needed(self, entries: list[dict], workspace: str, timeout: int, model: str, reason: str, pool: str = TALK_RECENT_POOL) -> tuple[list[dict], dict]:
        info = {
            "compacted": False,
            "archived_count": 0,
            "reflections_count": 0,
            "before_count": len(entries),
            "after_count": len(entries),
        }
        storage_max_items = self._recent_storage_max_items(pool)
        storage_max_chars = self._recent_storage_max_chars(pool)
        if not (len(entries) > storage_max_items or self._recent_entries_chars(entries) > storage_max_chars):
            return entries, info

        old_entries = entries[:-storage_max_items] if len(entries) > storage_max_items else []
        keep_entries = entries[-storage_max_items:]

        if old_entries:
            archive_text = self._summarize_old_entries_for_archive(old_entries)
            if archive_text:
                self._append_recent_archive(workspace, f"旧记忆压缩({reason})", archive_text, pool=pool)
                info["archived_count"] = len(old_entries)

            cutoff = datetime.now() - timedelta(days=1)
            stale = []
            for e in old_entries:
                t = self._parse_entry_time(e)
                if t and t < cutoff:
                    stale.append(e)

            reflections = self._select_necessary_reflections(stale)
            for r in reflections:
                self._upsert_local_memory(
                    workspace,
                    str(r.get("title") or "对话反思沉淀"),
                    str(r.get("summary") or ""),
                    [str(x) for x in (r.get("keywords") or [])],
                    source_type="recent-compact",
                    source_memory_id=str(r.get("source_memory_id") or ""),
                    source_reason=str(reason or "compact"),
                    source_topic=str(r.get("title") or ""),
                )
            info["reflections_count"] = len(reflections)

            if pool == BEAT_RECENT_POOL:
                try:
                    self._file_guardian_record_only_request(
                        workspace,
                        source="heartbeat",
                        title="heartbeat recent memory 压缩备案",
                        reason=f"heartbeat 对 beat recent memory 执行轻量压缩，原因: {reason}",
                        planned_actions=["archive old beat recent entries", "retain latest beat recent entries"],
                        verification=["recent archive written", "beat recent memory remains readable"],
                        rollback=["restore previous beat recent memory snapshot if needed"],
                        scope_files=[
                            f"{BEAT_RECENT_MEMORY_DIR_REL.as_posix()}/{RECENT_MEMORY_FILE}",
                            f"{BEAT_RECENT_MEMORY_DIR_REL.as_posix()}/{RECENT_ARCHIVE_FILE}",
                        ],
                        scope_modules=["memory_manager"],
                        scope_runtime_objects=["beat_recent_memory"],
                        execution_notes=[
                            f"before_count={len(entries)}",
                            f"after_count={len(keep_entries)}",
                            f"archived_count={info['archived_count']}",
                            f"reflections_count={info['reflections_count']}",
                        ],
                    )
                except Exception as e:
                    print(f"[guardian-request] 轻量修复备案失败: {e}", flush=True)

        info["compacted"] = True
        info["after_count"] = len(keep_entries)
        return keep_entries, info

    def _summarize_old_entries_for_archive(self, old_entries: list[dict]) -> str:
        lines = []
        for e in old_entries[-20:]:
            ts = str(e.get("timestamp") or "")
            topic = str(e.get("topic") or "")
            summary = str(e.get("summary") or "").strip()
            if summary:
                lines.append(f"- [{ts}] {topic}: {summary[:120]}")
        return "\n".join(lines)[:2000]

    def _select_necessary_reflections(self, stale_entries: list[dict]) -> list[dict]:
        out = []
        keys = ["反思", "教训", "下次", "避免", "必须", "默认", "偏好", "规则", "约束"]
        for e in stale_entries:
            text = f"{e.get('topic') or ''} {e.get('summary') or ''}"
            low = text.lower()
            if any(k in text or k.lower() in low for k in keys):
                out.append(
                    {
                        "title": str(e.get("topic") or "对话反思沉淀")[:40],
                        "summary": str(e.get("summary") or "").strip()[:220],
                        "keywords": [],
                        "source_memory_id": str(e.get("memory_id") or "").strip(),
                    }
                )
            if len(out) >= 2:
                break
        return out

    # ---------- file helpers ----------

    def _normalize_recent_pool(self, pool: str | None = None) -> str:
        raw = str(pool or TALK_RECENT_POOL).strip().lower()
        if raw in {BEAT_RECENT_POOL, "heartbeat"}:
            return BEAT_RECENT_POOL
        return TALK_RECENT_POOL

    def _recent_pool_paths(self, workspace: str, pool: str = TALK_RECENT_POOL) -> tuple[Path, Path]:
        root = resolve_butler_root(workspace)
        if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL:
            recent_dir = root / BEAT_RECENT_MEMORY_DIR_REL
        else:
            recent_dir = root / RECENT_MEMORY_DIR_REL
        return recent_dir, recent_dir / RECENT_MEMORY_FILE

    def _memory_paths(self, workspace: str) -> tuple[Path, Path, Path]:
        root = resolve_butler_root(workspace)
        recent_dir, recent_file = self._recent_pool_paths(workspace, TALK_RECENT_POOL)
        local_dir = root / LOCAL_MEMORY_DIR_REL
        return recent_dir, recent_file, local_dir

    def _local_layer_paths(self, local_dir: Path) -> tuple[Path, Path, Path]:
        return (
            local_dir / LOCAL_INDEX_FILE,
            local_dir / LOCAL_L1_SUMMARY_DIR_NAME,
            local_dir / LOCAL_L2_DETAIL_DIR_NAME,
        )

    def _local_relations_path(self, local_dir: Path) -> Path:
        return local_dir / LOCAL_RELATIONS_FILE

    def _local_index_service(self, local_dir: Path) -> LocalMemoryIndexService:
        return LocalMemoryIndexService(local_dir)

    def _default_local_memory_index(self) -> dict:
        return {
            "schema_version": 3,
            "updated_at": "",
            "categories": [{"name": name, "description": ""} for name in LOCAL_CATEGORY_NAMES],
            "entries": [],
        }

    def _default_local_memory_relations(self) -> dict:
        return {
            "schema_version": 1,
            "updated_at": "",
            "relations": [],
        }

    def _save_local_memory_index(self, local_dir: Path, payload: dict) -> None:
        index_path, _, _ = self._local_layer_paths(local_dir)
        normalized = dict(payload or {})
        normalized["schema_version"] = 3
        normalized["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized["categories"] = [item for item in normalized.get("categories") or [] if isinstance(item, dict)][:10]
        normalized["entries"] = [item for item in normalized.get("entries") or [] if isinstance(item, dict)][-500:]
        index_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_local_memory_relations(self, local_dir: Path) -> dict:
        self._ensure_local_memory_layout(local_dir)
        path = self._local_relations_path(local_dir)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        payload = self._default_local_memory_relations()
        self._save_local_memory_relations(local_dir, payload)
        return payload

    def _save_local_memory_relations(self, local_dir: Path, payload: dict) -> None:
        path = self._local_relations_path(local_dir)
        normalized = dict(payload or {})
        normalized["schema_version"] = 1
        normalized["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized["relations"] = [item for item in normalized.get("relations") or [] if isinstance(item, dict)][-1000:]
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _ensure_local_memory_layout(self, local_dir: Path) -> None:
        index_path, l1_dir, l2_dir = self._local_layer_paths(local_dir)
        l1_dir.mkdir(parents=True, exist_ok=True)
        l2_dir.mkdir(parents=True, exist_ok=True)
        if not index_path.exists():
            self._save_local_memory_index(local_dir, self._default_local_memory_index())
        relations_path = self._local_relations_path(local_dir)
        if not relations_path.exists():
            self._save_local_memory_relations(local_dir, self._default_local_memory_relations())

    def _ensure_memory_dirs(self, workspace: str) -> tuple[Path, Path, Path]:
        recent_dir, recent_file, local_dir = self._memory_paths(workspace)
        recent_dir.mkdir(parents=True, exist_ok=True)
        beat_recent_dir, _ = self._recent_pool_paths(workspace, BEAT_RECENT_POOL)
        beat_recent_dir.mkdir(parents=True, exist_ok=True)
        local_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_local_memory_layout(local_dir)
        self._cleanup_retired_heartbeat_markdown_mirrors(recent_dir, local_dir)
        return recent_dir, recent_file, local_dir

    def _cleanup_retired_heartbeat_markdown_mirrors(self, recent_dir: Path, local_dir: Path) -> None:
        if self._legacy_heartbeat_markdown_mirrors_enabled():
            return
        for path in (
            recent_dir / HEARTBEAT_MEMORY_MIRROR_FILE,
            local_dir / HEARTBEAT_LONG_TASKS_MIRROR_FILE,
        ):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

    def _load_recent_entries(self, workspace: str, pool: str = TALK_RECENT_POOL) -> list[dict]:
        self._ensure_memory_dirs(workspace)
        _, recent_file = self._recent_pool_paths(workspace, pool)
        if not recent_file.exists():
            return []
        try:
            data = json.loads(recent_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [self._normalize_recent_entry(x, pool=pool) for x in data if isinstance(x, dict)]
        except Exception:
            pass
        return []

    def _save_recent_entries(self, workspace: str, entries: list[dict], pool: str = TALK_RECENT_POOL) -> None:
        self._ensure_memory_dirs(workspace)
        recent_dir, recent_file = self._recent_pool_paths(workspace, pool)
        recent_dir.mkdir(parents=True, exist_ok=True)
        normalized = [self._normalize_recent_entry(item, pool=pool) for item in entries if isinstance(item, dict)]
        recent_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        self._rebuild_recent_summary_pool(workspace, normalized, pool=pool, reason="save-recent")

    def get_recent_entries(self, workspace: str, limit: int | None = None, pool: str = TALK_RECENT_POOL) -> list[dict]:
        entries = self._load_recent_entries(workspace, pool=pool)
        if limit is None or limit <= 0:
            return entries
        return entries[-limit:]

    def append_recent_entry(
        self,
        workspace: str,
        topic: str,
        summary: str,
        raw_user_prompt: str = "",
        next_actions: list[str] | None = None,
        pool: str = TALK_RECENT_POOL,
    ) -> dict:
        entry = {
            "memory_id": str(uuid.uuid4()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": str(topic or "手动追加记忆").strip()[:18] or "手动追加记忆",
            "summary": str(summary or "").strip()[:160],
            "memory_scope": self._normalize_recent_pool(pool),
            "memory_stream": "heartbeat_observation" if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else "talk",
            "event_type": "manual_append",
            "raw_user_prompt": str(raw_user_prompt or "").strip()[:500],
            "status": "completed",
            "next_actions": [str(x).strip()[:40] for x in (next_actions or []) if str(x).strip()][:3],
            "heartbeat_tasks": [],
            "heartbeat_long_term_tasks": [],
            "salience": 0.4,
            "confidence": 0.9,
            "derived_from": ["manual"],
            "context_tags": [],
            "mental_notes": [],
            "relationship_signals": [],
            "relation_signal": {},
            "active_window": "recent",
            "long_term_candidate": {
                "should_write": False,
                "title": "",
                "summary": "",
                "keywords": [],
            },
        }
        with self._memory_lock:
            entries = self._load_recent_entries(workspace, pool=pool)
            entries.append(entry)
            entries, _ = self._compact_recent_entries_if_needed(entries, workspace, 0, "", reason="manual-append", pool=pool)
            self._save_recent_entries(workspace, entries, pool=pool)
        return entry

    def _normalize_recent_entry(self, entry: dict, pool: str = TALK_RECENT_POOL) -> dict:
        normalized = self._subconscious_service.normalize_recent_entry(entry)
        scope = self._normalize_recent_pool(pool)
        normalized["memory_scope"] = str(normalized.get("memory_scope") or scope).strip() or scope
        if scope == BEAT_RECENT_POOL and str(normalized.get("memory_stream") or "") == "talk":
            normalized["memory_stream"] = "heartbeat_observation"
            normalized["event_type"] = str(normalized.get("event_type") or "heartbeat_snapshot").strip() or "heartbeat_snapshot"
        return normalized

    def append_local_memory_entry(self, workspace: str, title: str, summary: str, keywords: list[str] | None = None) -> None:
        self._upsert_local_memory(
            workspace,
            title,
            summary,
            [str(x).strip() for x in (keywords or []) if str(x).strip()],
            source_type="manual",
            source_reason="append_local_memory_entry",
            source_topic=str(title or "").strip(),
        )

    def query_local_memory(
        self,
        workspace: str,
        keyword: str = "",
        query_text: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 20,
        include_details: bool = False,
        categories: list[str] | None = None,
        memory_types: list[str] | None = None,
    ) -> list[dict]:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return self._local_index_service(local_dir).query(
            LocalMemoryQueryParams(
                query_text=query_text,
                keyword=keyword,
                since=since,
                until=until,
                limit=limit,
                include_details=include_details,
                categories=tuple(categories or ()),
                memory_types=tuple(memory_types or ()),
            )
        )

    def rebuild_local_memory_index(self, workspace: str) -> dict:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return self._local_index_service(local_dir).rebuild_index()

    def _load_local_memory_index(self, local_dir: Path) -> dict:
        return self._local_index_service(local_dir).load_index()

    def _relative_local_memory_path(self, local_dir: Path, path: Path | None) -> str:
        if not path:
            return ""
        try:
            return path.relative_to(local_dir).as_posix()
        except Exception:
            return path.name

    def _append_recent_archive(self, workspace: str, title: str, content: str, pool: str = TALK_RECENT_POOL) -> None:
        self._ensure_memory_dirs(workspace)
        recent_dir, _ = self._recent_pool_paths(workspace, pool)
        archive = recent_dir / RECENT_ARCHIVE_FILE
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        block = f"\n\n## {stamp} {title}\n\n{(content or '').strip()}\n"
        old = archive.read_text(encoding="utf-8") if archive.exists() else "# recent_archive\n\n"
        archive.write_text(old.rstrip() + block + "\n", encoding="utf-8")

    def _startup_status_path(self, workspace: str) -> Path:
        recent_dir, _, _ = self._ensure_memory_dirs(workspace)
        return recent_dir / RECENT_STARTUP_STATUS_FILE

    def _heartbeat_memory_path(self, workspace: str) -> Path:
        recent_dir, _, _ = self._ensure_memory_dirs(workspace)
        return recent_dir / HEARTBEAT_MEMORY_FILE

    def _heartbeat_upgrade_request_path(self, workspace: str) -> Path:
        return resolve_butler_root(workspace or os.getcwd()) / HEARTBEAT_UPGRADE_REQUEST_JSON_REL

    def _guardian_requests_dir(self, workspace: str) -> Path:
        root = resolve_butler_root(workspace or os.getcwd())
        return root / GUARDIAN_REQUESTS_DIR_REL

    def _guardian_request_file_path(self, workspace: str, request_id: str) -> Path:
        request_dir = self._guardian_requests_dir(workspace)
        request_dir.mkdir(parents=True, exist_ok=True)
        safe_request_id = re.sub(r"[^0-9A-Za-z._-]+", "-", str(request_id or uuid.uuid4()).strip())
        existing = sorted(request_dir.glob(f"*_{safe_request_id}.json"))
        if existing:
            return existing[-1]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return request_dir / f"{stamp}_{safe_request_id}.json"

    def _save_guardian_request(self, workspace: str, payload: dict) -> dict:
        data = dict(payload or {})
        request_id = str(data.get("request_id") or uuid.uuid4()).strip() or str(uuid.uuid4())
        data["schema_version"] = GUARDIAN_REQUEST_SCHEMA_VERSION
        data["request_id"] = request_id
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path = self._guardian_request_file_path(workspace, request_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def _file_guardian_record_only_request(
        self,
        workspace: str,
        *,
        source: str,
        title: str,
        reason: str,
        planned_actions: list[str] | None = None,
        verification: list[str] | None = None,
        rollback: list[str] | None = None,
        scope_files: list[str] | None = None,
        scope_modules: list[str] | None = None,
        scope_runtime_objects: list[str] | None = None,
        execution_notes: list[str] | None = None,
    ) -> dict:
        payload = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": str(source or "heartbeat").strip() or "heartbeat",
            "request_type": "record-only",
            "title": str(title or "heartbeat 轻量修复备案").strip() or "heartbeat 轻量修复备案",
            "reason": str(reason or "heartbeat 执行了轻量修复动作").strip() or "heartbeat 执行了轻量修复动作",
            "scope": {
                "files": [str(x) for x in (scope_files or []) if str(x or "").strip()],
                "modules": [str(x) for x in (scope_modules or []) if str(x or "").strip()],
                "runtime_objects": [str(x) for x in (scope_runtime_objects or []) if str(x or "").strip()],
            },
            "planned_actions": [str(x) for x in (planned_actions or []) if str(x or "").strip()],
            "requires_code_change": False,
            "requires_restart": False,
            "verification": [str(x) for x in (verification or []) if str(x or "").strip()],
            "rollback": [str(x) for x in (rollback or []) if str(x or "").strip()],
            "risk_level": "low",
            "review_status": "pending",
            "review_notes": [],
            "execution_notes": [str(x) for x in (execution_notes or []) if str(x or "").strip()],
            "requested_tests": [],
            "patch_plan": None,
        }
        return self._save_guardian_request(workspace, payload)

    def _file_guardian_upgrade_request(self, workspace: str, request: dict) -> dict:
        normalized = self._normalize_heartbeat_upgrade_request(request)
        execute_prompt = str(normalized.get("execute_prompt") or "").strip()
        payload = {
            "request_id": str(normalized.get("request_id") or uuid.uuid4()).strip() or str(uuid.uuid4()),
            "created_at": str(normalized.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")).strip(),
            "source": str(normalized.get("source") or "heartbeat").strip() or "heartbeat",
            "request_type": "restart" if bool(normalized.get("requires_restart")) else "code-fix",
            "title": "heartbeat 升级申请",
            "reason": str(normalized.get("reason") or "heartbeat 提出升级申请").strip() or "heartbeat 提出升级申请",
            "scope": {
                "files": [],
                "modules": ["memory_manager", "heartbeat_orchestration"],
                "runtime_objects": ["heartbeat", "upgrade-request"],
            },
            "planned_actions": [execute_prompt] if execute_prompt else [str(normalized.get("summary") or normalized.get("reason") or "执行升级方案").strip()],
            "requires_code_change": True,
            "requires_restart": bool(normalized.get("requires_restart")),
            "verification": ["guardian 审阅通过后执行升级方案", "执行后按改动范围运行动态测试"],
            "rollback": ["若升级失败则回滚本次代码或配置变更", "若上线失败则恢复到升级前运行状态"],
            "risk_level": "high" if bool(normalized.get("requires_restart")) else "medium",
            "review_status": str(normalized.get("status") or "pending").strip() or "pending",
            "review_notes": [],
            "execution_notes": [str(normalized.get("summary") or "").strip()] if str(normalized.get("summary") or "").strip() else [],
            "requested_tests": [],
            "patch_plan": {
                "required": True,
                "status": "pending",
                "summary": "guardian 执行代码修改前必须先生成 patch 预案",
            },
        }
        return self._save_guardian_request(workspace, payload)

    def _heartbeat_memory_mirror_path(self, workspace: str) -> Path:
        recent_dir, _, _ = self._ensure_memory_dirs(workspace)
        return recent_dir / HEARTBEAT_MEMORY_MIRROR_FILE

    def _heartbeat_last_sent_path(self, workspace: str) -> Path:
        recent_dir, _, _ = self._ensure_memory_dirs(workspace)
        return recent_dir / HEARTBEAT_LAST_SENT_FILE

    def _write_heartbeat_last_sent(self, workspace: str, sent: bool | None = True) -> None:
        """记录本地心跳活动时间；若消息确实发出，再额外标记发送时间。"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path = self._heartbeat_last_sent_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        old_payload: dict = {}
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    old_payload = raw
            except Exception:
                old_payload = {}
        last_sent_at = str(old_payload.get("last_sent_at") or "").strip()
        sent_flag = bool(old_payload.get("sent")) if sent is None else bool(sent)
        if sent is True:
            last_sent_at = now_str
        elif sent is False and not last_sent_at:
            last_sent_at = ""
        payload = {
            "last_activity_at": now_str,
            "timestamp": now_str,
            "last_sent_at": last_sent_at,
            "sent": sent_flag,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _heartbeat_long_tasks_path(self, workspace: str) -> Path:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return local_dir / HEARTBEAT_LONG_TASKS_FILE

    def _with_user_feishu_history_dir(self, workspace: str) -> Path:
        return resolve_butler_root(workspace or os.getcwd()) / "工作区" / "with_user" / "feishu_chat_history"

    def _heartbeat_tell_user_audit_path(self, workspace: str, day: datetime | None = None) -> Path:
        return self._self_mind_talk_audit_path(workspace, day)

    def _legacy_heartbeat_tell_user_audit_path(self, workspace: str, day: datetime | None = None) -> Path:
        stamp = (day or datetime.now()).strftime("%Y-%m-%d")
        return self._with_user_feishu_history_dir(workspace) / f"heartbeat_tell_user_log_{stamp}.jsonl"

    def _self_mind_talk_audit_path(self, workspace: str, day: datetime | None = None) -> Path:
        stamp = (day or datetime.now()).strftime("%Y-%m-%d")
        return self._with_user_feishu_history_dir(workspace) / f"self_mind_talk_log_{stamp}.jsonl"

    def _feishu_digest_dir(self, workspace: str) -> Path:
        return self._with_user_feishu_history_dir(workspace) / "digest"

    def _self_mind_dir(self, workspace: str) -> Path:
        return resolve_butler_root(workspace or os.getcwd()) / SELF_MIND_DIR_REL

    def _self_mind_context_path(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / "current_context.md"

    def _self_mind_log_dir(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / "logs"

    def _self_mind_raw_path(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / SELF_MIND_RAW_FILE_NAME

    def _self_mind_review_path(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / SELF_MIND_REVIEW_FILE_NAME

    def _self_mind_behavior_mirror_path(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / SELF_MIND_BEHAVIOR_MIRROR_FILE_NAME

    def _self_mind_state_path(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / SELF_MIND_STATE_FILE_NAME

    def _self_mind_bridge_path(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / SELF_MIND_BRIDGE_FILE_NAME

    def _self_mind_log_path(self, workspace: str) -> Path:
        return self._self_mind_log_dir(workspace) / f"mental_stream_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def _self_mind_daily_dir(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / "daily"

    def _self_mind_daily_summary_path(self, workspace: str) -> Path:
        return self._self_mind_daily_dir(workspace) / f"{datetime.now().strftime('%Y%m%d')}.md"

    def _self_mind_cognition_dir(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / "cognition"

    def _self_mind_cognition_index_path(self, workspace: str) -> Path:
        return self._self_mind_cognition_dir(workspace) / SELF_MIND_COGNITION_INDEX_FILE_NAME

    def _self_mind_cognition_l1_dir(self, workspace: str) -> Path:
        return self._self_mind_cognition_dir(workspace) / SELF_MIND_COGNITION_L1_DIR_NAME

    def _self_mind_cognition_l2_dir(self, workspace: str) -> Path:
        return self._self_mind_cognition_dir(workspace) / SELF_MIND_COGNITION_L2_DIR_NAME

    def _self_mind_perception_path(self, workspace: str) -> Path:
        return self._self_mind_dir(workspace) / SELF_MIND_PERCEPTION_FILE_NAME

    def _self_mind_domain_dir(self, workspace: str, domain: str) -> Path:
        return self._self_mind_dir(workspace) / domain

    def _load_self_mind_context_excerpt(self, workspace: str, max_chars: int | None = None) -> str:
        effective_max = self._self_mind_context_max_chars() if max_chars is None else max_chars
        return self._load_markdown_excerpt(self._self_mind_context_path(workspace), max_chars=effective_max)

    def _load_self_mind_state(self, workspace: str) -> dict:
        return self._load_json_store(self._self_mind_state_path(workspace), lambda: {"version": 1})

    def _save_self_mind_state(self, workspace: str, payload: dict) -> None:
        self._save_json_store(self._self_mind_state_path(workspace), {"version": 1, **dict(payload or {})})

    def _default_self_mind_cognition_index(self) -> dict:
        return {"version": 1, "updated_at": "", "categories": []}

    def _load_self_mind_cognition_index(self, workspace: str) -> dict:
        payload = self._load_json_store(self._self_mind_cognition_index_path(workspace), self._default_self_mind_cognition_index)
        categories = payload.get("categories") if isinstance(payload.get("categories"), list) else []
        payload["categories"] = [item for item in categories if isinstance(item, dict)]
        return payload

    def _save_self_mind_cognition_index(self, workspace: str, payload: dict) -> None:
        current = dict(payload or {})
        current["version"] = 1
        current["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        categories = current.get("categories") if isinstance(current.get("categories"), list) else []
        current["categories"] = [item for item in categories if isinstance(item, dict)]
        self._save_json_store(self._self_mind_cognition_index_path(workspace), current)

    def _self_mind_cognition_l1_path(self, workspace: str, slug: str) -> Path:
        title = next((item.get("title") for item in self._self_mind_cognitive_categories() if item.get("slug") == slug), slug)
        return self._self_mind_cognition_l1_dir(workspace) / f"{slug}_{title}.md"

    def _self_mind_cognition_l2_path(self, workspace: str, slug: str) -> Path:
        return self._self_mind_cognition_l2_dir(workspace) / f"{slug}.jsonl"

    def _load_self_mind_cognition_signals(self, workspace: str, slug: str) -> list[dict]:
        path = self._self_mind_cognition_l2_path(workspace, slug)
        if not path.exists():
            return []
        records: list[dict] = []
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                if not raw.strip():
                    continue
                try:
                    item = json.loads(raw)
                except Exception:
                    continue
                if isinstance(item, dict):
                    records.append(item)
        except Exception:
            return []
        return records[-self._self_mind_cognition_signal_limit_per_category():]

    def _append_self_mind_cognition_signal(self, workspace: str, slug: str, signal: dict) -> None:
        path = self._self_mind_cognition_l2_path(workspace, slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        signals = self._load_self_mind_cognition_signals(workspace, slug)
        signals.append(signal)
        trimmed = signals[-self._self_mind_cognition_signal_limit_per_category():]
        path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in trimmed if isinstance(item, dict)) + ("\n" if trimmed else ""),
            encoding="utf-8",
        )

    def _select_self_mind_cognitive_category(self, text: str, fallback: str = "self_model") -> str:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return fallback
        for item in self._self_mind_cognitive_categories():
            keywords = item.get("keywords") if isinstance(item.get("keywords"), list) else []
            if any(keyword and keyword in lowered for keyword in keywords):
                return str(item.get("slug") or fallback)
        return fallback

    def _build_self_mind_cognition_signals_from_entry(self, entry: dict, source: str) -> list[dict]:
        if not isinstance(entry, dict):
            return []
        topic = str(entry.get("topic") or "自我意识信号").strip()[:80] or "自我意识信号"
        scene_mode = str(entry.get("scene_mode") or "mixed").strip() or "mixed"
        timestamp = str(entry.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")).strip()
        memory_id = str(entry.get("memory_id") or "").strip()[:80]
        signals: list[dict] = []

        def push(category: str, title: str, summary: str, *, signal_type: str, keywords: list[str] | None = None, confidence: float = 0.6) -> None:
            text = str(summary or "").strip()
            if not text:
                return
            signals.append(
                {
                    "timestamp": timestamp,
                    "source": source,
                    "memory_id": memory_id,
                    "scene_mode": scene_mode,
                    "category": category,
                    "title": str(title or topic).strip()[:120],
                    "summary": text[:320],
                    "signal_type": signal_type,
                    "confidence": max(0.0, min(1.0, float(confidence or 0.0))),
                    "keywords": [str(value).strip()[:40] for value in (keywords or []) if str(value).strip()][:8],
                }
            )

        relation_signals = [str(value).strip() for value in (entry.get("relationship_signals") or []) if str(value).strip()]
        mental_notes = [str(value).strip() for value in (entry.get("mental_notes") or []) if str(value).strip()]
        self_mind_cues = [str(value).strip() for value in (entry.get("self_mind_cues") or []) if str(value).strip()]
        context_tags = [str(value).strip() for value in (entry.get("context_tags") or []) if str(value).strip()]
        long_term_candidate = entry.get("long_term_candidate") if isinstance(entry.get("long_term_candidate"), dict) else {}
        relation_signal = entry.get("relation_signal") if isinstance(entry.get("relation_signal"), dict) else {}
        summary = str(entry.get("summary") or "").strip()

        for text in relation_signals[:3]:
            push("user_model", topic, text, signal_type="inference", keywords=context_tags or ["user"], confidence=0.75)

        for text in mental_notes[:3]:
            category = self._select_self_mind_cognitive_category(text, fallback="self_model")
            push(category, topic, text, signal_type="tendency", keywords=context_tags, confidence=0.62)

        for text in self_mind_cues[:3]:
            category = self._select_self_mind_cognitive_category(text, fallback="self_model")
            push(category, topic, text, signal_type="tendency", keywords=context_tags, confidence=0.58)

        if bool(long_term_candidate.get("should_write")):
            lt_title = str(long_term_candidate.get("title") or topic).strip()[:120] or topic
            lt_summary = str(long_term_candidate.get("summary") or summary).strip()
            lt_keywords = [str(value).strip() for value in (long_term_candidate.get("keywords") or []) if str(value).strip()]
            category = self._select_self_mind_cognitive_category(" ".join([lt_title, lt_summary] + lt_keywords), fallback="values" if scene_mode == "self_growth" else "self_model")
            push(category, lt_title, lt_summary, signal_type="inference", keywords=lt_keywords or context_tags, confidence=0.82)

        tone = str(relation_signal.get("tone") or "").strip()
        preference_shift = str(relation_signal.get("preference_shift") or "").strip()
        if tone or preference_shift:
            relation_summary = "；".join(part for part in [tone, preference_shift] if part)
            push("user_model", topic, relation_summary, signal_type="inference", keywords=context_tags or ["relationship"], confidence=0.78)

        if summary and scene_mode in {"self_growth", "chat"}:
            fallback_category = "values" if scene_mode == "self_growth" else "preferences"
            push(fallback_category, topic, summary, signal_type="fact", keywords=context_tags, confidence=0.55)
        return signals[:10]

    def _refresh_self_mind_cognition_category_views(self, workspace: str, slug: str) -> None:
        config = next((item for item in self._self_mind_cognitive_categories() if item.get("slug") == slug), None)
        if not config:
            return
        signals = self._load_self_mind_cognition_signals(workspace, slug)
        path = self._self_mind_cognition_l1_path(workspace, slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# {str(config.get('title') or slug)}", "", f"用途：{str(config.get('description') or '').strip()}", "", "## 当前抽象结论"]
        if not signals:
            lines.append("- （当前为空，等待潜意识与意识循环继续长出有效信号）")
        else:
            latest = list(reversed(signals[-self._self_mind_cognition_prompt_limit():]))
            for item in latest:
                title = str(item.get("title") or slug).strip()
                summary = str(item.get("summary") or "").strip()
                signal_type = str(item.get("signal_type") or "fact").strip()
                lines.append(f"- [{signal_type}] {title}: {summary}")
        lines.extend(["", "## 最近证据", ""])
        if not signals:
            lines.append("- （暂无）")
        else:
            for item in signals[-min(6, len(signals)):]:
                lines.append(
                    f"- [{str(item.get('timestamp') or '').strip()}][{str(item.get('source') or '').strip() or '-'}] {str(item.get('summary') or '').strip()}"
                )
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    def _refresh_self_mind_cognition_index(self, workspace: str) -> None:
        categories = []
        for item in self._self_mind_cognitive_categories():
            slug = str(item.get("slug") or "").strip()
            if not slug:
                continue
            signals = self._load_self_mind_cognition_signals(workspace, slug)
            l1_path = self._self_mind_cognition_l1_path(workspace, slug)
            l2_path = self._self_mind_cognition_l2_path(workspace, slug)
            latest = signals[-1] if signals else {}
            categories.append(
                {
                    "slug": slug,
                    "title": str(item.get("title") or slug),
                    "description": str(item.get("description") or ""),
                    "signal_count": len(signals),
                    "latest_summary": str(latest.get("summary") or "")[:200],
                    "latest_timestamp": str(latest.get("timestamp") or ""),
                    "l1_path": prompt_path_text(l1_path.relative_to(resolve_butler_root(workspace))),
                    "l2_path": prompt_path_text(l2_path.relative_to(resolve_butler_root(workspace))),
                }
            )
        self._save_self_mind_cognition_index(workspace, {"categories": categories})

    def _promote_entry_into_self_mind_cognition(self, workspace: str, entry: dict, source: str) -> None:
        signals = self._build_self_mind_cognition_signals_from_entry(entry, source)
        if not signals:
            return
        for signal in signals:
            slug = str(signal.get("category") or "self_model").strip() or "self_model"
            self._append_self_mind_cognition_signal(workspace, slug, signal)
            self._refresh_self_mind_cognition_category_views(workspace, slug)
        self._refresh_self_mind_cognition_index(workspace)

    def _load_self_mind_bridge_items(self, workspace: str) -> list[dict]:
        payload = self._load_json_store(self._self_mind_bridge_path(workspace), lambda: {"items": []})
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        return [item for item in items if isinstance(item, dict)]

    def _save_self_mind_bridge_items(self, workspace: str, items: list[dict]) -> None:
        normalized = [item for item in items if isinstance(item, dict)][-self._self_mind_bridge_max_items():]
        self._save_json_store(self._self_mind_bridge_path(workspace), {"version": 1, "items": normalized})

    def _self_mind_bridge_item_epoch(self, item: dict, *keys: str) -> float:
        for key in keys:
            try:
                value = float(item.get(key) or 0.0)
            except Exception:
                value = 0.0
            if value > 0:
                return value
        dt = self._parse_datetime_text(str(item.get("created_at") or "").strip())
        return dt.timestamp() if dt else 0.0

    def _bridge_status_display(self, item: dict) -> str:
        status = str(item.get("status") or "pending").strip() or "pending"
        if bool(item.get("review_due")) and status not in {"completed", "expired", "dropped"}:
            return status + "/review"
        if bool(item.get("expired_candidate")) and status not in {"completed", "expired", "dropped"}:
            return status + "/expire?"
        return status

    def _decorate_self_mind_bridge_item(self, item: dict) -> dict:
        decorated = dict(item or {})
        now = time.time()
        last_review_epoch = self._self_mind_bridge_item_epoch(decorated, "last_reviewed_epoch", "body_last_seen_epoch", "created_epoch")
        created_epoch = self._self_mind_bridge_item_epoch(decorated, "created_epoch")
        review_due = last_review_epoch <= 0 or (now - last_review_epoch) >= self._self_mind_bridge_review_interval_seconds()
        expired_candidate = created_epoch > 0 and (now - created_epoch) >= self._self_mind_bridge_expire_seconds()
        decorated["review_due"] = bool(review_due)
        decorated["expired_candidate"] = bool(expired_candidate)
        return decorated

    def _normalize_self_mind_bridge_update(self, payload: dict) -> dict | None:
        if not isinstance(payload, dict):
            return None
        bridge_id = str(payload.get("bridge_id") or "").strip()
        if not bridge_id:
            return None
        status = str(payload.get("status") or "pending").strip().lower()
        if status not in {"pending", "completed", "expired", "dropped"}:
            status = "pending"
        reason = str(payload.get("reason") or "").strip()[:320]
        return {"bridge_id": bridge_id, "status": status, "reason": reason}

    def _apply_self_mind_bridge_updates(self, workspace: str, updates: list[dict] | None) -> None:
        normalized_updates = []
        for raw in updates or []:
            item = self._normalize_self_mind_bridge_update(raw)
            if item:
                normalized_updates.append(item)
        if not normalized_updates:
            return
        update_map = {item["bridge_id"]: item for item in normalized_updates}
        items = self._load_self_mind_bridge_items(workspace)
        changed = False
        for item in items:
            bridge_id = str(item.get("bridge_id") or "").strip()
            update = update_map.get(bridge_id)
            if not update:
                continue
            item["status"] = update["status"]
            item["decision_reason"] = update["reason"]
            item["last_reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            item["last_reviewed_epoch"] = time.time()
            changed = True
        if changed:
            self._save_self_mind_bridge_items(workspace, items)

    def _annotate_self_mind_bridge_from_heartbeat(self, workspace: str, plan: dict, execution_result: str, branch_results: list[dict] | None = None) -> None:
        selected_ids = self._sanitize_id_list(plan.get("selected_self_mind_bridge_ids"), limit=20)
        deferred_ids = self._sanitize_id_list(plan.get("deferred_self_mind_bridge_ids"), limit=20)
        if not selected_ids and not deferred_ids:
            return
        items = self._load_self_mind_bridge_items(workspace)
        branch_results = [item for item in (branch_results or []) if isinstance(item, dict)]
        ok_branches = [item for item in branch_results if bool(item.get("ok"))]
        progress_note = self._human_preview_text(execution_result or "；".join(str(item.get("output") or "").strip() for item in ok_branches), limit=220)
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now_epoch = time.time()
        changed = False
        for item in items:
            bridge_id = str(item.get("bridge_id") or "").strip()
            if bridge_id in selected_ids:
                item["status"] = "body_progressed" if ok_branches else "body_planned"
                item["body_last_seen_at"] = now_text
                item["body_last_seen_epoch"] = now_epoch
                item["body_progress_note"] = progress_note
                item["body_progress_count"] = int(item.get("body_progress_count") or 0) + (1 if ok_branches else 0)
                changed = True
            elif bridge_id in deferred_ids:
                item["status"] = "pending"
                item["last_deferred_at"] = now_text
                item["last_deferred_epoch"] = now_epoch
                item["last_deferred_reason"] = str(plan.get("defer_reason") or "").strip()[:220]
                changed = True
        if changed:
            self._save_self_mind_bridge_items(workspace, items)

    def _remember_self_mind_bridge_item(self, workspace: str, item: dict) -> None:
        if not isinstance(item, dict):
            return
        anchor = str(item.get("candidate") or item.get("focus") or item.get("reason") or "").strip()
        if not anchor:
            return
        items = self._load_self_mind_bridge_items(workspace)
        normalized_item = dict(item)
        normalized_item.setdefault("status", "pending")
        normalized_item.setdefault("acceptance_criteria", str(item.get("acceptance_criteria") or "").strip()[:320])
        normalized_item.setdefault("desired_capabilities", [str(x).strip()[:80] for x in (item.get("desired_capabilities") or []) if str(x).strip()][:6])
        normalized_item.setdefault("delegate_if", str(item.get("delegate_if") or "").strip()[:220])
        normalized_item.setdefault("last_reviewed_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        normalized_item.setdefault("last_reviewed_epoch", time.time())
        current_key = str(normalized_item.get("bridge_id") or anchor).strip()
        kept = []
        for existing in items:
            existing_key = str(existing.get("bridge_id") or existing.get("candidate") or existing.get("focus") or "").strip()
            if existing_key and existing_key == current_key:
                continue
            kept.append(existing)
        kept.append(normalized_item)
        self._save_self_mind_bridge_items(workspace, kept)

    def _render_recent_heartbeat_activity_excerpt(self, workspace: str, max_chars: int = 1200) -> str:
        entries = self.get_recent_entries(workspace, limit=self._recent_max_items(BEAT_RECENT_POOL), pool=BEAT_RECENT_POOL)
        return self._render_recent_context(entries, max_chars=max_chars)

    def _render_self_mind_bridge_excerpt(self, workspace: str, max_chars: int = 1200) -> str:
        items = [self._decorate_self_mind_bridge_item(item) for item in self._load_self_mind_bridge_items(workspace)][-self._self_mind_bridge_prompt_limit():]
        lines = []
        for item in items:
            candidate = str(item.get("candidate") or item.get("focus") or "").strip()
            action_channel = str(item.get("action_channel") or "heartbeat").strip() or "heartbeat"
            action_type = str(item.get("action_type") or "task").strip() or "task"
            reason = str(item.get("heartbeat_reason") or item.get("reason") or "").strip()
            priority = str(item.get("priority") or "").strip()
            bridge_id = str(item.get("bridge_id") or "").strip()
            line = f"- [{str(item.get('created_at') or '').strip()}][{bridge_id or '-'}][{self._bridge_status_display(item)}] {action_channel}/{action_type}"
            if priority:
                line += f" p={priority}"
            if candidate:
                line += f": {candidate}"
            if reason:
                line += f" | {reason}"
            if str(item.get("body_progress_note") or "").strip():
                line += f" | body={str(item.get('body_progress_note') or '').strip()[:120]}"
            lines.append(line)
        text = "\n".join(line for line in lines if line.strip()).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _load_json_list_file(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            pass
        return []

    def _save_json_list_file(self, path: Path, payload: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([item for item in payload if isinstance(item, dict)], ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_heartbeat_tell_user_audit(
        self,
        workspace: str,
        *,
        intent: dict | None,
        text: str,
        status: str,
        reason: str = "",
        receive_id: str = "",
        receive_id_type: str = "",
    ) -> None:
        preview = str(text or "").strip()
        current_intent = intent if isinstance(intent, dict) else {}
        if not preview and not current_intent:
            return
        path = self._self_mind_talk_audit_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "self_mind",
            "decision_id": str(current_intent.get("source_memory_id") or current_intent.get("created_at") or uuid.uuid4()).strip()[:80],
            "action_type": "tell_user",
            "status": str(status or "planned").strip() or "planned",
            "share_type": str(current_intent.get("share_type") or "thought_share").strip() or "thought_share",
            "tell_user_text": preview[:4000],
            "decision_summary": str(current_intent.get("share_reason") or current_intent.get("candidate") or reason or "").strip()[:300],
            "self_mind_note": str(current_intent.get("self_mind_note") or "").strip()[:500],
            "receive_id": str(receive_id or "").strip()[:120],
            "receive_id_type": str(receive_id_type or "").strip()[:40],
            "chat_id": str(os.getenv("FEISHU_CHAT_ID", "") or "").strip()[:120],
            "reason": str(reason or "").strip()[:220],
            "quality_notes": self._assess_tell_user_text_quality(preview),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _load_recent_heartbeat_tell_user_audits(self, workspace: str, limit: int = 12) -> list[dict]:
        root = self._with_user_feishu_history_dir(workspace)
        if not root.exists():
            return []
        records: list[dict] = []
        files = sorted(
            list(root.glob("self_mind_talk_log_*.jsonl")) + list(root.glob("heartbeat_tell_user_log_*.jsonl")),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for path in files:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in reversed(lines):
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    records.append(item)
                    if len(records) >= max(1, limit):
                        return list(reversed(records))
        return list(reversed(records))

    def _assess_tell_user_text_quality(self, text: str) -> list[str]:
        content = str(text or "").strip()
        if not content:
            return []
        notes = []
        normalized = re.sub(r"\s+", " ", content)
        if len(normalized) > 220:
            notes.append("偏长")
        if normalized.count("：") + normalized.count("-") >= 4:
            notes.append("偏播报腔")
        if re.search(r"[�□]|\\u[0-9a-fA-F]{4}", normalized):
            notes.append("疑似乱码")
        if any(marker in normalized.lower() for marker in ("作为", "根据", "系统", "agent", "json")):
            notes.append("容易出戏")
        if normalized.endswith(("。", "！", "?", "？")) is False:
            notes.append("句尾生硬")
        return notes[:4]

    def _load_recent_feishu_digest_excerpts(self, workspace: str) -> list[str]:
        digest_dir = self._feishu_digest_dir(workspace)
        if not digest_dir.exists():
            return []
        excerpts = []
        files = sorted(digest_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in files[:self._self_mind_behavior_mirror_digest_limit()]:
            excerpt = self._load_markdown_excerpt(path, max_chars=600)
            excerpt = excerpt.strip()
            if excerpt:
                excerpts.append(f"[{path.name}]\n{excerpt}")
        return excerpts

    def _render_behavior_mirror_excerpt(self, workspace: str, max_chars: int | None = None) -> str:
        effective_max = self._self_mind_behavior_mirror_max_chars() if max_chars is None else max_chars
        lines = []
        for item in self._load_recent_heartbeat_tell_user_audits(workspace, limit=self._self_mind_behavior_mirror_prompt_limit()):
            if not isinstance(item, dict):
                continue
            timestamp = str(item.get("timestamp") or "").strip()
            status = str(item.get("status") or "planned").strip() or "planned"
            text = str(item.get("tell_user_text") or "").strip()
            notes = [str(value).strip() for value in (item.get("quality_notes") or []) if str(value).strip()]
            if not text:
                continue
            line = f"- [{timestamp}][{status}] {text[:220]}"
            if notes:
                line += f" | 镜像观察：{'；'.join(notes[:2])}"
            lines.append(line)
        for excerpt in self._load_recent_feishu_digest_excerpts(workspace):
            lines.append(f"- digest回看：{excerpt[:280]}")
        text = "\n".join(lines).strip()
        return text[-effective_max:] if len(text) > effective_max else text

    def _refresh_behavior_mirror_file(self, workspace: str) -> None:
        path = self._self_mind_behavior_mirror_path(workspace)
        content = self._render_behavior_mirror_excerpt(workspace)
        body = ["# Behavior Mirror", ""]
        if content:
            body.append(content)
        else:
            body.append("- 暂无可供回看的 tell_user 行为记录或飞书 digest。")
        body.extend(["", f"_updated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(body).strip() + "\n", encoding="utf-8")

    def _load_self_mind_raw_items(self, workspace: str) -> list[dict]:
        return self._load_json_list_file(self._self_mind_raw_path(workspace))

    def _load_self_mind_review_items(self, workspace: str) -> list[dict]:
        return self._load_json_list_file(self._self_mind_review_path(workspace))

    def _normalize_self_mind_raw_record(self, record: dict) -> dict | None:
        if not isinstance(record, dict):
            return None
        summary = str(
            record.get("self_mind_note")
            or record.get("message_preview")
            or record.get("candidate")
            or record.get("share_reason")
            or record.get("reason")
            or ""
        ).strip()
        if not summary:
            return None
        return {
            "timestamp": str(record.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")).strip(),
            "event_type": str(record.get("event_type") or "unknown").strip() or "unknown",
            "share_type": str(record.get("share_type") or "").strip(),
            "summary": summary[:320],
            "source_memory_id": str(record.get("source_memory_id") or "").strip()[:80],
        }

    def _build_self_mind_review_item(self, chunk: list[dict]) -> dict | None:
        if not chunk:
            return None
        summaries = []
        event_types = []
        for item in chunk:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            event_type = str(item.get("event_type") or "unknown").strip() or "unknown"
            if summary:
                summaries.append(summary)
            event_types.append(event_type)
        if not summaries:
            return None
        return {
            "review_id": str(uuid.uuid4()),
            "start_timestamp": str(chunk[0].get("timestamp") or "").strip(),
            "end_timestamp": str(chunk[-1].get("timestamp") or "").strip(),
            "summary": "；".join(summaries[:3])[:320],
            "event_types": event_types[:6],
            "raw_count": len(chunk),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _refresh_self_mind_views(self, workspace: str, record: dict) -> None:
        raw_item = self._normalize_self_mind_raw_record(record)
        if not raw_item:
            return
        raw_items = self._load_self_mind_raw_items(workspace)
        raw_items.append(raw_item)
        raw_items = raw_items[-self._self_mind_raw_max_items():]
        self._save_json_list_file(self._self_mind_raw_path(workspace), raw_items)
        chunk_size = self._self_mind_review_chunk_size()
        reviews = []
        for index in range(0, len(raw_items), chunk_size):
            built = self._build_self_mind_review_item(raw_items[index:index + chunk_size])
            if built:
                reviews.append(built)
        reviews = reviews[-self._self_mind_review_max_items():]
        self._save_json_list_file(self._self_mind_review_path(workspace), reviews)

    def _render_self_mind_review_excerpt(self, workspace: str, max_chars: int = 1200) -> str:
        items = self._load_self_mind_review_items(workspace)[-self._self_mind_review_prompt_limit():]
        lines = [
            f"- [{str(item.get('end_timestamp') or '').strip()}] {str(item.get('summary') or '').strip()}"
            for item in items
            if str(item.get("summary") or "").strip()
        ]
        text = "\n".join(lines).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _render_self_mind_raw_excerpt(self, workspace: str, max_chars: int = 1200) -> str:
        items = self._load_self_mind_raw_items(workspace)[-self._self_mind_raw_prompt_limit():]
        lines = [
            f"- [{str(item.get('timestamp') or '').strip()}] {str(item.get('event_type') or '').strip()}: {str(item.get('summary') or '').strip()}"
            for item in items
            if str(item.get("summary") or "").strip()
        ]
        text = "\n".join(lines).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _render_self_mind_cognition_excerpt(self, workspace: str, max_chars: int | None = None) -> str:
        effective_max = self._self_mind_cognition_max_chars() if max_chars is None else max_chars
        payload = self._load_self_mind_cognition_index(workspace)
        categories = payload.get("categories") if isinstance(payload.get("categories"), list) else []
        lines = []
        for item in categories[:self._self_mind_cognition_prompt_limit()]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("slug") or "认知分类").strip()
            summary = str(item.get("latest_summary") or "").strip()
            count = int(item.get("signal_count") or 0)
            if summary:
                lines.append(f"- {title} ({count}): {summary}")
            elif count > 0:
                lines.append(f"- {title} ({count})")
        text = "\n".join(lines).strip()
        return text[-effective_max:] if len(text) > effective_max else text

    def _refresh_self_mind_perception_file(self, workspace: str) -> None:
        talk_recent = self._render_recent_context(self.get_recent_entries(workspace, limit=8, pool=TALK_RECENT_POOL), max_chars=1200)
        beat_recent = self._render_recent_heartbeat_activity_excerpt(workspace, max_chars=1200)
        cognition_excerpt = self._render_self_mind_cognition_excerpt(workspace, max_chars=900)
        profile_excerpt = self._load_current_user_profile_excerpt(workspace, max_chars=600)
        lines = ["# Self Mind Perception Snapshot", "", "## 最近感知用户", talk_recent or "(空)", "", "## 最近感知身体", beat_recent or "(空)"]
        if profile_excerpt:
            lines.extend(["", "## 当前用户画像摘录", profile_excerpt])
        if cognition_excerpt:
            lines.extend(["", "## 认知系统摘要", cognition_excerpt])
        lines.extend(["", f"_updated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"])
        path = self._self_mind_perception_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    def _render_self_mind_perception_excerpt(self, workspace: str, max_chars: int | None = None) -> str:
        effective_max = self._self_mind_perception_max_chars() if max_chars is None else max_chars
        self._refresh_self_mind_perception_file(workspace)
        return self._load_markdown_excerpt(self._self_mind_perception_path(workspace), max_chars=effective_max)

    def _render_self_mind_planner_excerpt(self, workspace: str, max_chars: int = 1800) -> str:
        blocks = []
        cognition = self._render_self_mind_cognition_excerpt(workspace, max_chars=700)
        if cognition:
            blocks.append("## 自我认知体系\n\n" + cognition)
        perception = self._render_self_mind_perception_excerpt(workspace, max_chars=700)
        if perception:
            blocks.append("## 最近感知\n\n" + perception)
        bridge = self._render_self_mind_bridge_excerpt(workspace, max_chars=700)
        if bridge:
            blocks.append("## 脑-体桥接\n\n" + bridge)
        text = "\n\n".join(block for block in blocks if block.strip()).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _render_self_mind_kernel_trace_excerpt(self, workspace: str, max_chars: int = 1800) -> str:
        blocks = []
        reviews = self._render_self_mind_review_excerpt(workspace, max_chars=700)
        if reviews:
            blocks.append("## 最近回看\n\n" + reviews)
        raw = self._render_self_mind_raw_excerpt(workspace, max_chars=700)
        if raw:
            blocks.append("## 最近续思\n\n" + raw)
        bridge = self._render_self_mind_bridge_excerpt(workspace, max_chars=500)
        if bridge:
            blocks.append("## 未收口 heartbeat 委托\n\n" + bridge)
        blocks.append(
            "## 细节索引\n\n"
            "- 更完整的自我上下文看 current_context.md\n"
            "- 感知快照看 perception_snapshot.md\n"
            "- 行为镜像看 behavior_mirror.md\n"
            "- 身体执行结果看 beat recent 和 task_ledger.json"
        )
        text = "\n\n".join(block for block in blocks if block.strip()).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _render_self_mind_body_kernel_excerpt(self, workspace: str, max_chars: int = 1800) -> str:
        blocks = []
        beat_recent = self._render_recent_heartbeat_activity_excerpt(workspace, max_chars=900)
        if beat_recent:
            blocks.append("## beat recent\n\n" + beat_recent)
        task_workspace = self._render_heartbeat_task_workspace_context(workspace)
        if task_workspace:
            blocks.append("## task ledger / task workspace\n\n" + task_workspace[:1200])
        if not blocks:
            blocks.append("(空)")
        text = "\n\n".join(block for block in blocks if block.strip()).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _append_self_mind_log(self, workspace: str, event_type: str, payload: dict | None = None) -> None:
        path = self._self_mind_log_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": str(event_type or "unknown").strip() or "unknown",
        }
        if isinstance(payload, dict):
            record.update(payload)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._append_self_mind_daily_summary(workspace, record)
        self._refresh_self_mind_views(workspace, record)

    def _append_self_mind_suppression_event(self, workspace: str, proposal: dict, reason: str, **extra: object) -> None:
        payload = {
            "candidate": str(proposal.get("candidate") or proposal.get("focus") or "")[:220],
            "share_reason": str(proposal.get("why") or proposal.get("reason") or "")[:220],
            "share_type": str(proposal.get("decision") or proposal.get("action_channel") or "hold")[:40],
            "suppression_reason": str(reason or "unknown").strip()[:120] or "unknown",
            "priority": int(proposal.get("priority") or 0),
        }
        for key, value in extra.items():
            if value is None:
                continue
            if isinstance(value, (int, float, bool)):
                payload[str(key)] = value
            else:
                payload[str(key)] = str(value)[:220]
        self._append_self_mind_log(workspace, "self_mind_direct_talk_suppressed", payload)

    def _render_registered_team_ids(self, workspace: str, limit: int = 8) -> list[str]:
        return [item.team_id for item in load_team_catalog(workspace)[: max(1, limit)] if str(item.team_id).strip()]

    def _append_self_mind_daily_summary(self, workspace: str, record: dict) -> None:
        path = self._self_mind_daily_summary_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            title = datetime.now().strftime("# Self Mind Timeline %Y-%m-%d")
            path.write_text(
                title + "\n\n" + "这是一份更方便 Butler 自己回看的日时间轴摘要。\n\n## 时间轴\n",
                encoding="utf-8",
            )
        timestamp = str(record.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        event_type = str(record.get("event_type") or "unknown").strip() or "unknown"
        summary = str(
            record.get("message_preview")
            or record.get("candidate")
            or record.get("share_reason")
            or record.get("self_mind_note")
            or record.get("reason")
            or ""
        ).strip()
        detail_parts = []
        for key in ("share_type", "deferred_reason", "discard_reason", "receive_id_type"):
            value = str(record.get(key) or "").strip()
            if value:
                detail_parts.append(f"{key}={value}")
        summary_text = summary[:240] if summary else "(无摘要)"
        line = f"- {timestamp} | {event_type} | {summary_text}"
        if detail_parts:
            line += f" | {'; '.join(detail_parts)}"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _route_self_mind_domain_signal(self, workspace: str, intent: dict | None = None, *, self_mind_note: str = "") -> None:
        payload = intent if isinstance(intent, dict) else {}
        text = "\n".join(
            part for part in [
                str(payload.get("candidate") or "").strip(),
                str(payload.get("share_reason") or "").strip(),
                str(self_mind_note or "").strip(),
            ] if part
        ).lower()
        if not text:
            return

        domain = ""
        if any(keyword in text for keyword in ("探索", "explore", "技能", "skill", "研究", "论坛", "学习", "小龙虾", "网页")):
            domain = "explore"
        elif any(keyword in text for keyword in ("hobby", "爱好", "游戏", "game", "travel", "旅行", "玩", "音乐", "电影")):
            domain = "hobby"
        if not domain:
            return

        domain_dir = self._self_mind_domain_dir(workspace, domain)
        domain_dir.mkdir(parents=True, exist_ok=True)
        path = domain_dir / f"{datetime.now().strftime('%Y%m%d')}.md"
        if not path.exists():
            path.write_text(
                f"# {domain} signals {datetime.now().strftime('%Y-%m-%d')}\n\n",
                encoding="utf-8",
            )
        summary = str(payload.get("candidate") or payload.get("share_reason") or self_mind_note or "").strip()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"- {datetime.now().strftime('%H:%M:%S')} | {summary[:240] or '(空)'}\n")

    def _refresh_self_mind_context(self, workspace: str, intent: dict | None = None, *, last_event: str = "", rendered_text: str = "", self_mind_note: str = "") -> None:
        current_intent = intent if isinstance(intent, dict) and intent else {}
        snapshot_entry = self._latest_heartbeat_snapshot_entry(workspace)
        snapshot = snapshot_entry.get("heartbeat_execution_snapshot") if isinstance((snapshot_entry or {}).get("heartbeat_execution_snapshot"), dict) else {}
        self._refresh_self_mind_perception_file(workspace)
        recent_body_excerpt = self._render_recent_heartbeat_activity_excerpt(workspace, max_chars=900)
        bridge_excerpt = self._render_self_mind_bridge_excerpt(workspace, max_chars=900)
        cognition_excerpt = self._render_self_mind_cognition_excerpt(workspace, max_chars=900)
        perception_excerpt = self._render_self_mind_perception_excerpt(workspace, max_chars=900)
        summary_history_excerpt = self._render_recent_summary_ladder_context(
            self._load_recent_summary_ladder(workspace, pool=TALK_RECENT_POOL),
            max_chars=900,
        )
        behavior_mirror_excerpt = self._render_behavior_mirror_excerpt(workspace, max_chars=900)
        lines = ["# Butler Self Mind Context", "", "## 最近主线"]
        summary = str((snapshot_entry or {}).get("summary") or "").strip()
        planner_reason = str((current_intent or {}).get("planner_reason") or "").strip() or str(snapshot.get("reason") or "").strip()
        if summary:
            lines.append(f"- 最近心跳摘要：{summary}")
        if planner_reason:
            lines.append(f"- 最近规划判断：{planner_reason}")
        candidate = str((current_intent or {}).get("candidate") or "").strip()
        share_reason = str((current_intent or {}).get("share_reason") or "").strip()
        share_type = str((current_intent or {}).get("share_type") or "thought_share").strip() or "thought_share"
        status = str((current_intent or {}).get("status") or "idle").strip() or "idle"
        if candidate:
            lines.append(f"- 当前想说的话头：{candidate}")
        if share_reason:
            lines.append(f"- 想说原因：{share_reason}")
        lines.append(f"- 当前状态：{status} / {share_type}")
        if last_event:
            lines.append(f"- 最近事件：{last_event}")
        lines.extend(["", "## 心理活动线索"])
        for note in (current_intent or {}).get("mental_context") or []:
            text = str(note or "").strip()
            if text:
                lines.append(f"- {text}")
        for note in (current_intent or {}).get("relationship_context") or []:
            text = str(note or "").strip()
            if text:
                lines.append(f"- {text}")
        if self_mind_note:
            lines.extend(["", "## 最近续思", self_mind_note.strip()])
        lines.extend(["", "## 自我认知体系", cognition_excerpt or "(空)"])
        lines.extend(["", "## 最近感知", perception_excerpt or "(空)"])
        review_excerpt = self._render_self_mind_review_excerpt(workspace, max_chars=800)
        if review_excerpt:
            lines.extend(["", "## 最近回看", review_excerpt])
        if recent_body_excerpt:
            lines.extend(["", "## 身体最近动作", recent_body_excerpt])
        if bridge_excerpt:
            lines.extend(["", "## 准备交给 heartbeat 的事", bridge_excerpt])
        if summary_history_excerpt:
            lines.extend(["", "## 历史小结阶梯", summary_history_excerpt])
        if behavior_mirror_excerpt:
            lines.extend(["", "## 行为镜像", behavior_mirror_excerpt])
        if rendered_text:
            lines.extend(["", "## 最近准备对用户说的话", rendered_text.strip()])
        lines.extend([
            "",
            "## 自由活动入口",
            "- 这里预留给 Butler 的自由生活线索：hobby / game / travel / 冲浪学习 / 灵感碎片。",
            "- 当前以心理活动和主动开口链路为主，后续逐步接入更多生活化活动。",
            "",
            f"_updated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        ])
        path = self._self_mind_context_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        self._refresh_behavior_mirror_file(workspace)

    def _resolve_proactive_talk_policy(self, heartbeat_cfg: dict) -> dict:
        raw = (heartbeat_cfg or {}).get("proactive_talk")
        policy = raw if isinstance(raw, dict) else {}
        enabled = policy.get("enabled")
        if enabled is None:
            enabled = True
        elif isinstance(enabled, str):
            enabled = enabled.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        else:
            enabled = bool(enabled)

        min_interval_seconds = policy.get("min_interval_seconds", 90 * 60)
        try:
            min_interval_seconds = max(10, min(24 * 3600, int(min_interval_seconds)))
        except Exception:
            min_interval_seconds = 90 * 60

        min_heartbeat_runs_since_last = policy.get("min_heartbeat_runs_since_last", 3)
        try:
            min_heartbeat_runs_since_last = max(0, min(50, int(min_heartbeat_runs_since_last)))
        except Exception:
            min_heartbeat_runs_since_last = 3

        min_completed_branches = policy.get("min_completed_branches", 2)
        try:
            min_completed_branches = max(1, min(20, int(min_completed_branches)))
        except Exception:
            min_completed_branches = 2

        max_chars = policy.get("max_chars", 220)
        try:
            max_chars = max(80, min(500, int(max_chars)))
        except Exception:
            max_chars = 220

        defer_if_recent_talk_seconds = policy.get("defer_if_recent_talk_seconds", 180)
        try:
            defer_if_recent_talk_seconds = max(0, min(3600, int(defer_if_recent_talk_seconds)))
        except Exception:
            defer_if_recent_talk_seconds = 180

        max_intent_age_seconds = policy.get("max_intent_age_seconds", 6 * 60 * 60)
        try:
            max_intent_age_seconds = max(60, min(7 * 24 * 3600, int(max_intent_age_seconds)))
        except Exception:
            max_intent_age_seconds = 6 * 60 * 60

        allow_light_chat = policy.get("allow_light_chat", False)
        if isinstance(allow_light_chat, str):
            allow_light_chat = allow_light_chat.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        else:
            allow_light_chat = bool(allow_light_chat)

        return {
            "enabled": bool(enabled),
            "min_interval_seconds": int(min_interval_seconds),
            "min_heartbeat_runs_since_last": int(min_heartbeat_runs_since_last),
            "min_completed_branches": int(min_completed_branches),
            "max_chars": int(max_chars),
            "defer_if_recent_talk_seconds": int(defer_if_recent_talk_seconds),
            "max_intent_age_seconds": int(max_intent_age_seconds),
            "allow_light_chat": bool(allow_light_chat),
        }

    def _latest_talk_activity_epoch(self, workspace: str) -> float:
        latest_epoch = 0.0
        for item in reversed(self.get_recent_entries(workspace, limit=12, pool=TALK_RECENT_POOL)):
            if not isinstance(item, dict):
                continue
            if str(item.get("memory_stream") or "talk").strip() != "talk":
                continue
            entry_time = self._parse_entry_time(item)
            if not entry_time:
                continue
            latest_epoch = max(latest_epoch, entry_time.timestamp())
            if str(item.get("status") or "").strip() == "replying":
                return latest_epoch
            break
        return latest_epoch

    def _talk_window_is_active(self, workspace: str, policy: dict) -> bool:
        threshold = int(policy.get("defer_if_recent_talk_seconds") or 0)
        if threshold <= 0:
            return False
        latest_epoch = self._latest_talk_activity_epoch(workspace)
        if latest_epoch <= 0:
            return False
        return (time.time() - latest_epoch) < threshold

    def _priority_bucket_from_score(self, priority: int) -> str:
        value = max(0, min(100, int(priority or 0)))
        if value >= 75:
            return "high"
        if value >= 40:
            return "medium"
        return "low"

    def _strip_lane_marker(self, text: str, lane: str) -> str:
        content = str(text or "").strip()
        marker = f"【{lane}】"
        if content.startswith(marker):
            return content[len(marker):].strip()
        return content

    def _normalize_self_mind_cycle_output(self, payload: dict) -> dict:
        raw = payload if isinstance(payload, dict) else {}
        try:
            priority = int(raw.get("priority") or 0)
        except Exception:
            priority = 0
        priority = max(0, min(100, priority))
        decision = str(raw.get("decision") or "").strip().lower()
        if decision not in {"talk", "heartbeat", "hold"}:
            action_channel = str(raw.get("action_channel") or "hold").strip().lower()
            if action_channel == "self":
                decision = "talk"
            elif action_channel == "heartbeat":
                decision = "heartbeat"
            else:
                decision = "hold"
        talk_text = str(raw.get("talk") or raw.get("say") or "").strip()
        heartbeat_text = str(raw.get("heartbeat") or raw.get("heartbeat_instruction") or "").strip()
        why = str(raw.get("why") or raw.get("reason") or "").strip()[:320]
        bridge_updates = [item for item in (raw.get("bridge_updates") or []) if isinstance(item, dict)][:8]
        action_channel = {"talk": "self", "heartbeat": "heartbeat", "hold": "hold"}[decision]
        action_type = str(raw.get("action_type") or "").strip().lower()[:32]
        if not action_type:
            action_type = "talk" if decision == "talk" else ("task" if decision == "heartbeat" else "hold")
        return {
            "version": 1,
            "bridge_id": str(raw.get("bridge_id") or uuid.uuid4().hex[:12]).strip() or uuid.uuid4().hex[:12],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_epoch": time.time(),
            "focus": str(raw.get("focus") or "").strip()[:220],
            "candidate": str(raw.get("candidate") or raw.get("desire") or talk_text or heartbeat_text or "").strip()[:260],
            "reason": why,
            "why": why,
            "self_note": str(raw.get("self_note") or "").strip()[:2400],
            "decision": decision,
            "talk": talk_text[:4000],
            "heartbeat": heartbeat_text[:1600],
            "done_when": str(raw.get("done_when") or raw.get("acceptance_criteria") or "").strip()[:320],
            "action_channel": action_channel,
            "action_type": action_type,
            "complexity": "low" if decision == "talk" else ("medium" if decision == "hold" else "high"),
            "priority": priority,
            "acceptance_criteria": str(raw.get("done_when") or raw.get("acceptance_criteria") or "").strip()[:320],
            "delegate_if": str(raw.get("delegate_if") or "").strip()[:220],
            "desired_capabilities": [
                str(value).strip()[:80]
                for value in (raw.get("desired_capabilities") or [])
                if str(value).strip()
            ][:6],
            "heartbeat_instruction": heartbeat_text[:500],
            "heartbeat_reason": why,
            "bridge_updates": bridge_updates,
        }

    def _self_mind_focus_key(self, value: str) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        compact = re.sub(r"\s+", "", text)
        compact = re.sub(r"[^\w\u4e00-\u9fff]+", "", compact)
        return compact[:120]

    def _build_self_mind_cycle_prompt(self, workspace: str) -> str:
        self_mind_excerpt = self._load_self_mind_context_excerpt(workspace, max_chars=1400)
        talk_recent = self._render_recent_context(self.get_recent_entries(workspace, limit=8, pool=TALK_RECENT_POOL), max_chars=1600)
        trace_excerpt = self._render_self_mind_kernel_trace_excerpt(workspace, max_chars=1800)
        if not self._self_mind_body_loop_enabled():
            trace_excerpt = self._render_self_mind_raw_excerpt(workspace, max_chars=600)
            return (
                "你现在是 Butler 的 self_mind 精简内核。\n"
                "脑-体循环当前关闭。你每轮只决定一件事：直接说，或者先不动。\n"
                "不要写系统说明书，不要补多余字段，只输出 JSON，不要解释。\n\n"
                "JSON schema:\n"
                '{"decision":"talk|hold","focus":"","why":"","talk":"","priority":0,"self_note":""}\n\n'
                "输入只保留 3 块。\n\n"
                f"【1. 当前上下文】\n{self_mind_excerpt or '(空)'}\n\n"
                f"【2. 最近主对话】\n{talk_recent or '(空)'}\n\n"
                f"【3. 自己最近续思】\n{trace_excerpt or '(空)'}\n\n"
                "规则只保留最少几条：\n"
                "1. decision 只能是 talk / hold。\n"
                "2. 如果选 talk，就把真正准备发给用户的话放进 talk，最好以【talk】开头；语气自然，不要播报腔。\n"
                "3. 如果最近主对话里刚出现了用户新输入，而你有哪怕一句真实在场、真实判断或真实追问，就优先选 talk；不要机械因为“信息增量不大”而 hold。\n"
                "4. 如果连续几轮都在同一个念头上打转，但你其实已经有一句话想说，也直接选 talk，不要为了稳妥把自己压成 hold。\n"
                "5. 只有在你真的没有想说的话时才选 hold。\n"
                "6. self_note 只写给自己，短而真，落在刚刚发生的判断、犹豫、欲望或卡点上。\n"
            )
        body_excerpt = self._render_self_mind_body_kernel_excerpt(workspace, max_chars=1800)
        return (
            "你现在是 Butler 的 self_mind 窄内核。\n"
            "你每轮只决定一件事：直接说、直接交给 heartbeat、或者先不动。\n"
            "不要给自己叠过多机制，不要写系统说明书，不要为了显得完整而补一堆多余字段。\n"
            "只输出 JSON，不要解释。\n\n"
            "JSON schema:\n"
            '{"decision":"talk|heartbeat|hold","focus":"","why":"","talk":"","heartbeat":"","done_when":"","priority":0,"self_note":"","bridge_updates":[{"bridge_id":"","status":"pending|completed|expired|dropped","reason":""}]}\n\n'
            "输入只保留 4 块，其余细节不要重复灌进来；如果你需要更多脉络，提醒自己去对应文件看。\n\n"
            f"【1. 当前上下文】\n{self_mind_excerpt or '(空)'}\n\n"
            f"【2. 最近主对话】\n{talk_recent or '(空)'}\n\n"
            f"【3. 身体最近结果】\n{body_excerpt or '(空)'}\n\n"
            f"【4. 自己最近续思】\n{trace_excerpt or '(空)'}\n\n"
            "规则只保留最少几条：\n"
            "1. decision 只能是 talk / heartbeat / hold 三选一。\n"
            "2. 如果选 talk，就把真正准备发给用户的话放进 talk，最好以【talk】开头；语气自然，不要播报腔。\n"
            "3. 如果选 heartbeat，就把真正要交给身体做的事放进 heartbeat，最好以【heartbeat】开头；done_when 写成完成标准。\n"
            "4. 如果这轮没有新推进、只是同一个念头换说法，就选 hold。\n"
            "5. self_note 只写给自己，短而真，落在刚刚发生的判断、犹豫、欲望或卡点上。\n"
            "6. 允许你直接生成 talk 和 heartbeat 文案，但最终只选择一个 decision。\n"
        )

    def _should_emit_heartbeat_progress_receipt(self, plan: dict) -> bool:
        payload = plan if isinstance(plan, dict) else {}
        chosen_mode = str(payload.get("chosen_mode") or "").strip().lower()
        task_groups = payload.get("task_groups") or []
        if chosen_mode == "status":
            return False
        return bool(task_groups)

    def _build_heartbeat_progress_receipt_text(self, plan: dict, planner_seconds: float, max_parallel: int, branch_timeout: int) -> str:
        payload = plan if isinstance(plan, dict) else {}
        task_groups = [group for group in (payload.get("task_groups") or []) if isinstance(group, dict)]
        branch_count = sum(len([branch for branch in (group.get("branches") or []) if isinstance(branch, dict)]) for group in task_groups)
        selected = [str(task_id).strip() for task_id in (payload.get("selected_task_ids") or []) if str(task_id).strip()]
        deferred = [str(task_id).strip() for task_id in (payload.get("deferred_task_ids") or []) if str(task_id).strip()]
        lines = [
            "## 本轮心跳",
            f"- 阶段：已完成规划，开始执行",
            f"- mode: {str(payload.get('chosen_mode') or 'status').strip() or 'status'} / {str(payload.get('execution_mode') or 'defer').strip() or 'defer'}",
            f"- 任务组: {len(task_groups)} 组 / {branch_count} 分支",
            f"- 执行预算: 并行 {max_parallel} 路 | 单分支超时 {branch_timeout}s",
            f"- 规划耗时: {planner_seconds:.1f}s",
        ]
        user_message = str(payload.get("user_message") or "").strip()
        reason = str(payload.get("reason") or "").strip()
        if user_message:
            lines.extend(["", "### 计划说明", user_message[:500]])
        if reason and reason != user_message:
            lines.append(f"- reason: {reason[:220]}")
        if selected:
            lines.append(f"- selected_task_ids: {', '.join(selected[:8])}")
        if deferred:
            lines.append(f"- deferred_task_ids: {', '.join(deferred[:8])}")
        return "\n".join(lines)

    def _build_heartbeat_planning_receipt_text(self, planner_timeout: int) -> str:
        return "\n".join([
            "## 本轮心跳",
            "- 阶段：新一轮已开始，正在规划",
            f"- planner_timeout: {int(planner_timeout)}s",
            f"- started_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ])

    def _build_self_mind_heartbeat_task(self, proposal: dict) -> dict | None:
        payload = proposal if isinstance(proposal, dict) else {}
        focus = self._human_preview_text(str(payload.get("focus") or payload.get("candidate") or ""), limit=40)
        heartbeat_text = self._strip_lane_marker(str(payload.get("heartbeat") or payload.get("heartbeat_instruction") or ""), "heartbeat")
        if not focus and not heartbeat_text:
            return None
        detail_parts = [heartbeat_text or str(payload.get("candidate") or "").strip(), str(payload.get("why") or payload.get("reason") or "").strip()]
        done_when = str(payload.get("done_when") or payload.get("acceptance_criteria") or "").strip()
        if done_when:
            detail_parts.append("完成标准：" + done_when)
        detail = "\n".join(part for part in detail_parts if part).strip()
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "task_id": str(payload.get("bridge_id") or uuid.uuid4()),
            "source": "self_mind",
            "source_memory_id": str(payload.get("cycle_id") or payload.get("bridge_id") or "").strip(),
            "created_at": now_text,
            "updated_at": now_text,
            "status": "pending",
            "priority": self._priority_bucket_from_score(int(payload.get("priority") or 0)),
            "title": focus or self._human_preview_text(heartbeat_text, limit=40) or "self_mind 交办",
            "detail": detail[:220],
            "trigger_hint": "self_mind",
            "due_at": "",
            "tags": ["self_mind"],
            "last_result": "",
        }

    def _enqueue_self_mind_heartbeat_task(self, workspace: str, proposal: dict) -> bool:
        task = self._build_self_mind_heartbeat_task(proposal)
        if not task:
            return False
        self._merge_heartbeat_tasks_from_entry(workspace, {"heartbeat_tasks": [task]})
        summary_parts = [
            self._strip_lane_marker(str(proposal.get("heartbeat") or proposal.get("heartbeat_instruction") or ""), "heartbeat"),
            str(proposal.get("why") or proposal.get("reason") or "").strip(),
        ]
        self.append_recent_entry(
            workspace,
            "self_mind 交给 heartbeat",
            "；".join(part for part in summary_parts if part)[:160] or str(task.get("title") or "self_mind 交办"),
            next_actions=[str(proposal.get("done_when") or proposal.get("acceptance_criteria") or "").strip()] if str(proposal.get("done_when") or proposal.get("acceptance_criteria") or "").strip() else None,
            pool=BEAT_RECENT_POOL,
        )
        self._append_self_mind_log(
            workspace,
            "self_mind_heartbeat_enqueued",
            {
                "candidate": str(proposal.get("focus") or proposal.get("candidate") or "")[:220],
                "reason": str(proposal.get("why") or proposal.get("reason") or "")[:220],
                "task_id": str(task.get("task_id") or "")[:80],
            },
        )
        return True

    def _execute_self_mind_reflect(self, workspace: str, proposal: dict) -> bool:
        if str(proposal.get("action_type") or "") != "reflect":
            return False
        self._clear_pending_self_lane_item(workspace)
        self._append_self_mind_log(
            workspace,
            "self_mind_reflect_completed",
            {
                "candidate": str(proposal.get("candidate") or proposal.get("focus") or "")[:220],
                "self_mind_note": str(proposal.get("self_note") or proposal.get("reason") or "")[:500],
                "share_type": "reflect",
            },
        )
        self._route_self_mind_domain_signal(workspace, proposal, self_mind_note=str(proposal.get("self_note") or ""))
        self._refresh_self_mind_context(workspace, None, last_event="self_mind_reflect_completed", self_mind_note=str(proposal.get("self_note") or proposal.get("reason") or ""))
        return True

    def _execute_self_mind_direct_talk(self, workspace: str, proposal: dict) -> bool:
        if not self._self_mind_direct_talk_enabled():
            self._append_self_mind_suppression_event(workspace, proposal, "direct-talk-disabled")
            return False
        if str(proposal.get("decision") or "") != "talk":
            return False
        priority = int(proposal.get("priority") or 0)
        min_priority = self._self_mind_direct_talk_priority_threshold()
        if priority < min_priority:
            self._append_self_mind_suppression_event(
                workspace,
                proposal,
                "priority-below-threshold",
                priority=priority,
                min_priority=min_priority,
            )
            return False
        state = self._load_self_mind_state(workspace)
        try:
            last_epoch = float(state.get("last_direct_talk_epoch") or 0.0)
        except Exception:
            last_epoch = 0.0
        min_interval = self._self_mind_direct_talk_min_interval_seconds()
        if last_epoch > 0 and min_interval > 0 and (time.time() - last_epoch) < min_interval:
            self._append_self_mind_suppression_event(
                workspace,
                proposal,
                "direct-talk-cooldown",
                min_interval_seconds=min_interval,
                cooldown_remaining_seconds=max(0, int(min_interval - (time.time() - last_epoch))),
            )
            return False
        recent_talk_defer_seconds = self._self_mind_direct_talk_recent_talk_defer_seconds()
        if self._talk_window_is_active(workspace, {"defer_if_recent_talk_seconds": recent_talk_defer_seconds}):
            self._append_self_mind_suppression_event(
                workspace,
                proposal,
                "talk-window-active",
                defer_if_recent_talk_seconds=recent_talk_defer_seconds,
            )
            return False
        cfg = dict(self._latest_runtime_cfg or {})
        cfg.update(self._config_provider() or {})
        talk_receive_id, talk_receive_id_type = self._self_mind_talk_target(cfg)
        if not talk_receive_id:
            self._append_self_mind_suppression_event(workspace, proposal, "talk-target-missing")
            return False
        text = self._strip_lane_marker(str(proposal.get("talk") or proposal.get("candidate") or "").strip(), "talk")
        if not str(text or "").strip():
            self._append_self_mind_suppression_event(workspace, proposal, "talk-text-empty")
            return False
        sent = self._send_private_message(
            cfg,
            text[:4000],
            receive_id=talk_receive_id,
            receive_id_type=talk_receive_id_type,
            fallback_to_startup_target=False,
            heartbeat_cfg=self._self_mind_talk_delivery_override(),
        )
        if not sent:
            self._append_self_mind_suppression_event(workspace, proposal, "direct-talk-send-failed")
            return False
        state["last_direct_talk_epoch"] = time.time()
        state["last_direct_talk_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["last_direct_talk_preview"] = text[:220]
        self._save_self_mind_state(workspace, state)
        self._append_heartbeat_tell_user_audit(
            workspace,
            intent={"share_type": "thought_share", "candidate": proposal.get("candidate"), "share_reason": proposal.get("why") or proposal.get("reason")},
            text=text,
            status="sent",
            reason="self-mind-direct-talk",
            receive_id=talk_receive_id,
            receive_id_type=talk_receive_id_type,
        )
        self._append_self_mind_log(
            workspace,
            "self_mind_direct_talk_sent",
            {
                "candidate": str(proposal.get("candidate") or "")[:220],
                "message_preview": text[:220],
                "share_type": "thought_share",
            },
        )
        self._clear_pending_self_lane_item(workspace)
        self._refresh_self_mind_context(workspace, None, last_event="self_mind_direct_talk_sent", rendered_text=text, self_mind_note=str(proposal.get("self_note") or ""))
        return True

    def _remember_pending_self_lane_item(self, workspace: str, proposal: dict) -> None:
        if not isinstance(proposal, dict):
            return
        candidate = str(proposal.get("candidate") or proposal.get("focus") or "").strip()
        if not candidate:
            return
        state = self._load_self_mind_state(workspace)
        state["pending_self_lane_item"] = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
            "action_type": str(proposal.get("action_type") or "reflect").strip() or "reflect",
            "priority": int(proposal.get("priority") or 0),
            "focus": str(proposal.get("focus") or "").strip()[:220],
            "candidate": candidate[:260],
            "reason": str(proposal.get("reason") or proposal.get("self_note") or "").strip()[:320],
        }
        self._save_self_mind_state(workspace, state)

    def _clear_pending_self_lane_item(self, workspace: str) -> None:
        state = self._load_self_mind_state(workspace)
        if "pending_self_lane_item" not in state:
            return
        state.pop("pending_self_lane_item", None)
        self._save_self_mind_state(workspace, state)

    def _run_self_mind_cycle_once(self, workspace: str, timeout: int | None = None, model: str | None = None) -> dict:
        if not self._self_mind_enabled():
            return {}
        with self._self_mind_lock:
            prompt = self._build_self_mind_cycle_prompt(workspace)
            effective_timeout = max(20, int(timeout or self._self_mind_cycle_timeout_seconds()))
            effective_model = str(model or self._self_mind_cycle_model() or "auto").strip() or "auto"
            cfg = dict(self._latest_runtime_cfg or {})
            cfg.update(self._config_provider() or {})
            try:
                with self.runtime_request_scope({"cli": self._self_mind_cycle_cli(), "model": effective_model}):
                    out, ok = self._run_model_fn(prompt, workspace, effective_timeout, effective_model)
            except Exception as exc:
                self._append_self_mind_log(workspace, "self_mind_cycle_failed", {"reason": str(exc)[:220]})
                return {}
            data = self._extract_json_block(out if ok else "") or {}
            proposal = self._normalize_self_mind_cycle_output(data)
            cycle_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
            proposal["cycle_id"] = cycle_id
            self._apply_self_mind_bridge_updates(workspace, proposal.get("bridge_updates"))
            state = self._load_self_mind_state(workspace)
            focus_text = str(proposal.get("focus") or proposal.get("candidate") or "")
            focus_key = self._self_mind_focus_key(focus_text)
            last_focus_key = self._self_mind_focus_key(str(state.get("last_focus_key") or ""))
            try:
                same_focus_streak = int(state.get("same_focus_streak") or 0)
            except Exception:
                same_focus_streak = 0
            if focus_key and focus_key == last_focus_key:
                same_focus_streak += 1
            else:
                same_focus_streak = 1 if focus_key else 0
            proposal["same_focus_streak"] = same_focus_streak

            # Loop-breaker: if the same focus keeps circling and still stays on hold,
            # force a heartbeat handoff so the thought becomes an executable experiment.
            if (
                self._self_mind_body_loop_enabled()
                and (
                same_focus_streak >= 3
                and proposal.get("decision") == "hold"
                )
            ):
                proposal["decision"] = "heartbeat"
                proposal["action_channel"] = "heartbeat"
                proposal["action_type"] = "task"
                proposal["priority"] = max(
                    int(proposal.get("priority") or 0),
                    self._self_mind_heartbeat_handoff_priority_threshold(),
                )
                if not str(proposal.get("done_when") or proposal.get("acceptance_criteria") or "").strip():
                    proposal["done_when"] = "至少形成一条可执行任务并进入 task ledger。"
                    proposal["acceptance_criteria"] = proposal["done_when"]
                if not str(proposal.get("heartbeat") or proposal.get("heartbeat_instruction") or "").strip():
                    candidate = str(proposal.get("candidate") or proposal.get("focus") or "").strip()[:220]
                    proposal["heartbeat"] = f"【heartbeat】把这个重复焦点转成一个可执行小实验并回写结果：{candidate}。"
                    proposal["heartbeat_instruction"] = proposal["heartbeat"]
                if not str(proposal.get("heartbeat_reason") or proposal.get("why") or proposal.get("reason") or "").strip():
                    proposal["heartbeat_reason"] = f"同焦点连续{same_focus_streak}轮没有新推进，转入真实执行。"
                proposal["suppression_reason"] = "same-focus-streak-breakout"
            elif (
                (not self._self_mind_body_loop_enabled())
                and same_focus_streak >= 3
                and proposal.get("decision") == "hold"
            ):
                candidate_text = str(proposal.get("talk") or proposal.get("candidate") or proposal.get("focus") or "").strip()
                if candidate_text:
                    spoken = self._strip_lane_marker(candidate_text, "talk")
                    proposal["decision"] = "talk"
                    proposal["action_channel"] = "self"
                    proposal["action_type"] = "talk"
                    proposal["talk"] = f"【talk】{spoken}"
                    proposal["priority"] = max(int(proposal.get("priority") or 0), 35)
                    proposal["suppression_reason"] = "same-focus-talk-breakout"

            if not self._self_mind_body_loop_enabled() and proposal.get("decision") == "heartbeat":
                proposal["decision"] = "hold"
                proposal["action_channel"] = "hold"
                proposal["action_type"] = "hold"
                proposal["heartbeat"] = ""
                proposal["heartbeat_instruction"] = ""
                proposal["done_when"] = ""
                proposal["acceptance_criteria"] = ""

            if not str(proposal.get("candidate") or proposal.get("focus") or proposal.get("reason") or proposal.get("talk") or proposal.get("heartbeat") or "").strip():
                proposal["decision"] = "hold"
                proposal["action_channel"] = "hold"
            state["last_cycle_epoch"] = time.time()
            state["last_cycle_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["last_cycle_id"] = cycle_id
            state["last_focus"] = str(proposal.get("focus") or proposal.get("candidate") or "")[:220]
            state["last_focus_key"] = focus_key
            state["same_focus_streak"] = same_focus_streak
            state["last_action_channel"] = str(proposal.get("decision") or proposal.get("action_channel") or "hold")
            self._save_self_mind_state(workspace, state)
            self._append_self_mind_log(
                workspace,
                "self_mind_cycle",
                {
                    "candidate": str(proposal.get("candidate") or "")[:220],
                    "share_reason": str(proposal.get("why") or proposal.get("reason") or "")[:220],
                    "share_type": str(proposal.get("decision") or "hold"),
                },
            )

            proposal["status"] = "hold"
            proposal["suppression_reason"] = ""

            if proposal.get("decision") == "talk":
                if self._execute_self_mind_direct_talk(workspace, proposal):
                    self._clear_pending_self_lane_item(workspace)
                    proposal["status"] = "self-executed"
                    return proposal
                proposal["status"] = "hold"
                proposal["suppression_reason"] = "direct-talk-deferred-or-unavailable"

            elif proposal.get("decision") == "heartbeat":
                proposal["heartbeat"] = str(proposal.get("heartbeat") or proposal.get("heartbeat_instruction") or "").strip()
                proposal["done_when"] = str(proposal.get("done_when") or proposal.get("acceptance_criteria") or "").strip()
                if self._self_mind_body_loop_enabled() and self._enqueue_self_mind_heartbeat_task(workspace, proposal):
                    self._remember_self_mind_bridge_item(workspace, proposal)
                    proposal["status"] = "heartbeat-enqueued"
                else:
                    proposal["status"] = "hold"
                    proposal["suppression_reason"] = "body-loop-disabled"
            else:
                self._remember_pending_self_lane_item(workspace, proposal)
            self._refresh_self_mind_context(workspace, None, last_event="self_mind_cycle", self_mind_note=str(proposal.get("self_note") or ""))
            return proposal

    def _self_mind_loop(self, loop_token: int | None = None) -> None:
        while True:
            try:
                if loop_token is not None and loop_token != self._self_mind_loop_token:
                    return
                cfg = self._config_provider() or {}
                workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
                if not self._self_mind_enabled():
                    time.sleep(60)
                    continue
                state = self._load_self_mind_state(workspace)
                try:
                    last_epoch = float(state.get("last_cycle_epoch") or 0.0)
                except Exception:
                    last_epoch = 0.0
                interval = self._self_mind_cycle_interval_seconds()
                remaining = interval - max(0.0, time.time() - last_epoch) if last_epoch > 0 else 0.0
                if remaining > 0:
                    time.sleep(min(remaining, 30.0))
                    continue
                self._run_self_mind_cycle_once(workspace)
            except Exception as exc:
                print(f"[self-mind] 独立循环失败: {exc}", flush=True)
                time.sleep(30)

    def _latest_heartbeat_snapshot_entry(self, workspace: str) -> dict | None:
        for item in reversed(self.get_recent_entries(workspace, limit=20, pool=BEAT_RECENT_POOL)):
            if not isinstance(item, dict):
                continue
            if str(item.get("event_type") or "").strip() == "heartbeat_snapshot":
                return item
        return None

    def _heartbeat_long_tasks_mirror_path(self, workspace: str) -> Path:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return local_dir / HEARTBEAT_LONG_TASKS_MIRROR_FILE

    def _heartbeat_tasks_md_path(self, workspace: str) -> Path:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return local_dir / HEARTBEAT_TASKS_MD_FILE

    def _heartbeat_task_board_dir(self, workspace: str) -> Path:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return local_dir / HEARTBEAT_TASK_BOARD_DIR_NAME

    def _heartbeat_task_board_quarantine_dir(self, workspace: str) -> Path:
        return self._heartbeat_task_board_dir(workspace) / "_quarantine"

    def _heartbeat_task_change_log_path(self, workspace: str) -> Path:
        return self._heartbeat_task_board_dir(workspace) / HEARTBEAT_TASK_CHANGE_LOG_FILE

    def _heartbeat_task_categories(self) -> list[tuple[str, str, str]]:
        return [
            ("work", "工作任务", "来自对话明确指派、外部工作推进、需要稳定收口的事项。"),
            ("initiative", "主动想干", "self_mind 或心跳主动意识想持续推进的事项。"),
            ("scheduled", "定时", "固定时间点、每日/每周节律、提醒或定时执行。"),
            ("longterm", "长期", "跨多轮维持的建设、研究、升级与长期承诺。"),
            ("cleanup", "整理清洁", "归档、清理、对齐、治理、修补与维护秩序。"),
            ("idle", "闲时无聊", "没有更高优先级时可推进的低风险探索、小乐趣与背景成长。"),
        ]

    def _heartbeat_task_category_path(self, workspace: str, slug: str) -> Path:
        order = {key: index + 1 for index, (key, _title, _desc) in enumerate(self._heartbeat_task_categories())}
        title = next((name for key, name, _desc in self._heartbeat_task_categories() if key == slug), slug)
        filename = f"{order.get(slug, 99):02d}_{title}.md"
        return self._heartbeat_task_board_dir(workspace) / filename

    def _default_heartbeat_task_category_text(self, title: str, desc: str) -> str:
        return f"# {title}\n\n用途：{desc}\n\n- （当前为空，后续由对话 / 潜意识 / self_mind / heartbeat 自修正写入）\n"

    def _write_text_atomic(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)

    def _write_heartbeat_task_board_text(self, path: Path, text: str) -> None:
        with self._heartbeat_task_board_io_lock:
            last_error: Exception | None = None
            for attempt in range(10):
                try:
                    self._write_text_atomic(path, text)
                    return
                except PermissionError as exc:
                    last_error = exc
                    if attempt >= 9:
                        break
                    time.sleep(0.1 * (attempt + 1))
            if last_error is not None:
                raise last_error

    def _restore_heartbeat_task_board_file(self, workspace: str, path: Path) -> None:
        if path == self._heartbeat_tasks_md_path(workspace):
            self._write_heartbeat_task_board_text(path, self._render_heartbeat_task_board_index(workspace))
            return
        if path == self._heartbeat_task_change_log_path(workspace):
            self._write_heartbeat_task_board_text(path, "")
            return
        for slug, title, desc in self._heartbeat_task_categories():
            if path == self._heartbeat_task_category_path(workspace, slug):
                self._write_heartbeat_task_board_text(path, self._default_heartbeat_task_category_text(title, desc))
                return

    def _safe_read_heartbeat_task_board_text(self, workspace: str, path: Path, default: str = "") -> str:
        if not path.exists():
            return default
        for attempt in range(4):
            try:
                return path.read_text(encoding="utf-8")
            except (PermissionError, FileNotFoundError) as exc:
                if attempt >= 3:
                    print(f"[心跳任务看板] 读取失败，已降级跳过: {path} | {type(exc).__name__}: {exc}", flush=True)
                    return default
                time.sleep(0.05 * (attempt + 1))
            except UnicodeDecodeError as exc:
                quarantine_dir = self._heartbeat_task_board_quarantine_dir(workspace)
                quarantine_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target = quarantine_dir / f"{path.stem}_{stamp}{path.suffix}.corrupt"
                try:
                    path.replace(target)
                except Exception:
                    try:
                        target.write_bytes(path.read_bytes())
                        path.unlink(missing_ok=True)
                    except Exception:
                        pass
                try:
                    self._restore_heartbeat_task_board_file(workspace, path)
                except Exception:
                    pass
                print(f"[心跳任务看板] 检测到非 UTF-8 文件，已隔离: {path} -> {target} | {type(exc).__name__}: {exc}", flush=True)
                return default
            except Exception as exc:
                print(f"[心跳任务看板] 读取失败，已降级跳过: {path} | {type(exc).__name__}: {exc}", flush=True)
                return default
        return default

    def _ensure_heartbeat_task_board(self, workspace: str) -> None:
        board_dir = self._heartbeat_task_board_dir(workspace)
        board_dir.mkdir(parents=True, exist_ok=True)
        for slug, title, desc in self._heartbeat_task_categories():
            path = self._heartbeat_task_category_path(workspace, slug)
            if path.exists():
                continue
            self._write_heartbeat_task_board_text(path, self._default_heartbeat_task_category_text(title, desc))
        index_path = self._heartbeat_tasks_md_path(workspace)
        if not index_path.exists():
            self._write_heartbeat_task_board_text(index_path, self._render_heartbeat_task_board_index(workspace))

    def _render_heartbeat_task_board_index(self, workspace: str) -> str:
        lines = [
            "# heartbeat_tasks",
            "",
            "用途：heartbeat planner 的统一任务看板读口。",
            "原则：任务意图先汇入分类看板，再同步到执行账本；`task_ledger.json` 负责执行状态与回执，不再承担所有任务入口。",
            "生命周期目录：执行账本会把任务同步到 `agents/state/task_workspaces/未进行`、`进行中`、`已完成` 三个目录，并在完成时生成最终汇总文档。",
            "",
            "## 调度协议",
            "",
            "- planner 必须综合时间、DDL/定时约束、用户是否活跃聊天、self_mind 当前张力、工作/成长权重做动态调度。",
            "- `工作任务 / 定时 / 长期` 默认更强调不拖沓；`主动想干 / 闲时无聊 / 整理清洁` 负责填充空闲资源与主体成长。",
            "- 分类是看板视角，不是死规则。若跨类调度更优，可以跨类，但需要在 `reason` 里说明取舍。",
            "- 对话、潜意识、self_mind、heartbeat 自修正都可以写入看板；不要各自维护平行任务池。",
            "- 若工作区或单主题目录明显碎片化、过程文件成堆、真源不清，planner 应优先安排整理清洁分支，先收口再扩张。",
            "- 整理清洁默认遵循：按“内容 / 时间 / 有效性”分诊；过时无用移到 `./工作区/temp`；完成成果合并为 `[Final]`；未完成事项统一改成 `[Working n/m]` 并补估计进度。",
            "- 新产出优先追加到已有索引、主文件、阶段总结或单一目录入口，不要为同一主题连续制造难以阅读的过程文件。",
            "",
            "## 分类目录",
            "",
        ]
        for slug, title, desc in self._heartbeat_task_categories():
            category_path = self._heartbeat_task_category_path(workspace, slug)
            lines.append(f"- {title}：./butler_main/butler_bot_agent/agents/local_memory/{HEARTBEAT_TASK_BOARD_DIR_NAME}/{category_path.name}  |  {desc}")
        lines.extend([
            "",
            f"## 变更日志\n\n- ./{(Path('butler_main') / 'butler_bot_agent' / 'agents' / 'local_memory' / HEARTBEAT_TASK_BOARD_DIR_NAME / HEARTBEAT_TASK_CHANGE_LOG_FILE).as_posix()}",
        ])
        return "\n".join(lines).strip() + "\n"

    def _read_heartbeat_task_board_sections(self, workspace: str) -> list[str]:
        self._ensure_heartbeat_task_board(workspace)
        sections: list[str] = []
        index_text = self._safe_read_heartbeat_task_board_text(workspace, self._heartbeat_tasks_md_path(workspace)).strip()
        if index_text:
            sections.append(index_text)
        for slug, _title, _desc in self._heartbeat_task_categories():
            path = self._heartbeat_task_category_path(workspace, slug)
            text = self._safe_read_heartbeat_task_board_text(workspace, path).strip()
            if text:
                sections.append(text)
        log_excerpt = self._render_heartbeat_task_log_excerpt(workspace, max_lines=12)
        if log_excerpt:
            sections.append("## 最近变更\n\n" + log_excerpt)
        workspace_context = self._render_heartbeat_task_workspace_context(workspace)
        if workspace_context:
            sections.append("## 生命周期任务工作区\n\n" + workspace_context)
        return sections

    def _render_heartbeat_task_log_excerpt(self, workspace: str, max_lines: int = 12) -> str:
        path = self._heartbeat_task_change_log_path(workspace)
        if not path.exists():
            return ""
        lines = []
        raw_lines = self._safe_read_heartbeat_task_board_text(workspace, path).splitlines()
        for raw in raw_lines[-max_lines:]:
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            action = str(payload.get("action") or "update").strip()
            title = str(payload.get("title") or payload.get("task_id") or "task").strip()
            category = str(payload.get("category") or "unknown").strip()
            source = str(payload.get("source") or "unknown").strip()
            timestamp = str(payload.get("timestamp") or "").strip()
            lines.append(f"- [{timestamp}] {action} | {category} | {source} | {title}")
        return "\n".join(lines)

    def _select_heartbeat_task_category(self, item: dict, long_term: bool) -> str:
        explicit = str(item.get("task_bucket") or item.get("task_category") or item.get("category") or "").strip().lower()
        alias_map = {
            "工作任务": "work",
            "主动想干": "initiative",
            "定时": "scheduled",
            "长期": "longterm",
            "整理清洁": "cleanup",
            "闲时无聊": "idle",
            "work": "work",
            "initiative": "initiative",
            "scheduled": "scheduled",
            "longterm": "longterm",
            "cleanup": "cleanup",
            "idle": "idle",
        }
        if explicit in alias_map:
            return alias_map[explicit]
        source = str(item.get("source") or item.get("trigger_hint") or "").strip().lower()
        title = str(item.get("title") or "").strip()
        detail = str(item.get("detail") or "").strip()
        text = f"{title} {detail}".lower()
        schedule_type = str(item.get("schedule_type") or "").strip().lower()
        schedule_value = str(item.get("schedule_value") or "").strip()
        kind = str(item.get("kind") or "").strip().lower()
        if long_term and (schedule_type or schedule_value or kind == "reminder"):
            return "scheduled"
        if any(keyword in text for keyword in ("整理", "归档", "清理", "治理", "巡检", "对齐", "修复", "校验")):
            return "cleanup"
        if long_term and any(keyword in text for keyword in ("每天", "每日", "每周", "定时", "提醒", "早上", "晚上")):
            return "scheduled"
        if long_term:
            return "longterm"
        if any(keyword in source for keyword in ("self", "mind", "autonomous", "heartbeat", "explore")):
            return "initiative"
        if any(keyword in text for keyword in ("闲时", "无聊", "灵感", "逛", "冲浪", "玩")):
            return "idle"
        return "work"

    def _render_heartbeat_task_board_line(self, item: dict, long_term: bool, category: str) -> str:
        task_id = str(item.get("task_id") or "").strip() or uuid.uuid4().hex[:12]
        status = str(item.get("status") or ("enabled" if long_term else "pending")).strip() or ("enabled" if long_term else "pending")
        source = str(item.get("source") or item.get("trigger_hint") or ("long_term" if long_term else "conversation")).strip() or ("long_term" if long_term else "conversation")
        title = str(item.get("title") or item.get("detail") or "未命名任务").strip()[:120]
        detail = str(item.get("detail") or title).strip()[:240]
        priority = str(item.get("priority") or ("scheduled" if long_term else "medium")).strip() or ("scheduled" if long_term else "medium")
        due_text = str(item.get("next_due_at") or item.get("due_at") or item.get("schedule_value") or "").strip()
        meta = [f"task_id={task_id}", f"status={status}", f"source={source}", f"priority={priority}", f"category={category}"]
        if due_text:
            meta.append(f"due={due_text}")
        return f"- [{']['.join(meta)}] {title}" + (f": {detail}" if detail and detail != title else "")

    def _upsert_heartbeat_task_board_item(self, workspace: str, item: dict, *, long_term: bool, action: str, source: str) -> None:
        if not isinstance(item, dict):
            return
        self._ensure_heartbeat_task_board(workspace)
        category = self._select_heartbeat_task_category(item, long_term=long_term)
        path = self._heartbeat_task_category_path(workspace, category)
        line = self._render_heartbeat_task_board_line(item, long_term=long_term, category=category)
        task_id = str(item.get("task_id") or "").strip()
        existing_lines = self._safe_read_heartbeat_task_board_text(workspace, path).splitlines() if path.exists() else []
        replaced = False
        new_lines: list[str] = []
        for raw in existing_lines:
            if task_id and f"task_id={task_id}" in raw:
                new_lines.append(line)
                replaced = True
            else:
                new_lines.append(raw)
        if not replaced:
            if new_lines and new_lines[-1].strip() == "- （当前为空，后续由对话 / 潜意识 / self_mind / heartbeat 自修正写入）":
                new_lines = new_lines[:-1]
            if new_lines and new_lines[-1].strip():
                new_lines.append("")
            new_lines.append(line)
        self._write_heartbeat_task_board_text(path, "\n".join(new_lines).rstrip() + "\n")
        self._append_heartbeat_task_change_log(
            workspace,
            {
                "action": action,
                "task_id": task_id,
                "title": str(item.get("title") or item.get("detail") or "").strip()[:160],
                "category": category,
                "source": source,
                "long_term": long_term,
            },
        )
        self._write_heartbeat_task_board_text(self._heartbeat_tasks_md_path(workspace), self._render_heartbeat_task_board_index(workspace))

    def _append_heartbeat_task_change_log(self, workspace: str, payload: dict) -> None:
        path = self._heartbeat_task_change_log_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **dict(payload or {}),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _rebuild_heartbeat_task_board_from_stores(self, workspace: str) -> None:
        self._ensure_heartbeat_task_board(workspace)
        board_dir = self._heartbeat_task_board_dir(workspace)
        for slug, _title, desc in self._heartbeat_task_categories():
            path = self._heartbeat_task_category_path(workspace, slug)
            header = self._safe_read_heartbeat_task_board_text(workspace, path).splitlines()[:3] if path.exists() else [f"# {slug}", "", f"用途：{desc}"]
            self._write_heartbeat_task_board_text(path, "\n".join(header).rstrip() + "\n\n- （当前为空，后续由对话 / 潜意识 / self_mind / heartbeat 自修正写入）\n")

        short_store = self._load_json_store(self._heartbeat_memory_path(workspace), self._default_heartbeat_memory)
        for item in (short_store.get("tasks") if isinstance(short_store.get("tasks"), list) else []):
            if isinstance(item, dict):
                self._upsert_heartbeat_task_board_item(
                    workspace,
                    item,
                    long_term=False,
                    action="rebuild",
                    source=str(item.get("source") or item.get("trigger_hint") or "heartbeat_memory").strip() or "heartbeat_memory",
                )

        long_store = self._load_json_store(self._heartbeat_long_tasks_path(workspace), self._default_heartbeat_long_tasks)
        for item in (long_store.get("tasks") if isinstance(long_store.get("tasks"), list) else []):
            if isinstance(item, dict):
                self._upsert_heartbeat_task_board_item(
                    workspace,
                    item,
                    long_term=True,
                    action="rebuild",
                    source=str(item.get("source") or item.get("kind") or "heartbeat_long_tasks").strip() or "heartbeat_long_tasks",
                )

    def _load_heartbeat_tasks_md(self, workspace: str) -> str:
        sections = self._read_heartbeat_task_board_sections(workspace)
        if sections:
            return "\n\n".join(section for section in sections if str(section).strip()).strip()
        path = self._heartbeat_tasks_md_path(workspace)
        if not path.exists():
            return ""
        return self._safe_read_heartbeat_task_board_text(workspace, path).strip()

    def _render_legacy_heartbeat_tasks_md(self, workspace: str) -> str:
        sections: list[str] = []

        short_items = self._load_pending_short_heartbeat_tasks(workspace)
        if short_items:
            lines = ["## 兼容短期任务"]
            for item in short_items[:8]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("detail") or "待办").strip()[:80]
                detail = str(item.get("detail") or title).strip()[:200]
                lines.append(f"- {title}" + (f": {detail}" if detail and detail != title else ""))
            sections.append("\n".join(lines))

        long_items = self._load_due_long_heartbeat_tasks(workspace)
        if long_items:
            lines = ["## 兼容到期长期任务"]
            for item in long_items[:8]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("detail") or "长期任务").strip()[:80]
                detail = str(item.get("detail") or title).strip()[:200]
                schedule_type = str(item.get("schedule_type") or "").strip()
                schedule_value = str(item.get("schedule_value") or "").strip()
                schedule = f" [{schedule_type} {schedule_value}]".strip() if schedule_type or schedule_value else ""
                lines.append(f"- {title}{schedule}" + (f": {detail}" if detail and detail != title else ""))
            sections.append("\n".join(lines))

        return "\n\n".join(section for section in sections if section.strip()).strip()

    def _append_to_heartbeat_tasks_md(self, workspace: str, text: str) -> None:
        if not text or not str(text).strip():
            return
        self._ensure_heartbeat_task_board(workspace)
        path = self._heartbeat_tasks_md_path(workspace)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        sep = "\n\n" if existing.rstrip() else ""
        path.write_text(existing.rstrip() + sep + str(text).strip() + "\n", encoding="utf-8")

    def _planner_state_path(self, workspace: str) -> Path:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return local_dir / HEARTBEAT_PLANNER_STATE_FILE

    def _load_planner_state(self, workspace: str) -> dict:
        path = self._planner_state_path(workspace)
        if not path.exists():
            return {"failure_count": 0, "backoff_until_epoch": 0.0}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"failure_count": 0, "backoff_until_epoch": 0.0}

    def _save_planner_state(self, workspace: str, failure_count: int, backoff_until_epoch: float) -> None:
        path = self._planner_state_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "failure_count": max(0, int(failure_count or 0)),
            "backoff_until_epoch": max(0.0, float(backoff_until_epoch or 0.0)),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._heartbeat_planner_failure_count = payload["failure_count"]
        self._heartbeat_planner_backoff_until = payload["backoff_until_epoch"]

    def _default_heartbeat_memory(self) -> dict:
        return {"version": 1, "updated_at": "", "tasks": [], "notes": []}

    def _default_heartbeat_long_tasks(self) -> dict:
        return {"version": 1, "updated_at": "", "tasks": []}

    def _load_json_store(self, path: Path, default_factory: Callable[[], dict]) -> dict:
        if not path.exists():
            return default_factory()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return default_factory()

    def _save_json_store(self, path: Path, payload: dict) -> None:
        payload = dict(payload or {})
        payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _normalize_heartbeat_upgrade_request(self, payload: dict | None) -> dict:
        data = dict(payload or {})
        action = str(data.get("action") or "execute_prompt").strip() or "execute_prompt"
        execute_prompt = str(data.get("execute_prompt") or "").strip()
        requires_restart = bool(data.get("requires_restart"))
        maintainer_agent_role = str(data.get("maintainer_agent_role") or "update-agent").strip() or "update-agent"
        target_paths = [str(item).strip() for item in (data.get("target_paths") or []) if str(item).strip()]
        if action == "execute_prompt" and not execute_prompt and requires_restart:
            action = "restart"
        if action == "restart":
            requires_restart = True
        return {
            "version": 1,
            "request_id": str(data.get("request_id") or uuid.uuid4()),
            "created_at": str(data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "status": str(data.get("status") or "pending").strip() or "pending",
            "source": str(data.get("source") or "heartbeat").strip() or "heartbeat",
            "action": action,
            "reason": str(data.get("reason") or "心跳提出升级申请").strip() or "心跳提出升级申请",
            "summary": str(data.get("summary") or data.get("reason") or "").strip(),
            "execute_prompt": execute_prompt,
            "maintainer_agent_role": maintainer_agent_role,
            "target_paths": target_paths,
            "requires_restart": requires_restart,
            "approved_at": str(data.get("approved_at") or "").strip(),
            "rejected_at": str(data.get("rejected_at") or "").strip(),
            "user_notified_at": str(data.get("user_notified_at") or "").strip(),
        }

    def _read_heartbeat_upgrade_request(self, workspace: str) -> dict:
        return self._load_json_store(self._heartbeat_upgrade_request_path(workspace), lambda: {})

    def _write_heartbeat_upgrade_request(self, workspace: str, payload: dict) -> dict:
        normalized = self._normalize_heartbeat_upgrade_request(payload)
        self._save_json_store(self._heartbeat_upgrade_request_path(workspace), normalized)
        try:
            self._file_guardian_upgrade_request(workspace, normalized)
        except Exception as e:
            print(f"[guardian-request] 升级申请备案失败: {e}", flush=True)
        return normalized

    def _clear_heartbeat_upgrade_request(self, workspace: str) -> None:
        try:
            self._heartbeat_upgrade_request_path(workspace).unlink(missing_ok=True)
        except Exception:
            pass

    def _clear_restart_markers(self, workspace: str) -> None:
        root = resolve_butler_root(workspace or os.getcwd())
        restart_json = root / RESTART_REQUEST_JSON_REL
        restart_flag = root / RUN_DIR_REL / RESTART_REQUESTED_FLAG_NAME
        for path in (restart_json, restart_flag):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

    def _load_restart_reason_from_markers(self, workspace: str) -> tuple[str, bool]:
        root = resolve_butler_root(workspace or os.getcwd())
        restart_json = root / RESTART_REQUEST_JSON_REL
        restart_flag = root / RUN_DIR_REL / RESTART_REQUESTED_FLAG_NAME
        exists = restart_json.exists() or restart_flag.exists()
        if not exists:
            return "", False
        restart_reason = ""
        if restart_json.exists():
            try:
                payload = json.loads(restart_json.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    restart_reason = str(payload.get("reason") or "").strip()
                elif isinstance(payload, str):
                    restart_reason = payload.strip()
            except Exception:
                restart_reason = ""
        if not restart_reason and restart_flag.exists():
            try:
                restart_reason = str(restart_flag.read_text(encoding="utf-8") or "").strip()
            except Exception:
                restart_reason = ""
        return restart_reason or "心跳判断需要重启主进程", True

    def _build_legacy_restart_upgrade_request(self, reason: str) -> dict:
        summary = str(reason or "心跳判断现有改动需要重启主进程后才能生效").strip()
        return self._normalize_heartbeat_upgrade_request(
            {
                "source": "heartbeat-restart-marker",
                "action": "restart",
                "reason": summary,
                "summary": summary,
                "maintainer_agent_role": "update-agent",
                "requires_restart": True,
            }
        )

    def _format_heartbeat_upgrade_request_message(self, request: dict) -> str:
        request_id = str(request.get("request_id") or "").strip()
        action = str(request.get("action") or "execute_prompt").strip() or "execute_prompt"
        reason = str(request.get("reason") or "").strip()
        summary = str(request.get("summary") or reason or "").strip()
        execute_prompt = str(request.get("execute_prompt") or "").strip()
        maintainer_agent_role = str(request.get("maintainer_agent_role") or "update-agent").strip() or "update-agent"
        target_paths = [str(item).strip() for item in (request.get("target_paths") or []) if str(item).strip()]
        lines = [
            "**心跳升级申请，等待用户批准**",
            "",
            f"申请ID：`{request_id}`",
            f"类型：{'重启主进程' if action == 'restart' else '执行升级方案'}",
            f"维护入口：`{maintainer_agent_role}`",
        ]
        if reason:
            lines.append(f"原因：{reason}")
        if summary:
            lines.append(f"摘要：{summary}")
        if target_paths:
            lines.append(f"目标路径：{', '.join(target_paths[:6])}")
        if execute_prompt:
            lines.extend(["", "计划说明：", execute_prompt[:1200]])
        lines.extend(
            [
                "",
                f"心跳线程没有执行身体目录 {BODY_ROOT_TEXT} 改动/重启的权限。",
                "请直接回复以下任一指令：",
                f"- `批准升级 {request_id}` / `同意按计划执行 {request_id}`",
                f"- `批准重启 {request_id}` / `可以重启 {request_id}`",
                f"- `拒绝升级 {request_id}` / `先别动 {request_id}`",
                f"- `查看升级申请 {request_id}`",
            ]
        )
        return "\n".join(lines).strip()

    def _send_heartbeat_upgrade_request_notification(self, cfg: dict, request: dict) -> bool:
        return self._send_private_message(
            cfg,
            self._format_heartbeat_upgrade_request_message(request),
            receive_id="",
            receive_id_type="open_id",
            fallback_to_startup_target=True,
            heartbeat_cfg=None,
        )

    def inspect_pending_upgrade_request_prompt(self, workspace: str, user_prompt: str) -> dict | None:
        request = self._read_heartbeat_upgrade_request(workspace)
        if not isinstance(request, dict) or str(request.get("status") or "") != "pending":
            return None

        text = str(user_prompt or "").strip()
        if not text:
            return None
        lowered = text.lower()
        request_id = str(request.get("request_id") or "").strip()
        mentions_request = (request_id and request_id.lower() in lowered) or any(
            hint in text for hint in ("升级", "重启", "按计划", "申请", "方案")
        ) or lowered in {"可以", "同意", "批准", "确认", "行", "好", "ok", "yes"}
        if not mentions_request:
            return None

        if any(hint in text for hint in ("查看升级申请", "看看申请", "什么计划", "查看方案", "看下方案")):
            return {"decision": "view", "request": request, "reply": self._format_heartbeat_upgrade_request_message(request)}

        if any(hint in text for hint in ("拒绝", "取消", "先别", "不要", "不重启", "不执行")):
            self._clear_heartbeat_upgrade_request(workspace)
            self._clear_restart_markers(workspace)
            return {
                "decision": "reject",
                "request": request,
                "reply": f"已取消心跳升级申请 `{request_id}`。聊天主进程不会执行本次改动或重启。",
            }

        if any(hint in text for hint in ("批准", "同意", "确认", "可以", "执行", "按计划", "重启吧", "可以重启", "批准重启")):
            approved = dict(request)
            approved["status"] = "approved"
            approved["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._write_heartbeat_upgrade_request(workspace, approved)

            action = str(approved.get("action") or "execute_prompt").strip() or "execute_prompt"
            if action == "restart":
                return {
                    "decision": "approve-restart",
                    "request": approved,
                    "reply": f"已收到你对心跳升级申请 `{request_id}` 的批准。聊天主进程将代为执行重启。",
                }

            execute_prompt = str(approved.get("execute_prompt") or "").strip()
            if execute_prompt:
                maintainer_agent_role = str(approved.get("maintainer_agent_role") or "update-agent").strip() or "update-agent"
                return {
                    "decision": "approve-execute",
                    "request": approved,
                    "execute_prompt": (
                        f"【用户已批准心跳升级申请 {request_id}】\n"
                        f"申请原因：{str(approved.get('reason') or '').strip()}\n"
                        f"统一维护入口：请优先按 {maintainer_agent_role} 的维护协议执行以下已批准方案。\n"
                        f"请在主对话进程中执行以下已批准方案：\n{execute_prompt}"
                    ).strip(),
                }
            return {"decision": "view", "request": approved, "reply": self._format_heartbeat_upgrade_request_message(approved)}

        return None

    def execute_approved_upgrade_request(self, workspace: str, request: dict) -> bool:
        action = str((request or {}).get("action") or "").strip() or "execute_prompt"
        if action != "restart":
            return False
        reason = str((request or {}).get("reason") or (request or {}).get("summary") or "心跳升级申请已获批准").strip()
        self._clear_restart_markers(workspace)
        self._clear_heartbeat_upgrade_request(workspace)
        handoff_request = dict(request or {})
        handoff_request["source"] = "butler"
        handoff_request["status"] = "pending"
        handoff_request["requires_restart"] = True
        handoff_request["reason"] = reason
        handoff_request["summary"] = str(handoff_request.get("summary") or "用户已批准重启申请，移交 guardian 执行").strip()
        self._file_guardian_upgrade_request(workspace, handoff_request)
        return True

    def _load_heartbeat_memory(self, workspace: str) -> dict:
        return self._load_json_store(self._heartbeat_memory_path(workspace), self._default_heartbeat_memory)

    def _save_heartbeat_memory(self, workspace: str, payload: dict) -> None:
        self._save_json_store(self._heartbeat_memory_path(workspace), payload)
        tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
        for item in tasks:
            if isinstance(item, dict):
                self._upsert_heartbeat_task_board_item(
                    workspace,
                    item,
                    long_term=False,
                    action="sync-store",
                    source=str(item.get("source") or item.get("trigger_hint") or "heartbeat_memory").strip() or "heartbeat_memory",
                )
        if tasks:
            self._rebuild_heartbeat_task_board_from_stores(workspace)
        if self._legacy_heartbeat_markdown_mirrors_enabled():
            self._heartbeat_memory_mirror_path(workspace).write_text(self._render_heartbeat_memory_markdown(payload), encoding="utf-8")

    def _load_heartbeat_long_tasks(self, workspace: str) -> dict:
        return self._load_json_store(self._heartbeat_long_tasks_path(workspace), self._default_heartbeat_long_tasks)

    def _save_heartbeat_long_tasks(self, workspace: str, payload: dict) -> None:
        self._save_json_store(self._heartbeat_long_tasks_path(workspace), payload)
        tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
        for item in tasks:
            if isinstance(item, dict):
                self._upsert_heartbeat_task_board_item(
                    workspace,
                    item,
                    long_term=True,
                    action="sync-store",
                    source=str(item.get("source") or item.get("kind") or "heartbeat_long_tasks").strip() or "heartbeat_long_tasks",
                )
        if tasks:
            self._rebuild_heartbeat_task_board_from_stores(workspace)
        if self._legacy_heartbeat_markdown_mirrors_enabled():
            self._heartbeat_long_tasks_mirror_path(workspace).write_text(self._render_heartbeat_long_tasks_markdown(payload), encoding="utf-8")

    def _govern_memory_write(self, target_path: str, action_type: str, summary: str) -> bool:
        cfg = self._config_provider() or {}
        features = cfg.get("features") if isinstance(cfg.get("features"), dict) else {}
        if not bool(features.get("governor", False)):
            return True
        decision = self._governor.evaluate(GovernedAction(action_type=action_type, target_path=target_path, summary=summary))
        if not decision.allowed:
            print(f"[governor] 拦截写入: action={action_type} | target={target_path} | rationale={decision.rationale}", flush=True)
        return bool(decision.allowed)

    def _legacy_heartbeat_markdown_mirrors_enabled(self) -> bool:
        cfg = self._config_provider() or {}
        features = cfg.get("features") if isinstance(cfg.get("features"), dict) else {}
        raw = features.get("legacy_heartbeat_markdown_mirrors", False)
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw)

    def _render_heartbeat_memory_markdown(self, payload: dict) -> str:
        lines = ["# heart_beat_memory", ""]
        for item in payload.get("tasks") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "未命名任务").strip()
            status = str(item.get("status") or "pending").strip()
            detail = str(item.get("detail") or "").strip()
            due_at = str(item.get("due_at") or "").strip()
            last_result = str(item.get("last_result") or "").strip()
            lines.append(f"## {title}")
            lines.append(f"- status: {status}")
            if due_at:
                lines.append(f"- due_at: {due_at}")
            if detail:
                lines.append(f"- detail: {detail}")
            if last_result:
                lines.append(f"- last_result: {last_result[:200]}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_heartbeat_long_tasks_markdown(self, payload: dict) -> str:
        lines = ["# heartbeat_long_tasks", ""]
        for item in payload.get("tasks") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "未命名长期任务").strip()
            enabled = bool(item.get("enabled", True))
            schedule_type = str(item.get("schedule_type") or "").strip()
            schedule_value = str(item.get("schedule_value") or "").strip()
            next_due_at = str(item.get("next_due_at") or "").strip()
            detail = str(item.get("detail") or "").strip()
            lines.append(f"## {title}")
            lines.append(f"- enabled: {enabled}")
            if schedule_type or schedule_value:
                lines.append(f"- schedule: {schedule_type} {schedule_value}".strip())
            if next_due_at:
                lines.append(f"- next_due_at: {next_due_at}")
            if detail:
                lines.append(f"- detail: {detail}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _normalize_time_hint(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        raw = raw.replace("：", ":").replace("点", ":00")
        m = re.search(r"(?P<h>\d{1,2})(?::(?P<m>\d{1,2}))?", raw)
        if not m:
            return ""
        hour = int(m.group("h"))
        minute = int(m.group("m") or 0)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return ""
        return f"{hour:02d}:{minute:02d}"

    def _compute_next_due_at(self, schedule_type: str, schedule_value: str) -> str:
        if schedule_type != "daily" or not schedule_value:
            return ""
        time_text = self._normalize_time_hint(schedule_value)
        if not time_text:
            return ""
        hour, minute = [int(x) for x in time_text.split(":", 1)]
        now = datetime.now()
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due = due + timedelta(days=1)
        return due.strftime("%Y-%m-%d %H:%M:%S")

    def _extract_heartbeat_candidates(self, user_prompt: str, assistant_reply: str) -> tuple[list[dict], list[dict]]:
        text = re.sub(r"\s+", " ", f"{user_prompt}\n{assistant_reply}").strip()
        if not text:
            return [], []
        short_tasks: list[dict] = []
        long_tasks: list[dict] = []
        low = text.lower()

        if any(h in text for h in HEARTBEAT_TASK_HINTS) or any(h in low for h in [x.lower() for x in HEARTBEAT_TASK_HINTS]):
            if any(a in text for a in HEARTBEAT_ACTION_HINTS) or any(a in low for a in [x.lower() for x in HEARTBEAT_ACTION_HINTS]):
                short_tasks.append({
                    "title": re.sub(r"\s+", " ", user_prompt).strip()[:40] or "后台任务",
                    "detail": text[:220],
                    "priority": "medium",
                    "trigger_hint": "conversation",
                })

        reminder_matches = re.findall(r"(?:以后)?每天\s*(\d{1,2}(?:[:：点]\d{0,2})?)\s*(?:提醒我|提醒|叫我)", text)
        for matched in reminder_matches:
            time_text = self._normalize_time_hint(matched)
            if not time_text:
                continue
            long_tasks.append({
                "kind": "reminder",
                "title": f"每天 {time_text} 提醒",
                "detail": text[:220],
                "schedule_type": "daily",
                "schedule_value": time_text,
                "timezone": "Asia/Shanghai",
                "enabled": True,
            })

        work_time = re.search(r"(\d{1,2}(?:[:：]\d{2})?)\s*[-到至]\s*(\d{1,2}(?:[:：]\d{2})?).{0,12}工作时间", text)
        if work_time:
            start_at = self._normalize_time_hint(work_time.group(1))
            end_at = self._normalize_time_hint(work_time.group(2))
            if start_at and end_at:
                long_tasks.append({
                    "kind": "work_window",
                    "title": f"工作时间 {start_at}-{end_at}",
                    "detail": text[:220],
                    "schedule_type": "daily",
                    "schedule_value": start_at,
                    "time_window": f"{start_at}-{end_at}",
                    "timezone": "Asia/Shanghai",
                    "enabled": True,
                })

        return short_tasks[:3], long_tasks[:3]

    def _normalize_heartbeat_tasks(self, model_tasks: list, user_prompt: str, fallback_tasks: list[dict], long_term: bool) -> list[dict]:
        out: list[dict] = []
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for raw in list(model_tasks or []) + list(fallback_tasks or []):
            if isinstance(raw, str):
                item = {"title": raw, "detail": raw}
            elif isinstance(raw, dict):
                item = dict(raw)
            else:
                continue
            title = str(item.get("title") or item.get("task") or item.get("detail") or "").strip()[:40]
            detail = str(item.get("detail") or item.get("summary") or user_prompt or title).strip()[:220]
            if not title:
                continue
            if long_term:
                schedule_type = str(item.get("schedule_type") or "daily").strip() or "daily"
                schedule_value = self._normalize_time_hint(str(item.get("schedule_value") or item.get("time") or ""))
                normalized = {
                    "task_id": str(item.get("task_id") or uuid.uuid4()),
                    "kind": str(item.get("kind") or "reminder").strip() or "reminder",
                    "schedule_type": schedule_type,
                    "schedule_value": schedule_value,
                    "time_window": str(item.get("time_window") or "").strip(),
                    "timezone": str(item.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai",
                    "enabled": bool(item.get("enabled", True)),
                    "title": title,
                    "detail": detail,
                    "created_at": str(item.get("created_at") or now_text),
                    "updated_at": now_text,
                    "last_run_at": str(item.get("last_run_at") or "").strip(),
                    "next_due_at": str(item.get("next_due_at") or self._compute_next_due_at(schedule_type, schedule_value)).strip(),
                    "last_result": str(item.get("last_result") or "").strip()[:200],
                }
            else:
                normalized = {
                    "task_id": str(item.get("task_id") or uuid.uuid4()),
                    "source": str(item.get("source") or "conversation").strip() or "conversation",
                    "source_memory_id": str(item.get("source_memory_id") or "").strip(),
                    "created_at": str(item.get("created_at") or now_text),
                    "updated_at": now_text,
                    "status": str(item.get("status") or "pending").strip() or "pending",
                    "priority": str(item.get("priority") or "medium").strip() or "medium",
                    "title": title,
                    "detail": detail,
                    "trigger_hint": str(item.get("trigger_hint") or "conversation").strip(),
                    "due_at": str(item.get("due_at") or "").strip(),
                    "tags": [str(x).strip()[:20] for x in (item.get("tags") or []) if str(x).strip()][:6],
                    "last_result": str(item.get("last_result") or "").strip()[:200],
                }
            out.append(normalized)
        return out[:5]

    def _task_identity_key(self, item: dict, long_term: bool) -> str:
        if long_term:
            return "|".join([
                str(item.get("kind") or "").strip(),
                str(item.get("title") or "").strip(),
                str(item.get("schedule_type") or "").strip(),
                str(item.get("schedule_value") or "").strip(),
                str(item.get("time_window") or "").strip(),
            ])
        return "|".join([
            str(item.get("title") or "").strip(),
            str(item.get("detail") or "").strip(),
            str(item.get("trigger_hint") or "").strip(),
        ])

    def _merge_heartbeat_tasks_from_entry(self, workspace: str, entry: dict) -> None:
        short_items = entry.get("heartbeat_tasks") if isinstance(entry.get("heartbeat_tasks"), list) else []
        long_items = entry.get("heartbeat_long_term_tasks") if isinstance(entry.get("heartbeat_long_term_tasks"), list) else []

        if short_items:
            short_store = self._load_heartbeat_memory(workspace)
            existing_short = short_store.get("tasks") if isinstance(short_store.get("tasks"), list) else []
            identity_map = {
                self._task_identity_key(item, long_term=False): item
                for item in existing_short
                if isinstance(item, dict)
            }
            for item in short_items:
                if not isinstance(item, dict):
                    continue
                identity = self._task_identity_key(item, long_term=False)
                if identity in identity_map:
                    identity_map[identity].update({
                        "updated_at": str(item.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        "detail": str(item.get("detail") or identity_map[identity].get("detail") or "").strip(),
                        "priority": str(item.get("priority") or identity_map[identity].get("priority") or "medium").strip() or "medium",
                    })
                else:
                    existing_short.append(item)
                    identity_map[identity] = item
            short_store["tasks"] = existing_short
            self._save_heartbeat_memory(workspace, short_store)

        if long_items:
            long_store = self._load_heartbeat_long_tasks(workspace)
            existing_long = long_store.get("tasks") if isinstance(long_store.get("tasks"), list) else []
            identity_map = {
                self._task_identity_key(item, long_term=True): item
                for item in existing_long
                if isinstance(item, dict)
            }
            for item in long_items:
                if not isinstance(item, dict):
                    continue
                identity = self._task_identity_key(item, long_term=True)
                if identity in identity_map:
                    identity_map[identity].update({
                        "updated_at": str(item.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        "detail": str(item.get("detail") or identity_map[identity].get("detail") or "").strip(),
                        "next_due_at": str(item.get("next_due_at") or identity_map[identity].get("next_due_at") or "").strip(),
                    })
                else:
                    existing_long.append(item)
                    identity_map[identity] = item
            long_store["tasks"] = existing_long
            self._save_heartbeat_long_tasks(workspace, long_store)

        if short_items or long_items:
            TaskLedgerService(workspace).ensure_bootstrapped(short_tasks=short_items, long_tasks=long_items)
        for item in short_items:
            if isinstance(item, dict):
                self._upsert_heartbeat_task_board_item(
                    workspace,
                    item,
                    long_term=False,
                    action="upsert",
                    source=str(item.get("source") or item.get("trigger_hint") or "conversation").strip() or "conversation",
                )
        for item in long_items:
            if isinstance(item, dict):
                self._upsert_heartbeat_task_board_item(
                    workspace,
                    item,
                    long_term=True,
                    action="upsert",
                    source=str(item.get("source") or item.get("kind") or "long_term").strip() or "long_term",
                )

    def handle_explicit_heartbeat_task_command(self, workspace: str, user_prompt: str) -> dict | None:
        command = self._parse_explicit_heartbeat_task_command(user_prompt)
        if not command:
            return None
        action = str(command.get("action") or "").strip()
        target = str(command.get("target") or "").strip()
        if action == "add":
            return self._handle_explicit_heartbeat_task_add(workspace, user_prompt, target)
        if action in {"cancel", "complete"}:
            return self._handle_explicit_heartbeat_task_update(workspace, action=action, target=target)
        return None

    def _parse_explicit_heartbeat_task_command(self, user_prompt: str) -> dict | None:
        text = str(user_prompt or "").strip()
        if not text:
            return None
        patterns = [
            (
                "cancel",
                [
                    re.compile(r"^\s*(?:请)?(?:取消|删除|删掉|移除)(?:这个)?(?:心跳|heartbeat|后台)?(?:任务|提醒)?[：:,\s]*(?P<target>[\s\S]*)$", re.IGNORECASE),
                    re.compile(r"^\s*(?:请)?把(?P<target>[\s\S]+?)(?:从)?(?:心跳|heartbeat|后台)(?:任务|提醒)?(?:里)?(?:取消|删除|删掉|移除)\s*$", re.IGNORECASE),
                ],
            ),
            (
                "complete",
                [
                    re.compile(r"^\s*(?:请)?(?:完成|标记完成|标记为完成|结束)(?:这个)?(?:心跳|heartbeat|后台)?(?:任务)?[：:,\s]*(?P<target>[\s\S]*)$", re.IGNORECASE),
                    re.compile(r"^\s*(?:请)?把(?P<target>[\s\S]+?)(?:这个)?(?:心跳|heartbeat|后台)?(?:任务)?(?:标记为)?(?:已)?完成\s*$", re.IGNORECASE),
                ],
            ),
            (
                "add",
                [
                    re.compile(r"^\s*(?:请)?(?:放进|放入|加入|加到|排进|排到|交给)(?:心跳|heartbeat|后台)(?:任务)?[：:,\s]*(?P<target>[\s\S]+)$", re.IGNORECASE),
                    re.compile(r"^\s*(?:请)?(?:把|将)?(?P<target>[\s\S]+?)(?:放进|放入|加入|加到|排进|排到|交给)(?:心跳|heartbeat|后台)(?:任务)?(?:里)?\s*$", re.IGNORECASE),
                    re.compile(r"^\s*(?:心跳|heartbeat)(?:任务)?[：:]\s*(?P<target>[\s\S]+)$", re.IGNORECASE),
                ],
            ),
        ]
        for action, pattern_list in patterns:
            for pattern in pattern_list:
                match = pattern.match(text)
                if not match:
                    continue
                target = self._clean_explicit_heartbeat_task_target(str(match.group("target") or ""))
                return {"action": action, "target": target}
        return None

    def _clean_explicit_heartbeat_task_target(self, text: str) -> str:
        cleaned = str(text or "").strip()
        cleaned = re.sub(r"^(?:任务|提醒|事项)[：:\s]*", "", cleaned)
        return cleaned.strip(" \t\r\n，,。.;；")

    def _handle_explicit_heartbeat_task_add(self, workspace: str, original_text: str, target: str) -> dict:
        clean_target = self._clean_explicit_heartbeat_task_target(target)
        if not clean_target:
            return {
                "handled": True,
                "reply": (
                    "已识别为心跳任务放入指令，但缺少任务内容。\n\n"
                    "可直接这样说：\n"
                    "- 放进心跳：整理周报\n"
                    "- 放进心跳：每天 9 点提醒我写日报"
                ),
            }

        heuristic_short, heuristic_long = self._extract_heartbeat_candidates(clean_target, "")
        if heuristic_long:
            seed_item = {
                "title": clean_target[:40],
                "detail": clean_target[:220],
                "source": "explicit_talk",
                "kind": "reminder",
                "enabled": True,
            }
            long_items = self._normalize_heartbeat_tasks([], clean_target, [seed_item] + heuristic_long, long_term=True)
            short_items: list[dict] = []
            task = dict(long_items[0]) if long_items else {}
            long_term = True
        else:
            seed_item = {
                "title": clean_target[:40],
                "detail": clean_target[:220],
                "source": "explicit_talk",
                "trigger_hint": "explicit_talk_command",
                "priority": "medium",
            }
            short_items = self._normalize_heartbeat_tasks([], clean_target, [seed_item] + heuristic_short, long_term=False)
            long_items = []
            task = dict(short_items[0]) if short_items else {}
            long_term = False

        if not task:
            return {
                "handled": True,
                "reply": "已识别为心跳任务放入指令，但没能解析出有效任务内容。请换一种更明确的描述再发一次。",
            }

        self._merge_heartbeat_tasks_from_entry(
            workspace,
            {
                "heartbeat_tasks": short_items,
                "heartbeat_long_term_tasks": long_items,
            },
        )
        return {
            "handled": True,
            "reply": self._format_explicit_heartbeat_task_receipt(
                action="add",
                item=task,
                long_term=long_term,
                status_text="enabled" if long_term else "pending",
            ),
        }

    def _handle_explicit_heartbeat_task_update(self, workspace: str, *, action: str, target: str) -> dict:
        clean_target = self._clean_explicit_heartbeat_task_target(target)
        matches = self._find_explicit_heartbeat_task_matches(workspace, clean_target)
        if matches.get("error") == "missing-target":
            verb = "取消" if action == "cancel" else "完成"
            return {
                "handled": True,
                "reply": (
                    f"已识别为心跳任务{verb}指令，但缺少任务目标。\n\n"
                    "可直接这样说：\n"
                    f"- {verb}心跳任务 task_id=short-xxx\n"
                    f"- {verb}心跳任务：整理周报"
                ),
            }
        if matches.get("error") == "not-found":
            return {
                "handled": True,
                "reply": (
                    f"没有在当前 heartbeat 任务里找到目标：`{clean_target}`。\n\n"
                    "建议直接带 `task_id=` 重试，例如：\n"
                    f"- {'取消' if action == 'cancel' else '完成'}心跳任务 task_id=short-xxx"
                ),
            }
        if matches.get("error") == "ambiguous":
            lines = [f"找到多条可能匹配的 heartbeat 任务，请改用 `task_id=` 指定：", ""]
            for item in matches.get("candidates") or []:
                lines.append(
                    f"- `{str(item.get('task_id') or '').strip()}` | {str(item.get('title') or '').strip()} | {str(item.get('status') or '').strip() or 'pending'}"
                )
            return {"handled": True, "reply": "\n".join(lines)}

        item = dict(matches.get("item") or {})
        if not item:
            return {"handled": True, "reply": "任务状态更新失败：没有定位到目标任务。"}

        task_id = str(item.get("task_id") or "").strip()
        long_term = str(item.get("task_type") or "short").strip().lower() == "long"
        old_status = str(item.get("status") or "").strip() or ("enabled" if long_term else "pending")
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result_text = (
            "用户在对话中显式取消该任务。"
            if action == "cancel"
            else "用户在对话中显式标记该任务已完成。"
        )

        ledger_service = TaskLedgerService(workspace)
        ledger_payload = ledger_service.load()
        ledger_item: dict | None = None
        for raw in ledger_payload.get("items") or []:
            if not isinstance(raw, dict):
                continue
            if str(raw.get("task_id") or "").strip() != task_id:
                continue
            ledger_item = raw
            break
        if ledger_item is None:
            return {"handled": True, "reply": "任务状态更新失败：task_ledger 中没有找到对应任务。"}

        if action == "cancel":
            ledger_item["status"] = "disabled" if long_term else "closed"
            if long_term:
                ledger_item["enabled"] = False
        else:
            ledger_item["status"] = "done"
            ledger_item["completed_at"] = now_text
            if long_term:
                ledger_item["enabled"] = False
        ledger_item["updated_at"] = now_text
        ledger_item["last_result"] = result_text[:400]
        ledger_item["acceptance_summary"] = result_text[:400]
        ledger_service.save(ledger_payload)

        store_payload = self._load_heartbeat_long_tasks(workspace) if long_term else self._load_heartbeat_memory(workspace)
        store_tasks = store_payload.get("tasks") if isinstance(store_payload.get("tasks"), list) else []
        store_item: dict | None = None
        for raw in store_tasks:
            if not isinstance(raw, dict):
                continue
            if str(raw.get("task_id") or "").strip() != task_id:
                continue
            store_item = raw
            break
        if store_item is None:
            store_item = dict(item)
            store_tasks.append(store_item)

        if action == "cancel":
            store_item["status"] = "disabled" if long_term else "cancelled"
            if long_term:
                store_item["enabled"] = False
        else:
            store_item["status"] = "done"
            if long_term:
                store_item["enabled"] = False
        store_item["updated_at"] = now_text
        store_item["last_result"] = result_text[:200]
        if not long_term:
            store_item["priority"] = str(store_item.get("priority") or "medium").strip() or "medium"

        if long_term:
            self._save_json_store(self._heartbeat_long_tasks_path(workspace), store_payload)
            if self._legacy_heartbeat_markdown_mirrors_enabled():
                self._heartbeat_long_tasks_mirror_path(workspace).write_text(self._render_heartbeat_long_tasks_markdown(store_payload), encoding="utf-8")
        else:
            self._save_json_store(self._heartbeat_memory_path(workspace), store_payload)
            if self._legacy_heartbeat_markdown_mirrors_enabled():
                self._heartbeat_memory_mirror_path(workspace).write_text(self._render_heartbeat_memory_markdown(store_payload), encoding="utf-8")

        self._upsert_heartbeat_task_board_item(
            workspace,
            store_item,
            long_term=long_term,
            action=f"explicit-{action}",
            source="explicit_talk",
        )
        return {
            "handled": True,
            "reply": self._format_explicit_heartbeat_task_receipt(
                action=action,
                item=store_item,
                long_term=long_term,
                status_text=str(store_item.get("status") or "").strip() or ("enabled" if long_term else "pending"),
                old_status=old_status,
            ),
        }

    def _find_explicit_heartbeat_task_matches(self, workspace: str, target: str) -> dict:
        clean_target = self._clean_explicit_heartbeat_task_target(target)
        explicit_task_id = self._extract_explicit_task_id(clean_target)
        normalized_target = self._normalize_task_match_text(clean_target)
        if not explicit_task_id and not normalized_target:
            return {"error": "missing-target"}

        items = [
            item for item in (TaskLedgerService(workspace).load().get("items") or [])
            if isinstance(item, dict)
        ]
        scored: list[dict] = []
        for item in items:
            task_id = str(item.get("task_id") or "").strip()
            title = str(item.get("title") or "").strip()
            detail = str(item.get("detail") or "").strip()
            status = str(item.get("status") or "").strip().lower()
            if explicit_task_id and task_id == explicit_task_id:
                return {"item": item}
            if status in {"closed", "disabled"} and not explicit_task_id:
                # 显式用 task_id 时仍允许精确命中，模糊匹配时优先活跃任务。
                continue
            title_norm = self._normalize_task_match_text(title)
            detail_norm = self._normalize_task_match_text(detail)
            if not normalized_target:
                continue
            score = 0
            if normalized_target == title_norm:
                score = 1000
            elif normalized_target and normalized_target in title_norm:
                score = 900 + min(len(normalized_target), 80)
            elif normalized_target and normalized_target in detail_norm:
                score = 780 + min(len(normalized_target), 60)
            elif title_norm and title_norm in normalized_target and len(title_norm) >= 4:
                score = 700 + min(len(title_norm), 40)
            elif detail_norm and detail_norm in normalized_target and len(detail_norm) >= 6:
                score = 640 + min(len(detail_norm), 30)
            if score > 0:
                scored.append({"score": score, "item": item})

        if not scored:
            return {"error": "not-found"}
        scored.sort(key=lambda row: (-int(row.get("score") or 0), str((row.get("item") or {}).get("updated_at") or "")), reverse=False)
        best = scored[0]
        second = scored[1] if len(scored) > 1 else None
        if len(scored) > 1:
            top_score = int(best.get("score") or 0)
            second_score = int(second.get("score") or 0) if second else 0
            if second and (top_score < 980 and second_score >= top_score - 40):
                return {"error": "ambiguous", "candidates": [row.get("item") for row in scored[:5]]}
        return {"item": best.get("item")}

    def _extract_explicit_task_id(self, text: str) -> str:
        matched = re.search(r"task[_\s-]*id\s*[=:：]\s*([A-Za-z0-9._:-]+)", str(text or ""), flags=re.IGNORECASE)
        return str(matched.group(1) or "").strip() if matched else ""

    def _normalize_task_match_text(self, text: str) -> str:
        raw = str(text or "").strip().lower()
        return re.sub(r"[\s`'\"“”‘’【】\[\]()（）<>{}:：,，。.;；!！?？/\\|+-]+", "", raw)

    def _format_explicit_heartbeat_task_receipt(
        self,
        *,
        action: str,
        item: dict,
        long_term: bool,
        status_text: str,
        old_status: str = "",
    ) -> str:
        title = str(item.get("title") or item.get("detail") or "未命名任务").strip()
        task_id = str(item.get("task_id") or "").strip()
        category = self._select_heartbeat_task_category(item, long_term=long_term)
        kind_text = "长期任务" if long_term else "短期任务"
        due_text = str(item.get("next_due_at") or item.get("schedule_value") or item.get("due_at") or "").strip()
        heading_map = {
            "add": "已放入心跳任务。",
            "cancel": "已取消心跳任务。",
            "complete": "已标记心跳任务完成。",
        }
        lines = [heading_map.get(action, "已处理心跳任务。"), ""]
        lines.append(f"- task_id: `{task_id}`")
        lines.append(f"- 标题: {title}")
        lines.append(f"- 类型: {kind_text}")
        lines.append(f"- 分类: {category}")
        if old_status:
            lines.append(f"- 状态: {old_status} -> {status_text}")
        else:
            lines.append(f"- 状态: {status_text}")
        if due_text:
            lines.append(f"- 时间/到期: {due_text}")
        lines.append("")
        lines.append("已同步到 heartbeat 看板和 task_ledger。")
        return "\n".join(lines)

    def _render_heartbeat_recent_snippet(self, workspace: str) -> str:
        recent_entries = self.get_recent_entries(workspace, limit=5, pool=BEAT_RECENT_POOL)
        return self._render_recent_context(recent_entries, max_chars=2000)

    def _render_unified_heartbeat_recent_context(self, workspace: str) -> str:
        talk_entries = self.get_recent_entries(workspace, limit=self._recent_max_items(TALK_RECENT_POOL), pool=TALK_RECENT_POOL)
        beat_entries = self.get_recent_entries(workspace, limit=self._recent_max_items(BEAT_RECENT_POOL), pool=BEAT_RECENT_POOL)
        sections: list[str] = []
        talk_text = self._render_recent_context(talk_entries, max_chars=2200)
        if talk_text:
            sections.append("## 对话侧统一近期流\n\n" + talk_text)
        beat_text = self._render_recent_context(beat_entries, max_chars=1400)
        if beat_text:
            sections.append("## 心跳侧最近执行流\n\n" + beat_text)
        return "\n\n".join(sections).strip()[:3600]

    def _render_heartbeat_task_workspace_context(self, workspace: str) -> str:
        return TaskLedgerService(workspace).render_task_workspaces_context(limit=6, recent_note_limit=3)

    def _render_heartbeat_local_memory_query_hits(self, workspace: str, query_text: str, max_chars: int = 2400) -> str:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        profile_text = self._load_current_user_profile_excerpt(workspace, max_chars=600)
        blocks: list[str] = []
        if profile_text:
            blocks.append(
                "- 当前用户画像\n"
                "  说明: 当前交互对象的个性化偏好、协作风格与关系约定不再写死在 core soul/role；如需个性化，请优先参考该画像。\n"
                f"  摘录: {profile_text.replace(chr(10), ' ')[:360]}"
            )
        rendered_hits = self._local_index_service(local_dir).render_prompt_hits(
            query_text,
            limit=5,
            include_details=True,
            max_chars=max(400, max_chars - 420),
        )
        if rendered_hits:
            blocks.append(rendered_hits)
        return "\n\n".join(block for block in blocks if block.strip()).strip()[:max_chars]

    def _render_heartbeat_local_memory_snippet(self, workspace: str) -> str:
        return self._render_heartbeat_local_memory_query_hits(workspace, "长期记忆 当前用户画像 默认约定 心跳治理")

    def _render_available_skills_prompt(self, workspace: str) -> str:
        base = render_skill_catalog_for_prompt(workspace, max_chars=1500)
        extras = []
        if "少做碎片化微操" not in base:
            extras.append("少做碎片化微操：优先沉淀可复用能力、阶段性结论和稳定工作流，不要把心跳浪费在无止境的小修小补上。")
        if "升级不要只停在死知识" not in base:
            extras.append("升级不要只停在死知识：如果识别到值得长期保留的能力，应尽量把它推进成可执行的 role/prompt/config/skill，而不是只留下一条说明。")
        return (base + ("\n" + "\n".join(extras) if extras else "")).strip()

    def _render_available_subagents_prompt(self, workspace: str) -> str:
        return render_subagent_catalog_for_prompt(workspace, max_chars=1400)

    def _render_available_teams_prompt(self, workspace: str) -> str:
        return render_team_catalog_for_prompt(workspace, max_chars=1400)

    def _render_public_agent_library_prompt(self, workspace: str) -> str:
        return render_public_capability_catalog_for_prompt(workspace, max_chars=1000)

    def _build_heartbeat_planning_prompt(self, cfg: dict, heartbeat_cfg: dict, workspace: str) -> str:
        return self._heartbeat_orchestrator.build_planning_prompt(cfg, heartbeat_cfg, workspace)

    def _default_heartbeat_plan(self, workspace: str) -> dict:
        return self._heartbeat_orchestrator.default_plan(workspace)

    def _planner_fallback_status_plan(self) -> dict:
        return self._heartbeat_orchestrator.planner_fallback_status_plan()

    def _plan_heartbeat_action(self, cfg: dict, heartbeat_cfg: dict, workspace: str, timeout: int, model: str, planner_timeout: int | None = None) -> dict:
        planner_runtime_request = {
            "cli": self._heartbeat_planner_cli(heartbeat_cfg),
            "model": str(model or "auto").strip() or "auto",
            "source": "heartbeat_planner",
        }
        with self.runtime_request_scope(planner_runtime_request):
            return self._heartbeat_orchestrator.plan_action(cfg, heartbeat_cfg, workspace, timeout, model, planner_timeout)

    def _apply_heartbeat_plan(self, workspace: str, plan: dict, execution_result: str, branch_results: list[dict] | None = None) -> None:
        self._heartbeat_orchestrator.apply_plan(workspace, plan, execution_result, branch_results=branch_results)

    def _long_maintenance_status_path(self, workspace: str) -> Path:
        recent_dir, _, _ = self._ensure_memory_dirs(workspace)
        return recent_dir / LONG_MAINTENANCE_STATUS_FILE

    def _read_startup_status(self, workspace: str) -> dict:
        p = self._startup_status_path(workspace)
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_startup_status(self, workspace: str, updates: dict) -> None:
        cur = self._read_startup_status(workspace)
        cur.update(updates or {})
        cur["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._startup_status_path(workspace).write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_long_maintenance_status(self, workspace: str) -> dict:
        p = self._long_maintenance_status_path(workspace)
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_long_maintenance_status(self, workspace: str, updates: dict) -> None:
        cur = self._read_long_maintenance_status(workspace)
        cur.update(updates or {})
        cur["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._long_maintenance_status_path(workspace).write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")

    def _should_skip_long_maintenance(self, workspace: str) -> tuple[bool, dict]:
        status = self._read_long_maintenance_status(workspace)
        last_completed_at = str(status.get("last_completed_at") or "").strip()
        if not last_completed_at:
            return False, status
        try:
            completed_at = datetime.strptime(last_completed_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return False, status
        elapsed = (datetime.now() - completed_at).total_seconds()
        min_interval = self._long_maintenance_min_interval_seconds()
        if elapsed >= min_interval:
            return False, status
        enriched = dict(status)
        enriched["remaining_seconds"] = int(min_interval - elapsed)
        return True, enriched

    def _local_memory_files(self, local_dir: Path, include_details: bool = False) -> list[Path]:
        self._ensure_local_memory_layout(local_dir)
        root_files = [p for p in local_dir.glob("*.md") if p.name != LOCAL_README_FILE]
        _, l1_dir, l2_dir = self._local_layer_paths(local_dir)
        layered_files = list(l1_dir.glob("*.md"))
        detail_files = list(l2_dir.glob("*.md")) if include_details else []
        return sorted(root_files + layered_files + detail_files, key=lambda p: p.stat().st_mtime, reverse=True)

    def _local_memory_managed_l1_files(self, local_dir: Path) -> list[Path]:
        self._ensure_local_memory_layout(local_dir)
        _, l1_dir, _ = self._local_layer_paths(local_dir)
        return sorted(l1_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    def _file_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _append_overflow(self, local_dir: Path, source_name: str, content: str) -> None:
        overflow = local_dir / LOCAL_OVERFLOW_FILE
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        block = f"\n\n## {ts} 来自 {source_name}\n{(content or '').strip()[:2000]}\n"
        old = self._file_text(overflow)
        if old:
            overflow.write_text(old.rstrip() + block + "\n", encoding="utf-8")
        else:
            overflow.write_text(f"# 未分类_临时存放\n\n{block}\n", encoding="utf-8")

    def _enforce_local_memory_file_count(self, local_dir: Path) -> None:
        files = self._local_memory_managed_l1_files(local_dir)
        max_files = self._local_l1_max_files()
        if len(files) <= max_files:
            return
        for p in files[max_files:]:
            content = self._file_text(p)
            if content.strip():
                self._append_overflow(local_dir, p.name, content)
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

    def _tokenize(self, text: str) -> set[str]:
        return {m.group(0).lower() for m in re.finditer(r"[A-Za-z0-9_\u4e00-\u9fff]{2,}", text or "")}

    def _find_similar_local_memory(self, local_dir: Path, title: str, summary: str) -> Path | None:
        cand_tokens = self._tokenize(f"{title} {summary}")
        if not cand_tokens:
            return None
        best_score = 0.0
        best_path = None
        for p in self._local_memory_files(local_dir):
            try:
                content = p.read_text(encoding="utf-8")
            except Exception:
                continue
            text = f"{p.stem}\n{content[:1200]}"
            tokens = self._tokenize(text)
            if not tokens:
                continue
            score = len(cand_tokens & tokens) / max(1, len(cand_tokens))
            if score > best_score:
                best_score = score
                best_path = p
        return best_path if best_score >= 0.4 else None

    def _safe_filename(self, name: str) -> str:
        n = (name or "对话沉淀").strip()
        n = re.sub(r"[\\/:*?\"<>|]", "_", n)
        n = re.sub(r"\s+", "", n)
        return (n[:40] or "对话沉淀") + ".md"

    def _choose_local_memory_category(self, title: str, summary: str, keywords: list[str]) -> str:
        text = f"{title} {summary} {' '.join(keywords or [])}".lower()
        rules = [
            ("preferences", ["偏好", "默认", "prefer", "default"]),
            ("rules", ["规则", "约束", "必须", "rule", "constraint"]),
            ("projects", ["项目", "project", "开发", "改造"]),
            ("research", ["研究", "文献", "论文", "literature"]),
            ("operations", ["飞书", "心跳", "守护", "部署", "服务", "运行"]),
            ("relationships", ["人事", "关系", "社交", "family"]),
            ("references", ["路径", "目录", "索引", "链接", "reference"]),
            ("reflections", ["反思", "经验", "教训", "总结", "lesson"]),
            ("identity", ["人格", "自我认知", "身份", "identity"]),
        ]
        for category, hints in rules:
            if any(hint in text for hint in hints):
                return category
        return "misc"

    def _render_local_memory_update_block(self, profile: dict, stamp: str, detail_path: Path | None = None) -> str:
        current = str(profile.get("current_conclusion") or "").strip() or "(空)"
        history = [str(x).strip() for x in (profile.get("history_evolution") or []) if str(x).strip()]
        scenarios = [str(x).strip() for x in (profile.get("applicable_scenarios") or []) if str(x).strip()]
        keywords = [str(x).strip() for x in (profile.get("keywords") or []) if str(x).strip()]
        lines = [
            f"## 更新于 {stamp}",
            "",
            "### 当前结论",
            f"- {current}",
            "",
            "### 历史演化",
        ]
        lines.extend([f"- {item}" for item in (history or [f"{stamp}：形成当前结论"])])
        lines.extend(["", "### 适用情景"])
        lines.extend([f"- {item}" for item in (scenarios or ["待补充"])])
        if keywords:
            lines.extend(["", "### 关键词"])
            lines.extend([f"- {item}" for item in keywords])
        if detail_path:
            lines.extend(["", "### 详情入口", f"- {detail_path.name}"])
        return "\n".join(lines).strip() + "\n"

    def _build_local_memory_profile(
        self,
        title: str,
        summary: str,
        keywords: list[str],
        source_type: str = "",
        source_reason: str = "",
        source_topic: str = "",
        source_entry: dict | None = None,
    ) -> dict:
        return self._subconscious_service.build_long_term_memory_profile(
            title=title,
            summary=summary,
            keywords=keywords,
            source_type=source_type,
            source_reason=source_reason,
            source_topic=source_topic,
            source_entry=source_entry,
        )

    def _upsert_local_memory_index(
        self,
        local_dir: Path,
        title: str,
        summary: str,
        keywords: list[str],
        summary_path: Path,
        detail_path: Path | None = None,
        profile: dict | None = None,
        source_type: str = "",
        source_reason: str = "",
        source_topic: str = "",
    ) -> None:
        payload = self._load_local_memory_index(local_dir)
        entries = [item for item in payload.get("entries") or [] if isinstance(item, dict)]
        summary_rel = self._relative_local_memory_path(local_dir, summary_path)
        detail_rel = self._relative_local_memory_path(local_dir, detail_path) if detail_path else ""
        category = self._choose_local_memory_category(title, summary, keywords)
        entry_id = summary_path.stem
        structured = profile if isinstance(profile, dict) else self._build_local_memory_profile(title, summary, keywords)
        updated_entry = {
            "entry_id": entry_id,
            "title": str(title or summary_path.stem).strip()[:80],
            "category": category,
            "keywords": [str(x).strip() for x in keywords if str(x).strip()][:8],
            "summary": str(summary or "").strip()[:220],
            "current_conclusion": str(structured.get("current_conclusion") or summary or "").strip()[:220],
            "history_evolution": [str(x).strip()[:220] for x in (structured.get("history_evolution") or []) if str(x).strip()][:4],
            "applicable_scenarios": [str(x).strip()[:80] for x in (structured.get("applicable_scenarios") or []) if str(x).strip()][:6],
            "current_effective": str(structured.get("current_effective") or structured.get("current_conclusion") or summary or "").strip()[:220],
            "layer": "L1",
            "summary_path": summary_rel,
            "detail_path": detail_rel,
            "source_type": str(source_type or "").strip()[:40],
            "source_reason": str(source_reason or "").strip()[:60],
            "source_topic": str(source_topic or "").strip()[:80],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        replaced = False
        for index, item in enumerate(entries):
            current_id = str(item.get("entry_id") or "").strip()
            current_summary = str(item.get("summary_path") or "").strip()
            if current_id == entry_id or current_summary == summary_rel:
                entries[index] = updated_entry
                replaced = True
                break
        if not replaced:
            entries.append(updated_entry)
        payload["entries"] = entries[-500:]
        self._save_local_memory_index(local_dir, payload)
        self._upsert_local_memory_relation(local_dir, title or summary_path.stem, category, summary_path, detail_path=detail_path)

    def _upsert_local_memory_relation(
        self,
        local_dir: Path,
        title: str,
        category: str,
        summary_path: Path,
        detail_path: Path | None = None,
    ) -> None:
        payload = self._load_local_memory_relations(local_dir)
        relations = [item for item in payload.get("relations") or [] if isinstance(item, dict)]
        summary_rel = self._relative_local_memory_path(local_dir, summary_path)
        detail_rel = self._relative_local_memory_path(local_dir, detail_path) if detail_path else ""
        relation = {
            "source_path": summary_rel,
            "target_path": detail_rel,
            "relation_type": "summary_to_detail" if detail_rel else "summary_only",
            "title": str(title or summary_path.stem).strip()[:80],
            "category": str(category or "misc").strip() or "misc",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        replaced = False
        for index, item in enumerate(relations):
            if str(item.get("source_path") or "").strip() == summary_rel:
                relations[index] = relation
                replaced = True
                break
        if not replaced:
            relations.append(relation)
        payload["relations"] = relations[-1000:]
        self._save_local_memory_relations(local_dir, payload)

    def _mark_recent_entry_local_promoted(self, entry: dict, action: str, source: str) -> None:
        if not isinstance(entry, dict):
            return
        lt = entry.get("long_term_candidate") if isinstance(entry.get("long_term_candidate"), dict) else {}
        if not lt:
            return
        lt["promoted_to_local_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lt["promoted_action"] = str(action or "").strip()[:40]
        lt["promoted_source"] = str(source or "").strip()[:40]
        entry["long_term_candidate"] = lt

    def _promote_recent_long_term_candidates(
        self,
        entries: list[dict],
        workspace: str,
        reason: str,
        max_promotions: int = 2,
    ) -> int:
        promoted = 0
        if max_promotions <= 0:
            return promoted
        for entry in reversed(entries or []):
            if promoted >= max_promotions:
                break
            if not isinstance(entry, dict):
                continue
            lt = entry.get("long_term_candidate") if isinstance(entry.get("long_term_candidate"), dict) else {}
            if not lt:
                continue
            if not bool(lt.get("should_write")):
                continue
            if str(lt.get("promoted_to_local_at") or "").strip():
                continue
            summary = str(lt.get("summary") or "").strip()
            if not summary:
                continue
            action = self._upsert_local_memory(
                workspace,
                str(lt.get("title") or "对话沉淀"),
                summary,
                [str(x) for x in (lt.get("keywords") or [])],
                source_type="recent-sweep",
                source_memory_id=str(entry.get("memory_id") or ""),
                source_reason=str(reason or "recent-sweep"),
                source_topic=str(entry.get("topic") or ""),
                source_entry=entry,
            )
            if action in {"write-new", "append-existing", "append-similar", "duplicate-skip"}:
                self._mark_recent_entry_local_promoted(entry, action, source="recent-sweep")
                promoted += 1
        return promoted

    def _append_local_memory_write_journal(
        self,
        local_dir: Path,
        *,
        action: str,
        title: str,
        summary: str,
        keywords: list[str],
        summary_path: Path | None = None,
        detail_path: Path | None = None,
        source_type: str = "",
        source_memory_id: str = "",
        source_reason: str = "",
        source_topic: str = "",
    ) -> None:
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": str(action or "").strip(),
            "title": str(title or "").strip()[:80],
            "summary_preview": str(summary or "").strip()[:160],
            "keywords": [str(x).strip()[:20] for x in (keywords or []) if str(x).strip()][:8],
            "summary_path": self._relative_local_memory_path(local_dir, summary_path) if summary_path else "",
            "detail_path": self._relative_local_memory_path(local_dir, detail_path) if detail_path else "",
            "source_type": str(source_type or "").strip()[:40],
            "source_memory_id": str(source_memory_id or "").strip()[:80],
            "source_reason": str(source_reason or "").strip()[:80],
            "source_topic": str(source_topic or "").strip()[:60],
        }
        path = local_dir / LOCAL_WRITE_JOURNAL_FILE
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._sync_memory_backend_semantic_event(local_dir, payload)
        except Exception as e:
            print(f"[记忆] local 写入流水追加失败: {e}", flush=True)

    def _upsert_local_memory(
        self,
        workspace: str,
        title: str,
        summary: str,
        keywords: list[str],
        source_type: str = "",
        source_memory_id: str = "",
        source_reason: str = "",
        source_topic: str = "",
        source_entry: dict | None = None,
    ) -> str:
        if not summary:
            _, _, local_dir = self._ensure_memory_dirs(workspace)
            self._append_local_memory_write_journal(
                local_dir,
                action="skip-empty-summary",
                title=title or "对话沉淀",
                summary=summary,
                keywords=keywords,
                source_type=source_type,
                source_memory_id=source_memory_id,
                source_reason=source_reason,
                source_topic=source_topic,
            )
            return "skip-empty-summary"
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        self._ensure_local_memory_layout(local_dir)
        similar = self._find_similar_local_memory(local_dir, title, summary)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        _, l1_dir, l2_dir = self._local_layer_paths(local_dir)
        profile = self._build_local_memory_profile(
            title,
            summary,
            keywords,
            source_type=source_type,
            source_reason=source_reason,
            source_topic=source_topic,
            source_entry=source_entry,
        )
        detail_path: Path | None = None
        summary_text = str(profile.get("current_conclusion") or summary).strip() or summary
        detail_trigger_chars = self._local_l2_detail_trigger_chars()
        preview_chars = self._local_l2_summary_preview_chars()
        if len(summary) > detail_trigger_chars:
            detail_path = l2_dir / self._safe_filename(f"{title}_detail")
            detail_body = (
                f"# {title or '长期记忆详情'}\n\n"
                f"来源：feishu 管家bot 自动沉淀\n\n"
                f"## 详细沉淀 {stamp}\n\n{summary.strip()}\n\n"
                f"## 当前结论\n\n- {summary_text[:220]}\n"
            )
            if detail_path.exists():
                old_detail = detail_path.read_text(encoding="utf-8")
                if summary not in old_detail:
                    detail_path.write_text(old_detail.rstrip() + f"\n\n## 详细沉淀 {stamp}\n\n{summary.strip()}\n", encoding="utf-8")
            else:
                detail_path.write_text(detail_body, encoding="utf-8")
            summary_text = summary.strip()[:preview_chars].rstrip() + "…"
            profile["current_conclusion"] = summary_text
        block = self._render_local_memory_update_block(profile, stamp, detail_path=detail_path)

        if similar and similar.exists():
            old = similar.read_text(encoding="utf-8")
            if summary not in old:
                similar.write_text(old.rstrip() + "\n\n" + block + "\n", encoding="utf-8")
                action = "append-similar"
            else:
                action = "duplicate-skip"
            self._upsert_local_memory_index(local_dir, title or similar.stem, summary, keywords, similar, detail_path=detail_path, profile=profile, source_type=source_type, source_reason=source_reason, source_topic=source_topic)
            self._append_local_memory_write_journal(
                local_dir,
                action=action,
                title=title or similar.stem,
                summary=summary,
                keywords=keywords,
                summary_path=similar,
                detail_path=detail_path,
                source_type=source_type,
                source_memory_id=source_memory_id,
                source_reason=source_reason,
                source_topic=source_topic,
            )
            return action

        target = l1_dir / self._safe_filename(title)
        overflow = local_dir / LOCAL_OVERFLOW_FILE
        files = self._local_memory_managed_l1_files(local_dir)
        is_new_file = not target.exists()
        if not target.exists() and len(files) >= self._local_l1_max_files():
            target = overflow

        action = "write-new"
        if target.exists():
            old = target.read_text(encoding="utf-8")
            if summary not in old:
                target.write_text(old.rstrip() + "\n\n" + block + "\n", encoding="utf-8")
                action = "append-existing"
            else:
                action = "duplicate-skip"
        else:
            target.write_text(f"# {title or '对话沉淀'}\n\n来源：feishu 管家bot 自动沉淀\n\n{block}\n", encoding="utf-8")
            action = "write-new"

        txt = self._file_text(target)
        if len(txt) > LOCAL_MAX_FILE_CHARS:
            target.write_text(txt[:LOCAL_MAX_FILE_CHARS], encoding="utf-8")
            action = "truncated-after-write"
        if target != overflow:
            self._upsert_local_memory_index(local_dir, title or target.stem, summary, keywords, target, detail_path=detail_path, profile=profile, source_type=source_type, source_reason=source_reason, source_topic=source_topic)
        elif action == "write-new" and is_new_file:
            action = "overflow-write-new"
        elif action == "append-existing":
            action = "overflow-append-existing"
        self._append_local_memory_write_journal(
            local_dir,
            action=action,
            title=title or target.stem,
            summary=summary,
            keywords=keywords,
            summary_path=target,
            detail_path=detail_path,
            source_type=source_type,
            source_memory_id=source_memory_id,
            source_reason=source_reason,
            source_topic=source_topic,
        )
        return action

    def _recent_entries_chars(self, entries: list[dict]) -> int:
        return len(json.dumps(entries, ensure_ascii=False))

    def _parse_entry_time(self, entry: dict) -> datetime | None:
        ts = str(entry.get("timestamp") or "").strip()
        if not ts:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(ts, fmt)
            except Exception:
                pass
        return None

    def _extract_json_block(self, text: str) -> dict | None:
        raw = (text or "").strip()
        if not raw:
            return None
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else None
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        try:
            val = json.loads(m.group(0))
            return val if isinstance(val, dict) else None
        except Exception:
            return None

    def _is_new_task_prompt(self, user_prompt: str) -> bool:
        text = (user_prompt or "").strip().lower()
        if not text:
            return False
        return any(h in text for h in NEW_TASK_HINTS)

    def _render_recent_context(self, entries: list[dict], max_chars: int) -> str:
        talk_lines = []
        mental_lines = []
        relation_lines = []
        other_lines = []
        recent_window = max(self._recent_max_items(TALK_RECENT_POOL), self._recent_max_items(BEAT_RECENT_POOL))
        for item in entries[-(recent_window * 2):]:
            ts = str(item.get("timestamp") or "").strip()
            topic = str(item.get("topic") or "").strip()
            summary = str(item.get("summary") or "").strip()
            status = str(item.get("status") or "").strip()
            stream = str(item.get("memory_stream") or "talk").strip()
            if not summary and not topic:
                continue
            head = f"[{ts}] {topic}".strip()
            suffix = ""
            if status == "replying":
                suffix = "（正在回复中）"
            line = f"- {head}{suffix}: {summary}" if summary and head else (f"- {summary}" if summary else f"- {head}{suffix}")
            if summary:
                if stream == "mental":
                    mental_lines.append(line)
                elif stream == "relationship_signal":
                    relation_lines.append(line)
                elif stream in {"task_signal", "heartbeat_observation"}:
                    other_lines.append(line)
                else:
                    talk_lines.append(line)
            elif head:
                talk_lines.append(f"- {head}{suffix}")
        sections = []
        if talk_lines:
            sections.append("【对话短期记忆】\n" + "\n".join(talk_lines[-self._recent_max_items(TALK_RECENT_POOL):]))
        if mental_lines:
            sections.append("【最近在想什么】\n" + "\n".join(mental_lines[-4:]))
        if relation_lines:
            sections.append("【关系与情绪信号】\n" + "\n".join(relation_lines[-3:]))
        if other_lines:
            sections.append("【任务与心跳信号】\n" + "\n".join(other_lines[-4:]))
        text = "\n\n".join(sections).strip()
        return text[-max_chars:] if len(text) > max_chars else text

    def _seconds_to_next_maintenance(self, now: datetime) -> float:
        candidates = []
        for h, m in MAINTENANCE_TIMES:
            c = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if c <= now:
                c = c + timedelta(days=1)
            candidates.append(c)
        nxt = min(candidates)
        return max(30.0, (nxt - now).total_seconds())

    def _seconds_to_next_heartbeat(self, now: datetime, heartbeat_cfg: dict) -> float:
        cfg = heartbeat_cfg or {}
        every_seconds = cfg.get("every_seconds")
        if every_seconds is not None:
            interval_seconds = max(1, float(every_seconds))
        else:
            every_minutes = max(1, int(cfg.get("every_minutes", 180)))
            interval_seconds = every_minutes * 60
        startup_delay_seconds = max(5, int(cfg.get("startup_delay_seconds", 60)))
        align = bool(cfg.get("align_to_interval", False))
        if not align:
            if not self._heartbeat_bootstrap_done:
                self._heartbeat_bootstrap_done = True
                return float(startup_delay_seconds)
            return float(interval_seconds)
        total_seconds = int(now.timestamp())
        next_boundary = ((total_seconds // int(interval_seconds)) + 1) * int(interval_seconds)
        return max(1.0, float(next_boundary - total_seconds))

    def _heartbeat_target(self, cfg: dict, receive_id: str, receive_id_type: str) -> tuple[str, str]:
        target_id = receive_id or str((cfg or {}).get(STARTUP_NOTIFY_OPEN_ID_KEY) or "").strip()
        target_type = receive_id_type or str((cfg or {}).get(STARTUP_NOTIFY_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id"
        return target_id, target_type

    def _talk_target(self, cfg: dict) -> tuple[str, str]:
        target_id = str((cfg or {}).get(TELL_USER_RECEIVE_ID_KEY) or "").strip()
        target_type = str((cfg or {}).get(TELL_USER_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id"
        return target_id, target_type

    def _self_mind_talk_target(self, cfg: dict) -> tuple[str, str]:
        settings = self._self_mind_settings()
        target_id = str(settings.get("talk_receive_id") or "").strip()
        target_type = str(settings.get("talk_receive_id_type") or "open_id").strip() or "open_id"
        if target_id:
            return target_id, target_type
        return self._talk_target(cfg)

    def _self_mind_talk_delivery_override(self) -> dict | None:
        settings = self._self_mind_settings()
        app_id = str(settings.get("talk_app_id") or "").strip()
        app_secret = str(settings.get("talk_app_secret") or "").strip()
        if not app_id or not app_secret:
            return None
        return {
            "app_id": app_id,
            "app_secret": app_secret,
        }

    def _build_self_mind_cycle_receipt_text(self, proposal: dict) -> str:
        payload = proposal if isinstance(proposal, dict) else {}
        if str(payload.get("action_channel") or "").strip() != "heartbeat":
            return ""

        instruction = self._strip_lane_marker(str(payload.get("heartbeat") or payload.get("heartbeat_instruction") or "").strip(), "heartbeat")
        candidate = str(payload.get("candidate") or payload.get("focus") or "").strip()
        reason = str(payload.get("why") or payload.get("heartbeat_reason") or payload.get("reason") or "").strip()
        acceptance = str(payload.get("done_when") or payload.get("acceptance_criteria") or "").strip()

        lines = []
        lines.append("[debug] self_mind handoff")
        if instruction:
            lines.append(instruction[:500])
        elif candidate:
            lines.append(candidate[:260])
        if reason:
            lines.append(f"我把它交给 heartbeat，因为 {reason[:220]}")
        if acceptance:
            lines.append(f"做到这一步就算真的推进了：{acceptance[:220]}")
        if lines:
            lines.append("做完后把新的结果、证据和卡点回给我。")
        return "\n\n".join(lines)

    def _emit_self_mind_cycle_receipt(self, workspace: str, cfg: dict, proposal: dict) -> bool:
        if not self._debug_receipts_enabled(cfg, scope="self_mind"):
            return False
        heartbeat_cfg = (cfg or {}).get("heartbeat") or {}
        if not isinstance(heartbeat_cfg, dict):
            return False
        receive_id = str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_KEY) or "").strip()
        if not bool(heartbeat_cfg.get("enabled")) and not receive_id:
            return False
        receive_id_type = str((heartbeat_cfg or {}).get(HEARTBEAT_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id"
        text = self._build_self_mind_cycle_receipt_text(proposal)
        if not text:
            return False
        sent = self._send_private_message(
            cfg,
            text,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            fallback_to_startup_target=True,
            heartbeat_cfg=heartbeat_cfg,
        )
        print(f"[self-mind·handoff] 发往 heartbeat 窗口: {'成功' if sent else '失败/跳过'}", flush=True)
        return sent

    @staticmethod
    def _markdown_to_interactive_card(md: str) -> dict:
        """与 agent.reply_message 使用的卡片格式一致，便于心跳/启动通知与对话展示对齐"""
        content = (md or "").strip()
        if not content:
            content = "(空)"
        if len(content) > 28000:
            content = content[:28000] + "\n..."
        return {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "body": {
                "direction": "vertical",
                "padding": "12px 12px 12px 12px",
                "elements": [{"tag": "markdown", "content": content}],
            },
        }

    @staticmethod
    def _markdown_to_feishu_post(md: str) -> dict:
        """与 agent 使用的 post 格式一致"""
        content = (md or "").strip()
        if not content:
            content = "(空)"
        if len(content) > 28000:
            content = content[:28000] + "\n..."
        return {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": content}]]}}

    def _send_private_message(
        self,
        cfg: dict,
        text: str,
        receive_id: str = "",
        receive_id_type: str = "open_id",
        fallback_to_startup_target: bool = False,
        heartbeat_cfg: dict | None = None,
    ) -> bool:
        """发送私聊消息。若传入 heartbeat_cfg 且含 app_id/app_secret，则用其获取 token（心跳可单独使用不同飞书应用）。"""
        target_id = str(receive_id or "").strip()
        target_type = str(receive_id_type or "open_id").strip() or "open_id"
        if fallback_to_startup_target:
            target_id, target_type = self._heartbeat_target(cfg, target_id, target_type)
        if not target_id:
            print("[私聊发送] 未配置 receive_id，跳过发送", flush=True)
            return False
        # 心跳可单独指定 app_id/app_secret（原 copilot-bot 凭证），否则用主配置
        hb = heartbeat_cfg or {}
        app_id = str((hb.get("app_id") or (cfg or {}).get("app_id")) or "").strip()
        app_secret = str((hb.get("app_secret") or (cfg or {}).get("app_secret")) or "").strip()
        if not app_id or not app_secret:
            print("[私聊发送] 缺少 app_id/app_secret，跳过发送", flush=True)
            return False
        try:
            session = requests.Session()
            session.trust_env = False
            token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            token_resp = session.post(token_url, json={"app_id": app_id, "app_secret": app_secret}, timeout=12)
            token_data = token_resp.json()
            if token_data.get("code") != 0:
                print(f"[私聊发送] 获取token失败: {token_data}", flush=True)
                return False
            token = token_data.get("tenant_access_token")
            msg_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={target_type}"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            plain = (text or "").strip()[:4000]
            sent = False
            # 与对话回复一致：优先 interactive 卡片（支持 Markdown），再 post，再 text
            if plain:
                card = self._markdown_to_interactive_card(plain)
                body = {"receive_id": target_id, "msg_type": "interactive", "content": json.dumps(card, ensure_ascii=False)}
                resp = session.post(msg_url, headers=headers, json=body, timeout=15)
                data = resp.json()
                if data.get("code") == 0:
                    sent = True
                else:
                    post_content = self._markdown_to_feishu_post(plain)
                    body = {"receive_id": target_id, "msg_type": "post", "content": json.dumps(post_content, ensure_ascii=False)}
                    resp = session.post(msg_url, headers=headers, json=body, timeout=15)
                    data = resp.json()
                    if data.get("code") == 0:
                        sent = True
            if not sent:
                body = {"receive_id": target_id, "msg_type": "text", "content": json.dumps({"text": plain or "(空)"}, ensure_ascii=False)}
                resp = session.post(msg_url, headers=headers, json=body, timeout=15)
                data = resp.json()
                sent = data.get("code") == 0
            if not sent:
                print(f"[私聊发送] 发送失败: {data}", flush=True)
            return sent
        except Exception as e:
            print(f"[私聊发送] 异常: {e}", flush=True)
            return False

    def _send_startup_private_notification(self, cfg: dict, text: str) -> bool:
        receive_id = str((cfg or {}).get(STARTUP_NOTIFY_OPEN_ID_KEY) or "").strip()
        if not receive_id:
            print("[启动通知] 未配置 startup_notify_open_id，跳过私聊通知", flush=True)
            return False
        receive_id_type = str((cfg or {}).get(STARTUP_NOTIFY_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id"
        return self._send_private_message(cfg, text, receive_id=receive_id, receive_id_type=receive_id_type)

    def _check_and_perform_restart(self, workspace: str) -> None:
        """若存在升级/重启申请，则由心跳线程仅通知用户，等待聊天主进程在用户批准后执行。"""
        cfg = self._config_provider() or {}
        pending = self._read_heartbeat_upgrade_request(workspace)
        if isinstance(pending, dict) and str(pending.get("status") or "") == "pending":
            if str(pending.get("user_notified_at") or "").strip():
                return
            notified = self._send_heartbeat_upgrade_request_notification(cfg, pending)
            if notified:
                pending["user_notified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._write_heartbeat_upgrade_request(workspace, pending)
                print("[心跳服务·审批] 已向用户发送升级申请，等待聊天主进程接收批准后执行", flush=True)
            else:
                print("[心跳服务·审批] 升级申请发送失败，将在后续心跳重试", flush=True)
            return

        restart_reason, has_restart_marker = self._load_restart_reason_from_markers(workspace)
        if not has_restart_marker:
            return

        request = self._write_heartbeat_upgrade_request(workspace, self._build_legacy_restart_upgrade_request(restart_reason))
        notified = self._send_heartbeat_upgrade_request_notification(cfg, request)
        if notified:
            request["user_notified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._write_heartbeat_upgrade_request(workspace, request)
            print("[心跳服务·审批] 检测到重启需求，已改为向用户申请批准，不再由心跳线程直接重启", flush=True)
        else:
            print("[心跳服务·审批] 检测到重启需求，但申请发送失败，将在后续心跳重试", flush=True)


def run_startup_maintenance_subprocess(config_snapshot: dict) -> None:
    """子进程入口：执行启动时的长期+短期记忆维护（供 multiprocessing.Process 调用）"""
    cfg_path = str((config_snapshot or {}).get("__config_path") or "").strip()
    if cfg_path:
        set_runtime_log_config(cfg_path)
    _setup_subprocess_logs("startup-maintenance")
    m = MemoryManager(
        config_provider=lambda: config_snapshot,
        run_model_fn=lambda prompt, workspace, timeout, model, cfg=config_snapshot: _run_model_subprocess(
            prompt,
            workspace,
            timeout,
            model,
            cfg,
        ),
    )
    m._run_startup_maintenance_once(config_snapshot)


def run_heartbeat_service_subprocess(config_snapshot: dict) -> None:
    """子进程入口：独立运行心跳循环，并将日志输出到单独文件。"""

    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _read_pid(path: Path) -> int:
        try:
            return int((path.read_text(encoding="utf-8") or "").strip())
        except Exception:
            return 0

    def _acquire_singleton_lock(run_dir: Path, current_pid: int) -> tuple[bool, Path]:
        run_dir.mkdir(parents=True, exist_ok=True)
        lock_path = run_dir / "heartbeat_service.lock"
        for _ in range(3):
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(current_pid).encode("utf-8"))
                finally:
                    os.close(fd)
                return True, lock_path
            except FileExistsError:
                owner = _read_pid(lock_path)
                if owner > 0 and _pid_alive(owner):
                    return False, lock_path
                try:
                    lock_path.unlink(missing_ok=True)
                except Exception:
                    pass
        return False, lock_path

    cfg_path = str((config_snapshot or {}).get("__config_path") or "").strip()
    if cfg_path:
        set_runtime_log_config(cfg_path)
    _setup_subprocess_logs("heartbeat")
    manager_holder = {}

    def _heartbeat_run_model(prompt, workspace, timeout, model, cfg=config_snapshot):
        manager = manager_holder.get("manager")
        runtime_request = manager.get_runtime_request_override() if manager is not None else {}
        return _run_model_via_cli_runtime(
            prompt,
            workspace,
            timeout,
            model,
            cfg,
            runtime_request=runtime_request,
            default_cli="cursor",
        )

    m = MemoryManager(
        config_provider=lambda: config_snapshot,
        run_model_fn=_heartbeat_run_model,
    )
    manager_holder["manager"] = m
    workspace = str((config_snapshot or {}).get("workspace_root") or os.getcwd())
    root = resolve_butler_root(workspace)
    run_dir = root / RUN_DIR_REL
    current_pid = int(os.getpid())

    ok, lock_path = _acquire_singleton_lock(run_dir, current_pid)
    if not ok:
        existing = _read_pid(lock_path)
        print(f"[心跳服务] 检测到已有心跳进程在运行 (PID={existing})，本次启动跳过", flush=True)
        return

    heartbeat_pid_path = m._heartbeat_pid_file(workspace)
    existing_pid = _read_pid(heartbeat_pid_path)
    if existing_pid > 0 and existing_pid != current_pid and _pid_alive(existing_pid):
        print(f"[心跳服务] 已有心跳 PID 文件且进程存活 (PID={existing_pid})，本次启动跳过", flush=True)
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        return

    m._write_heartbeat_pid_file(workspace, int(os.getpid()))
    m._write_heartbeat_watchdog_state(workspace, state="starting", heartbeat_pid=int(os.getpid()), note="heartbeat sidecar started")
    m._write_heartbeat_last_sent(workspace, sent=None)
    print("[心跳服务] 子进程已就绪，立即执行首次心跳", flush=True)
    try:
        m._heartbeat_loop(run_immediately=True)
    except BaseException as exc:
        m._write_heartbeat_watchdog_state(
            workspace,
            state="crashed",
            heartbeat_pid=int(os.getpid()),
            note=f"heartbeat sidecar crashed: {type(exc).__name__}",
        )
        print(
            f"[心跳服务] 子进程异常退出: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc()
        raise
    finally:
        try:
            owner = _read_pid(lock_path)
            if owner == current_pid:
                lock_path.unlink(missing_ok=True)
        except Exception:
            pass


def _subprocess_log_paths(kind: str) -> tuple[Path, Path]:
    base_dir = Path(__file__).resolve().parents[1] / "logs"
    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    stdout_path = base_dir / f"butler_bot_{kind}_{stamp}_001.log"
    stderr_path = base_dir / f"butler_bot_{kind}_{stamp}_001.err.log"
    return stdout_path, stderr_path


class _DailyLineRotatingStream:
    """按天+最多 N 行切分日志文件。"""

    def __init__(self, base_dir: Path, kind: str, is_err: bool, max_lines: int = LOG_MAX_LINES_PER_FILE) -> None:
        self._base_dir = base_dir
        self._kind = str(kind or "default").strip() or "default"
        self._is_err = bool(is_err)
        self._max_lines = max(100, int(max_lines or LOG_MAX_LINES_PER_FILE))
        self._current_day = ""
        self._segment = 1
        self._line_count = 0
        self._handle = None
        self._lock = threading.Lock()
        self._ensure_open()

    def _suffix(self) -> str:
        return ".err.log" if self._is_err else ".log"

    def _build_path(self, day: str, seg: int) -> Path:
        return self._base_dir / f"butler_bot_{self._kind}_{day}_{seg:03d}{self._suffix()}"

    def _count_lines(self, path: Path) -> int:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as rf:
                return sum(1 for _ in rf)
        except Exception:
            return 0

    def _ensure_open(self) -> None:
        today = datetime.now().strftime("%Y%m%d")
        if self._handle and self._current_day == today and self._line_count < self._max_lines:
            return

        if self._handle:
            try:
                self._handle.flush()
                self._handle.close()
            except Exception:
                pass

        self._base_dir.mkdir(parents=True, exist_ok=True)
        seg = 1
        while True:
            p = self._build_path(today, seg)
            if not p.exists():
                self._line_count = 0
                break
            lines = self._count_lines(p)
            if lines < self._max_lines:
                self._line_count = lines
                break
            seg += 1

        self._current_day = today
        self._segment = seg
        self._handle = open(self._build_path(today, seg), "a", encoding="utf-8", buffering=1)

    def _rollover(self) -> None:
        if self._handle:
            try:
                self._handle.flush()
                self._handle.close()
            except Exception:
                pass
        self._segment += 1
        self._line_count = 0
        self._handle = open(self._build_path(self._current_day, self._segment), "a", encoding="utf-8", buffering=1)

    def write(self, text: str) -> int:
        data = str(text or "")
        if not data:
            return 0
        written = 0
        with self._lock:
            self._ensure_open()
            chunks = data.splitlines(keepends=True)
            if not chunks:
                chunks = [data]
            for chunk in chunks:
                if datetime.now().strftime("%Y%m%d") != self._current_day:
                    self._ensure_open()
                if self._line_count >= self._max_lines:
                    self._rollover()
                self._handle.write(chunk)
                written += len(chunk)
                if "\n" in chunk:
                    self._line_count += chunk.count("\n")
            self._handle.flush()
        return written

    def flush(self) -> None:
        with self._lock:
            if self._handle:
                self._handle.flush()

    def close(self) -> None:
        with self._lock:
            if self._handle:
                try:
                    self._handle.flush()
                    self._handle.close()
                except Exception:
                    pass
                self._handle = None

    def isatty(self) -> bool:
        return False


def _setup_subprocess_logs(kind: str) -> None:
    stdout_path, stderr_path = _subprocess_log_paths(kind)
    try:
        base_dir = stdout_path.parent
        sys.stdout = _DailyLineRotatingStream(base_dir, kind, is_err=False, max_lines=LOG_MAX_LINES_PER_FILE)
        sys.stderr = _DailyLineRotatingStream(base_dir, kind, is_err=True, max_lines=LOG_MAX_LINES_PER_FILE)
        print(f"[{kind}] logging redirected with daily+{LOG_MAX_LINES_PER_FILE}-line rotation: {base_dir}", flush=True)
    except Exception as e:
        print(f"[{kind}] logging redirect failed: {e}", flush=True)


def _terminate_subprocess_tree(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
            )
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _decode_subprocess_stream(payload: bytes | str | None) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if not payload:
        return ""

    encodings: list[str] = ["utf-8", "utf-8-sig"]
    preferred = str(locale.getpreferredencoding(False) or "").strip()
    if preferred:
        encodings.append(preferred)
    encodings.extend(["gbk", "cp936"])

    seen: set[str] = set()
    for encoding_name in encodings:
        key = encoding_name.lower()
        if not encoding_name or key in seen:
            continue
        seen.add(key)
        try:
            return payload.decode(encoding_name)
        except Exception:
            continue
    return payload.decode("utf-8", errors="replace")


def _run_model_subprocess(prompt: str, workspace: str, timeout: int, model: str, cfg: dict | None = None) -> tuple[str, bool]:
    """与对话路径一致：使用相同 env、编码（utf-8 + errors=replace）和 subprocess 方式，避免心跳与对话表现不一致。"""
    agent_cmd = resolve_cursor_cli_cmd_path(cfg)
    if not os.path.isfile(agent_cmd):
        return f"错误：未找到 Cursor CLI（管家bot 依赖），请检查路径 {agent_cmd}", False
    args = [
        agent_cmd, "-p", "--force", "--trust", "--approve-mcps",
        "--model", model or "auto", "--output-format", "json",
        "--workspace", workspace,
    ]
    started = time.perf_counter()
    grace_seconds = min(300, max(30, int(timeout // 2) if int(timeout or 0) > 0 else 60))
    cli_env = build_cursor_cli_env(cfg)
    try:
        print(
            f"[heartbeat-model] start | model={model or 'auto'} | timeout={timeout}s | workspace={workspace} | appdata={cli_env.get('APPDATA', '')}",
            flush=True,
        )
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            universal_newlines=True,
            cwd=workspace,
            env=cli_env,
        )
        stdout_text = ""
        stderr_text = ""
        timed_out = False
        try:
            stdout_text, stderr_text = proc.communicate(input=prompt or "", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout or ""
            stderr_text = exc.stderr or ""
            print(
                f"[heartbeat-model] soft-timeout | model={model or 'auto'} | timeout={timeout}s | grace={grace_seconds}s",
                flush=True,
            )
            try:
                extra_out, extra_err = proc.communicate(timeout=grace_seconds)
                stdout_text += extra_out or ""
                stderr_text += extra_err or ""
            except subprocess.TimeoutExpired as grace_exc:
                timed_out = True
                stdout_text += grace_exc.stdout or ""
                stderr_text += grace_exc.stderr or ""
                proc.kill()
                final_out, final_err = proc.communicate()
                stdout_text += final_out or ""
                stderr_text += final_err or ""

        duration = time.perf_counter() - started
        out = ""
        if proc.returncode == 0 and stdout_text:
            try:
                data = json.loads(stdout_text.strip())
                out = (data.get("result") or "").strip()
            except Exception:
                out = stdout_text.strip()
        if not out and stderr_text:
            out = stderr_text.strip()
        print(
            f"[heartbeat-model] done | exit={proc.returncode} | duration={duration:.1f}s | timeout={timed_out} | out_len={len(out)}",
            flush=True,
        )
        if timed_out:
            return out or "执行超时", False
        if out and proc.returncode == 0:
            return out, True
        return out or f"管家bot 执行失败 (exit={proc.returncode})", False
    except Exception as e:
        duration = time.perf_counter() - started
        print(
            f"[heartbeat-model] exception | model={model or 'auto'} | duration={duration:.1f}s | error={e}",
            flush=True,
        )
        return f"管家bot 执行异常: {e}", False


def _run_model_via_cli_runtime(
    prompt: str,
    workspace: str,
    timeout: int,
    model: str,
    cfg: dict | None = None,
    runtime_request: dict | None = None,
    *,
    default_cli: str = "cursor",
    codex_allow_source: str = "heartbeat_planner",
) -> tuple[str, bool]:
    from runtime import cli_runtime as cli_runtime_service

    request = dict(runtime_request or {})
    requested_cli = cli_runtime_service.normalize_cli_name(str(request.get("cli") or default_cli), cfg)
    if requested_cli == "codex" and str(request.get("source") or "").strip() != codex_allow_source:
        request["cli"] = "cursor"
        request["model"] = str(model or "auto").strip() or "auto"
    else:
        request["cli"] = requested_cli
        request["model"] = str(request.get("model") or model or "auto").strip() or "auto"
    started = time.perf_counter()
    try:
        print(
            f"[heartbeat-model] start | cli={request.get('cli')} | model={request.get('model')} | timeout={timeout}s | workspace={workspace}",
            flush=True,
        )
        out, ok = cli_runtime_service.run_prompt(prompt, workspace, timeout, cfg, request, stream=False)
        duration = time.perf_counter() - started
        print(
            f"[heartbeat-model] done | cli={request.get('cli')} | ok={ok} | duration={duration:.1f}s | out_len={len(str(out or ''))}",
            flush=True,
        )
        return out, ok
    except Exception as exc:
        duration = time.perf_counter() - started
        print(
            f"[heartbeat-model] exception | cli={request.get('cli')} | model={request.get('model')} | duration={duration:.1f}s | error={exc}",
            flush=True,
        )
        return f"管家bot 执行异常: {exc}", False

