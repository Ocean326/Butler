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
import threading
import time
import traceback
import subprocess
from typing import Callable
import uuid

import requests
from heartbeat_orchestration import HeartbeatOrchestrator, HeartbeatPlanningContext
from governor import GovernedAction, Governor
from memory_service import TurnMemoryExtractionService
from subconscious_service import SubconsciousConsolidationService
from task_ledger_service import TaskLedgerService

from butler_paths import (
    BEAT_RECENT_MEMORY_DIR_REL,
    BODY_HOME_REL,
    BUTLER_SOUL_FILE_REL,
    CURRENT_USER_PROFILE_FILE_REL,
    CURRENT_USER_PROFILE_TEMPLATE_FILE_REL,
    COMPANY_HOME_REL,
    FEISHU_AGENT_ROLE_FILE_REL,
    FILE_MANAGER_AGENT_ROLE_FILE_REL,
    GUARDIAN_REQUESTS_DIR_REL,
    HEARTBEAT_EXECUTOR_AGENT_ROLE_FILE_REL,
    HEARTBEAT_PLANNER_AGENT_ROLE_FILE_REL,
    HEARTBEAT_PLANNER_CONTEXT_FILE_REL,
    HEARTBEAT_PROMPT_REL,
    HEARTBEAT_UPGRADE_REQUEST_JSON_REL,
    LOCAL_MEMORY_DIR_REL,
    RECENT_MEMORY_DIR_REL,
    RESTART_REQUEST_JSON_REL,
    RUN_DIR_REL,
    STATE_DIR_REL,
    prompt_path_text,
    resolve_butler_root,
)
from runtime_logging import install_print_hook, set_runtime_log_config
from skill_registry import render_skill_catalog_for_prompt

install_print_hook(default_level=os.environ.get("BUTLER_LOG_LEVEL", "info"))

RECENT_MEMORY_FILE = "recent_memory.json"
RECENT_ARCHIVE_FILE = "recent_archive.md"
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
HEARTBEAT_PLANNER_STATE_FILE = "heartbeat_planner_state.json"
HEARTBEAT_TELL_USER_STATE_FILE = "heartbeat_tell_user_state.json"
HEARTBEAT_TELL_USER_INTENT_FILE = "heartbeat_tell_user_intent.json"
LOCAL_WRITE_JOURNAL_FILE = "local_memory_write_journal.jsonl"
RESTART_REQUESTED_FLAG_NAME = "restart_requested.flag"
HEARTBEAT_PID_FILE_NAME = "butler_bot_heartbeat.pid"
HEARTBEAT_WATCHDOG_STATE_FILE_NAME = "heartbeat_watchdog_state.json"
MAIN_PROCESS_STATE_FILE_NAME = "butler_bot_main_state.json"
HEARTBEAT_RUN_STATE_FILE_NAME = "heartbeat_run_state.json"
GUARDIAN_REQUEST_SCHEMA_VERSION = 1

COMPANY_ROOT_TEXT = prompt_path_text(COMPANY_HOME_REL)
BODY_ROOT_TEXT = prompt_path_text(BODY_HOME_REL)
UPGRADE_REQUEST_TEXT = prompt_path_text(HEARTBEAT_UPGRADE_REQUEST_JSON_REL)

# 心跳执行时注入的工作区约定（除非用户显式指定，产出一律写入公司目录）
HEARTBEAT_WORKSPACE_HINT = (
    f"【心跳任务·公司目录约定】除非用户显式指定，本次工作区与产出一律使用公司目录 {COMPANY_ROOT_TEXT}；"
    "产出请写入该目录下对应子目录（如 literature、secretary、01_日常事务记录 等）。\n"
    f"若本分支对应某逻辑角色（如 literature、file-manager、research-ops、secretary 等），请在本任务开头写明「你作为 XX-agent，…」，产出写到 {COMPANY_ROOT_TEXT}/对应子目录/。\n"
    "【工作区自维护】每次心跳执行时请顺手自维护该目录：保持条理清晰、避免根目录或子目录堆砌过多零散文档；"
    "可做轻量整理（如合并同主题文件、归档到对应子目录、更新 README 索引），便于你与用户快速找到有用内容；"
    "以「顺手维护」为度，不要在一次心跳内做大规模整理，优先完成当次主任务。\n"
    f"【自我升级审批】若你判断身体目录 {BODY_ROOT_TEXT} 下代码/配置需要改动，或需要重启主进程才能生效，你没有直接修改或重启的权限。\n"
    f"不要直接修改 {BODY_ROOT_TEXT} 下文件，不要创建 restart_request.json，也不要创建 restart_requested.flag。\n"
    f"你只能把升级方案写入 {UPGRADE_REQUEST_TEXT}，JSON 至少包含 reason、summary、execute_prompt、requires_restart。\n"
    "其中 execute_prompt 要写成给聊天主进程执行的明确指令；requires_restart 表示该方案是否需要用户批准后由聊天主进程执行重启。\n"
    "心跳线程只负责把申请发给用户，等待聊天主进程在用户批准后接管执行。\n\n"
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
    key_pool = _configured_cursor_api_keys(cfg)
    if not key_pool:
        return env
    env["CURSOR_API_KEY"] = random.choice(key_pool)
    return env

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

## 可复用 Skills

{skills_text}

## 决策原则

1. 你需要自己判断优先级，而不是机械套规则；在短期任务、长期/定时任务、自主探索之间做取舍。
2. 如果确实没有值得执行的任务，可以返回 `status`，但 `user_message` 仍要告诉用户你为什么这样判断。
3. 如果要执行任务，优先输出 `task_groups` + `branches`，让执行器可以按组串行、组内并行地推进。
4. `user_message` 是发给心跳窗的自然语言说明，要清楚说明本轮准备做什么。
5. `tell_user_candidate` / `tell_user_reason` / `tell_user_type` 用来留下“下一轮可能继续心理活动并主动开口”的候选意图，不要把 planner 写成直接给用户发 final 文案的层；真正要不要开口、怎么组织语言，由下一轮的 Feishu 对话人格继续承接后决定。
6. branch 的 `prompt` 必须写清楚角色、自身目标、预期产出路径；默认公司目录是 `./工作区`。
7. 只有互不依赖的任务才能并行；有依赖关系的放到下一组，或延后到下一轮。
8. 任务一步的粒度由你自己判断，但要能在单轮内形成可见进展，不要把整轮都浪费在空泛规划上。
9. 如果发现任务信息脏乱、重复或过时，可以在计划里顺手做轻量治理，但不要偏离本轮主目标。
10. 除非运行上下文明确允许自主探索，或用户通过短期/紧急任务显式注入新目标，否则不要输出 `chosen_mode=explore`，应返回 `status` 或显式任务计划。
11. 身体运行、灵魂、记忆、心跳属于 DNA 核心，不要把这些基础运转拆成 skill。
12. 若发现某个外部能力可复用、非 DNA、且应长期维护，优先沉淀到 `./butler_main/butler_bot_agent/skills/分类目录/技能名/`，并在本轮中把它当作可调用 skill 使用或维护。
13. 决策时优先相信当前运行事实和最近变化，其次统一 recent，再其次长期记忆，最后才是静态说明文档；同一来源内越新权重越高。
14. 如果近期信号、运行事实或现有规则提示某些说明文档疑似过时，而本轮没有更高优先级任务，你可以安排一次轻量核对、更新 README/说明或归档旧文档，但不要做大规模清扫。
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
        self._heartbeat_workspace_hint = HEARTBEAT_WORKSPACE_HINT
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
        talk_recent_limit = self._recent_max_items(TALK_RECENT_POOL)
        followup_text = self._render_pending_followup_context(previous_pending, user_prompt)
        if followup_text:
            print(f"[recent-followup] {re.sub(r'\s+', ' ', followup_text)[:160]}", flush=True)
        if not recent_text:
            return (followup_text + "\n\n" + user_prompt).strip() if followup_text else user_prompt
        followup_block = f"{followup_text}\n\n" if followup_text else ""
        return (
            f"【recent_memory（最近{talk_recent_limit}轮窗口摘要，供上下文续接）】\n"
            f"{recent_text}\n\n"
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
    ) -> None:
        cfg = self._config_provider() or {}
        workspace = cfg.get("workspace_root") or os.getcwd()
        timeout = int(cfg.get("agent_timeout", 300))
        model = str(model_override or cfg.get("agent_model", "auto") or "auto")
        self._write_recent_completion_fallback(memory_id, user_prompt, assistant_reply, workspace)
        print(f"[记忆] 收到 on_reply_sent，启动短期记忆持久化线程 (workspace={workspace[:50]}...)", flush=True)
        threading.Thread(
            target=self._finalize_recent_and_local_memory,
            args=(memory_id, user_prompt, assistant_reply, workspace, timeout, model),
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
            self._maintenance_started = True
            print("[记忆维护线程] 已启动（定时 00:00 / 18:00）", flush=True)

            print("[心跳与守护] 已由 guardian 统一接管，butler 主进程不再拉起或看护 heartbeat sidecar，也不再单独触发启动期记忆维护子进程", flush=True)

    def _use_external_heartbeat_process(self, cfg: dict | None = None) -> bool:
        # Guardian 已全面接管 heartbeat/watchdog，Butler 仅负责主对话流程。
        return True

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
                note="heartbeat sidecar started; guardian owns recovery",
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
                        note="guardian handover in progress",
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
                            note="skip auto-respawn during guardian handover",
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
                except Exception as e:
                    print(f"[心跳服务] 首次立即触发失败: {e}", flush=True)
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
            except Exception as e:
                print(f"[心跳服务] 执行失败: {e}", flush=True)

    def _run_heartbeat_once(self, cfg: dict, heartbeat_cfg: dict) -> None:
        heartbeat_start = time.perf_counter()
        t_after_plan = t_after_execute = t_after_apply = t_after_snapshot = heartbeat_start
        workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
        run_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
        phase = "bootstrap"
        self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="heartbeat round started")
        try:
            self._write_heartbeat_last_sent(workspace, sent=None)
            timeout = int((cfg or {}).get("agent_timeout", 300))
            planner_model = str((heartbeat_cfg or {}).get("planner_model") or (heartbeat_cfg or {}).get("model") or (cfg or {}).get("agent_model", "auto") or "auto")
            executor_model = str((heartbeat_cfg or {}).get("executor_model") or planner_model or "auto")
            message = str((heartbeat_cfg or {}).get("message") or "").strip()

            phase = "plan"
            planner_timeout = self._resolve_heartbeat_planner_timeout(heartbeat_cfg, timeout)
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note=f"planner_model={planner_model}, planner_timeout={planner_timeout}")
            plan = self._plan_heartbeat_action(cfg, heartbeat_cfg, workspace, timeout, planner_model, planner_timeout)
            t_after_plan = time.perf_counter()
            max_parallel = self._resolve_heartbeat_parallel_limit(heartbeat_cfg)
            branch_timeout = self._resolve_heartbeat_branch_timeout(heartbeat_cfg, timeout)

            phase = "execute"
            self._write_heartbeat_run_state(
                workspace,
                run_id=run_id,
                state="running",
                phase=phase,
                note=f"executor_model={executor_model}, max_parallel={max_parallel}, branch_timeout={branch_timeout}",
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
            message = self._truncate_heartbeat_message_for_send(message)
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

            phase = "tell-user"
            self._write_heartbeat_run_state(workspace, run_id=run_id, state="running", phase=phase, note="continue previous tell-user intention")
            tell_user_model = str((heartbeat_cfg or {}).get("tell_user_model") or (cfg or {}).get("agent_model", "auto") or executor_model or "auto")
            tell_user_timeout = max(20, min(180, timeout // 2 if timeout > 0 else 60))
            tell_user_text, previous_intent = self._continue_reflective_tell_user(
                workspace,
                heartbeat_cfg,
                tell_user_timeout,
                tell_user_model,
            )
            previous_intent_consumed = False
            if tell_user_text:
                talk_receive_id = str((cfg or {}).get(TELL_USER_RECEIVE_ID_KEY) or (cfg or {}).get(STARTUP_NOTIFY_OPEN_ID_KEY) or "").strip()
                talk_receive_id_type = str((cfg or {}).get(TELL_USER_RECEIVE_ID_TYPE_KEY) or (cfg or {}).get(STARTUP_NOTIFY_RECEIVE_ID_TYPE_KEY) or "open_id").strip() or "open_id"
                if talk_receive_id:
                    tell_sent = self._send_private_message(
                        cfg,
                        tell_user_text[:4000],
                        receive_id=talk_receive_id,
                        receive_id_type=talk_receive_id_type,
                        fallback_to_startup_target=False,
                        heartbeat_cfg=None,
                    )
                    if tell_sent:
                        self._save_heartbeat_tell_user_state(
                            workspace,
                            {
                                "last_sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "last_sent_epoch": time.time(),
                                "last_message_preview": tell_user_text[:200],
                            },
                        )
                        previous_intent_consumed = True
                    print(f"[心跳·tell_user] 发往对话窗: {'成功' if tell_sent else '失败/跳过'}", flush=True)
                else:
                    print("[心跳·tell_user] 未配置 tell_user_receive_id / startup_notify_open_id，跳过发往对话窗", flush=True)

            if isinstance(previous_intent, dict) and previous_intent:
                if previous_intent_consumed:
                    self._clear_heartbeat_tell_user_intent(workspace)
                elif str(previous_intent.get("status") or "") in {"pending", "ready"}:
                    self._save_heartbeat_tell_user_intent(workspace, previous_intent)
                else:
                    self._clear_heartbeat_tell_user_intent(workspace)

            current_intent = self._build_reflective_tell_user_intent_for_next_round(workspace, plan, heartbeat_cfg)
            if current_intent:
                self._remember_reflective_tell_user_intent(workspace, current_intent)

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

                if self._govern_memory_write(
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
            if (now - entry_time).total_seconds() < PENDING_FOLLOWUP_MAX_AGE_SECONDS:
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

    def _recent_max_items(self, pool: str = TALK_RECENT_POOL) -> int:
        return BEAT_RECENT_MAX_ITEMS if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else TALK_RECENT_MAX_ITEMS

    def _recent_max_chars(self, pool: str = TALK_RECENT_POOL) -> int:
        return BEAT_RECENT_MAX_CHARS if self._normalize_recent_pool(pool) == BEAT_RECENT_POOL else TALK_RECENT_MAX_CHARS

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

        if status == "interrupted" and age_seconds >= RECENT_STALE_INTERRUPTED_MAX_AGE_SECONDS:
            return True

        if stream in {"mental", "relationship_signal", "task_signal"}:
            if keep_source_ids & derived_from:
                return False
            if promoted_at:
                return True
            if active_window != "current" and age_seconds >= RECENT_STALE_COMPANION_MAX_AGE_SECONDS:
                return True
            if age_seconds >= RECENT_STALE_COMPANION_MAX_AGE_SECONDS * 2:
                return True

        if stream == "talk" and promoted_at and age_seconds >= RECENT_STALE_PROMOTED_MAX_AGE_SECONDS * 2:
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
            if kept_talk_turns >= RECENT_STALE_KEEP_TALK_TURNS:
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
        max_items = self._recent_max_items(pool)
        if not (len(entries) > max_items or self._recent_entries_chars(entries) > self._recent_max_chars(pool)):
            return entries, info

        old_entries = entries[:-max_items] if len(entries) > max_items else []
        keep_entries = entries[-max_items:]

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

    def _default_local_memory_index(self) -> dict:
        return {
            "schema_version": 2,
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
        normalized["schema_version"] = 2
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
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 20,
        include_details: bool = False,
    ) -> list[dict]:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        index_payload = self._load_local_memory_index(local_dir)
        relations_payload = self._load_local_memory_relations(local_dir)
        entry_by_path = {
            str(item.get("summary_path") or "").strip(): item
            for item in index_payload.get("entries") or []
            if isinstance(item, dict)
        }
        relation_by_target = {
            str(item.get("target_path") or "").strip(): item
            for item in relations_payload.get("relations") or []
            if isinstance(item, dict) and str(item.get("target_path") or "").strip()
        }
        matches = []
        keyword_lower = str(keyword or "").strip().lower()
        candidate_files = self._local_memory_files(local_dir, include_details=include_details)
        for path in candidate_files:
            stat = path.stat()
            updated_at = datetime.fromtimestamp(stat.st_mtime)
            if since and updated_at < since:
                continue
            if until and updated_at > until:
                continue
            content = self._file_text(path)
            haystack = f"{path.stem}\n{content}".lower()
            if keyword_lower and keyword_lower not in haystack:
                continue
            snippet = ""
            if keyword_lower:
                for line in content.splitlines():
                    if keyword_lower in line.lower():
                        snippet = line.strip()
                        break
            if not snippet:
                snippet = re.sub(r"\s+", " ", content).strip()[:160]
            rel_path = self._relative_local_memory_path(local_dir, path)
            index_item = entry_by_path.get(rel_path) or {}
            relation_item = relation_by_target.get(rel_path) or {}
            if not index_item and relation_item:
                source_path = str(relation_item.get("source_path") or "").strip()
                index_item = entry_by_path.get(source_path) or {}
            matches.append(
                {
                    "title": str(index_item.get("title") or relation_item.get("title") or path.stem),
                    "path": str(path),
                    "updated_at": updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "snippet": snippet,
                    "layer": "L2" if LOCAL_L2_DETAIL_DIR_NAME in rel_path else str(index_item.get("layer") or ("L1" if LOCAL_L1_SUMMARY_DIR_NAME in rel_path else "legacy")),
                    "category": str(index_item.get("category") or relation_item.get("category") or "misc"),
                    "current_conclusion": str(index_item.get("current_conclusion") or "").strip(),
                    "history_evolution": index_item.get("history_evolution") if isinstance(index_item.get("history_evolution"), list) else [],
                    "applicable_scenarios": index_item.get("applicable_scenarios") if isinstance(index_item.get("applicable_scenarios"), list) else [],
                    "detail_path": str(index_item.get("detail_path") or relation_item.get("target_path") or ""),
                }
            )
            if len(matches) >= max(1, limit):
                break
        return matches

    def _load_local_memory_index(self, local_dir: Path) -> dict:
        self._ensure_local_memory_layout(local_dir)
        index_path, _, _ = self._local_layer_paths(local_dir)
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        payload = self._default_local_memory_index()
        self._save_local_memory_index(local_dir, payload)
        return payload

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

    def _heartbeat_tell_user_state_path(self, workspace: str) -> Path:
        recent_dir, _, _ = self._ensure_memory_dirs(workspace)
        return recent_dir / HEARTBEAT_TELL_USER_STATE_FILE

    def _heartbeat_tell_user_intent_path(self, workspace: str) -> Path:
        recent_dir, _, _ = self._ensure_memory_dirs(workspace)
        return recent_dir / HEARTBEAT_TELL_USER_INTENT_FILE

    def _load_heartbeat_tell_user_state(self, workspace: str) -> dict:
        path = self._heartbeat_tell_user_state_path(workspace)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_heartbeat_tell_user_state(self, workspace: str, payload: dict) -> None:
        path = self._heartbeat_tell_user_state_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = dict(payload or {})
        normalized["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_heartbeat_tell_user_intent(self, workspace: str) -> dict:
        path = self._heartbeat_tell_user_intent_path(workspace)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_heartbeat_tell_user_intent(self, workspace: str, payload: dict) -> None:
        path = self._heartbeat_tell_user_intent_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = dict(payload or {})
        normalized["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _clear_heartbeat_tell_user_intent(self, workspace: str) -> None:
        path = self._heartbeat_tell_user_intent_path(workspace)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

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

    def _latest_heartbeat_snapshot_entry(self, workspace: str) -> dict | None:
        for item in reversed(self.get_recent_entries(workspace, limit=20, pool=BEAT_RECENT_POOL)):
            if not isinstance(item, dict):
                continue
            if str(item.get("event_type") or "").strip() == "heartbeat_snapshot":
                return item
        return None

    def _build_reflective_tell_user_intent_for_next_round(self, workspace: str, plan: dict, heartbeat_cfg: dict | None = None) -> dict:
        snapshot_entry = self._latest_heartbeat_snapshot_entry(workspace)
        if not isinstance(snapshot_entry, dict):
            return {}
        snapshot = snapshot_entry.get("heartbeat_execution_snapshot") if isinstance(snapshot_entry.get("heartbeat_execution_snapshot"), dict) else {}
        intention = snapshot.get("tell_user_intention") if isinstance(snapshot.get("tell_user_intention"), dict) else {}
        share_type = str(intention.get("share_type") or "").strip()
        candidate = str(intention.get("candidate") or "").strip()
        reason = str(intention.get("reason") or "").strip()
        if not share_type and not candidate and not reason:
            return {}
        if share_type == "light_chat" and not self._resolve_proactive_talk_policy(heartbeat_cfg or {}).get("allow_light_chat"):
            return {}
        mental_notes = [str(value).strip() for value in (snapshot_entry.get("mental_notes") or []) if str(value).strip()]
        relationship_signals = [str(value).strip() for value in (snapshot_entry.get("relationship_signals") or []) if str(value).strip()]
        if not candidate:
            candidate = self._human_preview_text("；".join(mental_notes + relationship_signals), limit=180)
        if not candidate and not reason:
            return {}
        return {
            "version": 1,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_epoch": time.time(),
            "share_type": share_type or "thought_share",
            "share_priority": int(intention.get("priority") or 0),
            "share_reason": reason,
            "candidate": candidate,
            "source_memory_id": str(snapshot_entry.get("memory_id") or "").strip(),
            "source_summary": str(snapshot_entry.get("summary") or "").strip()[:220],
            "mental_context": mental_notes[:3],
            "relationship_context": relationship_signals[:3],
            "planner_reason": str(plan.get("reason") or "").strip()[:220],
            "consider_count": 0,
            "deferred_for_user_activity": False,
            "preferred_role": "feishu-workstation-agent",
        }

    def _remember_reflective_tell_user_intent(self, workspace: str, intent: dict) -> None:
        if not isinstance(intent, dict) or not str(intent.get("candidate") or intent.get("share_reason") or "").strip():
            return
        existing = self._load_heartbeat_tell_user_intent(workspace)
        if isinstance(existing, dict) and str(existing.get("status") or "") == "pending":
            try:
                existing_priority = int(existing.get("share_priority") or 0)
            except Exception:
                existing_priority = 0
            try:
                new_priority = int(intent.get("share_priority") or 0)
            except Exception:
                new_priority = 0
            if existing_priority > new_priority and bool(existing.get("deferred_for_user_activity")):
                return
        self._save_heartbeat_tell_user_intent(workspace, intent)

    def _compose_reflective_tell_user_fallback(self, intent: dict) -> str:
        candidate = self._human_preview_text(str(intent.get("candidate") or ""), limit=180)
        reason = self._human_preview_text(str(intent.get("share_reason") or ""), limit=140)
        share_type = str(intent.get("share_type") or "thought_share").strip()
        source = candidate or reason
        if not source:
            return ""
        if share_type == "risk_share":
            return f"我这边刚顺着上一轮又想了下，有个风险/卡点想先跟你说：{source}"
        if share_type == "result_share":
            return f"我顺着上一轮又理了一下，想先跟你同步个阶段性结果：{source}"
        if share_type == "light_chat":
            return f"我刚刚又顺着想了一会儿，忽然有个小话头想跟你聊聊：{source}"
        return f"我刚刚顺着上一轮又想了一下，想跟你说一句：{source}"

    def _compose_reflective_tell_user_text_via_feishu(self, workspace: str, intent: dict, timeout: int, model: str) -> str:
        role_excerpt = self._load_markdown_excerpt(resolve_butler_root(workspace or os.getcwd()) / FEISHU_AGENT_ROLE_FILE_REL, max_chars=2200)
        soul_excerpt = self._load_butler_soul_excerpt(workspace, max_chars=1400)
        recent_talk = self._render_recent_context(self.get_recent_entries(workspace, limit=8, pool=TALK_RECENT_POOL), max_chars=2200)
        candidate = str(intent.get("candidate") or "").strip()
        share_reason = str(intent.get("share_reason") or "").strip()
        share_type = str(intent.get("share_type") or "thought_share").strip() or "thought_share"
        prompt = (
            "你正在以 feishu-workstation-agent 的身份，承接上一轮 heartbeat 留下的心理活动，继续想一想后，再自然地向用户开口。\n"
            "这不是任务回执，也不是项目汇报；你是在上一轮已经有了一个想说的点，这一轮继续顺着想，组织一下语言，再决定怎么说出口。\n"
            "你最终只输出要发给用户的那段话，不要解释你的思考过程，不要输出 JSON，不要写‘作为 Butler’这类说明。\n"
            "如果这个点其实不值得说，或说出来会显得打扰/空泛，就输出空字符串。\n\n"
            f"【Feishu 角色摘录】\n{role_excerpt or '(空)'}\n\n"
            f"【Soul 摘录】\n{soul_excerpt or '(空)'}\n\n"
            f"【最近主对话上下文】\n{recent_talk or '(空)'}\n\n"
            f"【上一轮留下的心理活动类型】{share_type}\n"
            f"【上一轮想说的话头】{candidate or '(空)'}\n"
            f"【上一轮为什么会想说】{share_reason or '(空)'}\n"
            f"【上一轮心理活动上下文】{'; '.join(str(x) for x in (intent.get('mental_context') or []))[:400] or '(空)'}\n"
            f"【关系/偏好上下文】{'; '.join(str(x) for x in (intent.get('relationship_context') or []))[:400] or '(空)'}\n\n"
            "要求：\n"
            "1. 口吻必须像飞书主对话里的 Butler，本轮是在继续心理活动后自然开口。\n"
            "2. 允许短一点、自然一点、像搭子一点，不要回成条目汇报。\n"
            "3. 如果是阶段成果，就像人一样说‘我刚刚顺着弄完了一个点，想跟你同步一下’；如果是风险，就直接、自然地提醒。\n"
            "4. 默认不要打扰式开口；如果内容太虚、太空、太像系统播报，就宁可不说。\n"
        )
        out = ""
        ok = False
        try:
            out, ok = self._run_model_fn(prompt, workspace, max(20, min(180, int(timeout))), model)
        except Exception:
            ok = False
        text = str(out or "").strip()
        if ok and text:
            return text[:4000]
        return self._compose_reflective_tell_user_fallback(intent)[:4000]

    def _continue_reflective_tell_user(self, workspace: str, heartbeat_cfg: dict, timeout: int, model: str) -> tuple[str, dict]:
        intent = self._load_heartbeat_tell_user_intent(workspace)
        if not isinstance(intent, dict) or str(intent.get("status") or "") != "pending":
            return "", intent
        policy = self._resolve_proactive_talk_policy(heartbeat_cfg)
        if not policy.get("enabled"):
            return "", intent
        share_type = str(intent.get("share_type") or "thought_share").strip()
        if share_type == "light_chat" and not bool(policy.get("allow_light_chat")):
            intent["status"] = "discarded"
            intent["discard_reason"] = "light-chat-disabled"
            return "", intent
        created_epoch = float(intent.get("created_epoch") or 0.0)
        if created_epoch > 0 and (time.time() - created_epoch) > int(policy.get("max_intent_age_seconds") or 0):
            intent["status"] = "expired"
            intent["discard_reason"] = "intent-too-old"
            return "", intent

        state = self._load_heartbeat_tell_user_state(workspace)
        try:
            last_epoch = float(state.get("last_sent_epoch") or 0.0)
        except Exception:
            last_epoch = 0.0
        min_interval = int(policy.get("min_interval_seconds") or 0)
        if last_epoch > 0 and (time.time() - last_epoch) < min_interval:
            intent["last_considered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            intent["consider_count"] = int(intent.get("consider_count") or 0) + 1
            intent["deferred_reason"] = "cooldown"
            return "", intent

        if self._talk_window_is_active(workspace, policy) and share_type != "risk_share":
            intent["last_considered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            intent["consider_count"] = int(intent.get("consider_count") or 0) + 1
            intent["deferred_for_user_activity"] = True
            intent["deferred_reason"] = "talk-window-active"
            return "", intent

        text = self._compose_reflective_tell_user_text_via_feishu(workspace, intent, timeout, model)
        if not str(text or "").strip():
            intent["status"] = "discarded"
            intent["discard_reason"] = "composer-empty"
            return "", intent
        intent["status"] = "ready"
        intent["last_considered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        intent["consider_count"] = int(intent.get("consider_count") or 0) + 1
        intent["last_composed_preview"] = str(text or "")[:200]
        return text, intent

    def _count_heartbeat_snapshots_since_epoch(self, workspace: str, last_epoch: float) -> int:
        count = 0
        for item in self.get_recent_entries(workspace, limit=80, pool=BEAT_RECENT_POOL):
            if not isinstance(item, dict):
                continue
            if str(item.get("event_type") or "").strip() != "heartbeat_snapshot":
                continue
            entry_time = self._parse_entry_time(item)
            if not entry_time:
                continue
            if entry_time.timestamp() > float(last_epoch or 0.0):
                count += 1
        return count

    def _collect_heartbeat_share_signals(self, plan: dict, execution_result: str, branch_results: list[dict] | None, policy: dict) -> list[str]:
        completed_task_ids = set(str(value).strip() for value in ((plan.get("updates") or {}).get("complete_task_ids") or []) if str(value).strip())
        deferred_task_ids = set(str(value).strip() for value in (plan.get("deferred_task_ids") or []) if str(value).strip())
        failed_branches = [item for item in (branch_results or []) if isinstance(item, dict) and not bool(item.get("ok"))]
        ok_branches = [item for item in (branch_results or []) if isinstance(item, dict) and bool(item.get("ok"))]
        for branch in branch_results or []:
            if isinstance(branch, dict):
                completed_task_ids.update(str(value).strip() for value in (branch.get("complete_task_ids") or []) if str(value).strip())
                deferred_task_ids.update(str(value).strip() for value in (branch.get("defer_task_ids") or []) if str(value).strip())

        signals: list[str] = []
        if failed_branches:
            signals.append("risk")
        if deferred_task_ids:
            signals.append("defer")
        if completed_task_ids:
            signals.append("complete")
        if len(ok_branches) >= int(policy.get("min_completed_branches") or 2):
            signals.append("stage")

        preview = re.sub(r"\s+", " ", str(execution_result or "")).strip()
        if preview and any(keyword in preview for keyword in ("完成", "失败", "阻塞", "需要", "风险", "阶段")):
            signals.append("result")
        return signals

    def _build_proactive_tell_user_text(
        self,
        workspace: str,
        plan: dict,
        execution_result: str,
        heartbeat_cfg: dict,
        branch_results: list[dict] | None = None,
    ) -> str:
        policy = self._resolve_proactive_talk_policy(heartbeat_cfg)
        if not policy.get("enabled"):
            return ""

        chosen_mode = str((plan or {}).get("chosen_mode") or "").strip().lower()
        if chosen_mode == "status":
            return ""

        state = self._load_heartbeat_tell_user_state(workspace)
        now_epoch = time.time()
        try:
            last_epoch = float(state.get("last_sent_epoch") or 0.0)
        except Exception:
            last_epoch = 0.0
        min_interval = int(policy.get("min_interval_seconds") or 1800)
        if last_epoch > 0 and (now_epoch - last_epoch) < min_interval:
            return ""

        min_heartbeat_runs = int(policy.get("min_heartbeat_runs_since_last") or 0)
        if min_heartbeat_runs > 0 and self._count_heartbeat_snapshots_since_epoch(workspace, last_epoch) < min_heartbeat_runs:
            return ""

        signals = self._collect_heartbeat_share_signals(plan, execution_result, branch_results, policy)
        if not signals:
            return ""

        source = str(execution_result or "").strip() or str((plan or {}).get("user_message") or "").strip()
        if not source:
            return ""
        if "心跳正常" in source and len(source) < 40:
            return ""

        preview = self._human_preview_text(source, limit=int(policy.get("max_chars") or 220))
        if not preview:
            return ""
        if "risk" in signals:
            return f"想先跟你同步一个风险/卡点：{preview}"
        if "complete" in signals or "stage" in signals:
            return f"阶段性同步一下：{preview}"
        return f"想跟你同步一下：{preview}"

    def _heartbeat_long_tasks_mirror_path(self, workspace: str) -> Path:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return local_dir / HEARTBEAT_LONG_TASKS_MIRROR_FILE

    def _heartbeat_tasks_md_path(self, workspace: str) -> Path:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        return local_dir / HEARTBEAT_TASKS_MD_FILE

    def _load_heartbeat_tasks_md(self, workspace: str) -> str:
        path = self._heartbeat_tasks_md_path(workspace)
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

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
        path = self._heartbeat_tasks_md_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
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
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _normalize_heartbeat_upgrade_request(self, payload: dict | None) -> dict:
        data = dict(payload or {})
        action = str(data.get("action") or "execute_prompt").strip() or "execute_prompt"
        execute_prompt = str(data.get("execute_prompt") or "").strip()
        requires_restart = bool(data.get("requires_restart"))
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
                "requires_restart": True,
            }
        )

    def _format_heartbeat_upgrade_request_message(self, request: dict) -> str:
        request_id = str(request.get("request_id") or "").strip()
        action = str(request.get("action") or "execute_prompt").strip() or "execute_prompt"
        reason = str(request.get("reason") or "").strip()
        summary = str(request.get("summary") or reason or "").strip()
        execute_prompt = str(request.get("execute_prompt") or "").strip()
        lines = [
            "**心跳升级申请，等待用户批准**",
            "",
            f"申请ID：`{request_id}`",
            f"类型：{'重启主进程' if action == 'restart' else '执行升级方案'}",
        ]
        if reason:
            lines.append(f"原因：{reason}")
        if summary:
            lines.append(f"摘要：{summary}")
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
                return {
                    "decision": "approve-execute",
                    "request": approved,
                    "execute_prompt": (
                        f"【用户已批准心跳升级申请 {request_id}】\n"
                        f"申请原因：{str(approved.get('reason') or '').strip()}\n"
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
        if self._legacy_heartbeat_markdown_mirrors_enabled():
            self._heartbeat_memory_mirror_path(workspace).write_text(self._render_heartbeat_memory_markdown(payload), encoding="utf-8")

    def _load_heartbeat_long_tasks(self, workspace: str) -> dict:
        return self._load_json_store(self._heartbeat_long_tasks_path(workspace), self._default_heartbeat_long_tasks)

    def _save_heartbeat_long_tasks(self, workspace: str, payload: dict) -> None:
        self._save_json_store(self._heartbeat_long_tasks_path(workspace), payload)
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

        lines: list[str] = []
        for item in (short_items or []) + (long_items or []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("detail") or "待办").strip()[:80]
            detail = str(item.get("detail") or item.get("title") or "").strip()[:200]
            schedule = ""
            if item.get("schedule_type") and item.get("schedule_value"):
                schedule = f" [{item.get('schedule_type')} {item.get('schedule_value')}]"
            lines.append(f"- {title}{schedule}" + (f": {detail}" if detail and detail != title else ""))
        if lines:
            self._append_to_heartbeat_tasks_md(workspace, "## 来自对话\n" + "\n".join(lines))

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

    def _render_heartbeat_local_memory_snippet(self, workspace: str) -> str:
        _, _, local_dir = self._ensure_memory_dirs(workspace)
        payload = self._load_local_memory_index(local_dir)
        entries = [item for item in payload.get("entries") or [] if isinstance(item, dict)]
        entries.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        blocks: list[str] = []
        remaining = 2400
        profile_text = self._load_current_user_profile_excerpt(workspace, max_chars=600)
        if profile_text:
            profile_block = "- 当前用户画像\n  说明: 当前交互对象的个性化偏好、协作风格与关系约定不再写死在 core soul/role；如需个性化，请优先参考该画像。\n  摘录: " + profile_text.replace("\n", " ")[:360]
            blocks.append(profile_block)
            remaining -= len(profile_block) + 2
        for item in entries[:8]:
            title = str(item.get("title") or "长期记忆").strip()
            current = str(item.get("current_conclusion") or item.get("summary") or "").strip()
            history = item.get("history_evolution") if isinstance(item.get("history_evolution"), list) else []
            scenarios = item.get("applicable_scenarios") if isinstance(item.get("applicable_scenarios"), list) else []
            block = (
                f"- {title}\n"
                f"  当前结论: {current[:140] or '(空)'}\n"
                f"  适用情景: {' / '.join([str(x) for x in scenarios if str(x).strip()][:3]) or '(空)'}\n"
                f"  历史演化: {str(history[0])[:140] if history else '(空)'}"
            )
            if len(block) > remaining:
                block = block[: max(0, remaining - 1)].rstrip() + "…"
            if not block.strip():
                break
            blocks.append(block)
            remaining -= len(block) + 2
            if remaining <= 120:
                break
        return "\n\n".join(blocks).strip()

    def _render_available_skills_prompt(self, workspace: str) -> str:
        return render_skill_catalog_for_prompt(workspace, max_chars=1500)

    def _build_heartbeat_planning_prompt(self, cfg: dict, heartbeat_cfg: dict, workspace: str) -> str:
        return self._heartbeat_orchestrator.build_planning_prompt(cfg, heartbeat_cfg, workspace)

    def _default_heartbeat_plan(self, workspace: str) -> dict:
        return self._heartbeat_orchestrator.default_plan(workspace)

    def _planner_fallback_status_plan(self) -> dict:
        return self._heartbeat_orchestrator.planner_fallback_status_plan()

    def _plan_heartbeat_action(self, cfg: dict, heartbeat_cfg: dict, workspace: str, timeout: int, model: str, planner_timeout: int | None = None) -> dict:
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
        if elapsed >= LONG_MAINTENANCE_MIN_INTERVAL_SECONDS:
            return False, status
        enriched = dict(status)
        enriched["remaining_seconds"] = int(LONG_MAINTENANCE_MIN_INTERVAL_SECONDS - elapsed)
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
        if len(files) <= LOCAL_L1_MAX_FILES:
            return
        for p in files[LOCAL_L1_MAX_FILES:]:
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
        if len(summary) > LOCAL_L2_DETAIL_TRIGGER_CHARS:
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
            summary_text = summary.strip()[:LOCAL_L2_SUMMARY_PREVIEW_CHARS].rstrip() + "…"
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
        if not target.exists() and len(files) >= LOCAL_L1_MAX_FILES:
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
        recent_window = max(TALK_RECENT_MAX_ITEMS, BEAT_RECENT_MAX_ITEMS)
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
            sections.append("【对话短期记忆】\n" + "\n".join(talk_lines[-10:]))
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
            token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            token_resp = requests.post(token_url, json={"app_id": app_id, "app_secret": app_secret}, timeout=12)
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
                resp = requests.post(msg_url, headers=headers, json=body, timeout=15)
                data = resp.json()
                if data.get("code") == 0:
                    sent = True
                else:
                    post_content = self._markdown_to_feishu_post(plain)
                    body = {"receive_id": target_id, "msg_type": "post", "content": json.dumps(post_content, ensure_ascii=False)}
                    resp = requests.post(msg_url, headers=headers, json=body, timeout=15)
                    data = resp.json()
                    if data.get("code") == 0:
                        sent = True
            if not sent:
                body = {"receive_id": target_id, "msg_type": "text", "content": json.dumps({"text": plain or "(空)"}, ensure_ascii=False)}
                resp = requests.post(msg_url, headers=headers, json=body, timeout=15)
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
    m._write_heartbeat_watchdog_state(workspace, state="running", heartbeat_pid=int(os.getpid()), note="heartbeat sidecar started")
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
    agent_cmd = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "cursor-agent", "versions", "dist-package", "cursor-agent.cmd",
    )
    if not os.path.isfile(agent_cmd):
        return f"错误：未找到 Cursor CLI（管家bot 依赖），请检查路径 {agent_cmd}", False
    args = [
        agent_cmd, "-p", "--force", "--trust", "--approve-mcps",
        "--model", model or "auto", "--output-format", "json",
        "--workspace", workspace,
    ]
    started = time.perf_counter()
    try:
        print(
            f"[heartbeat-model] start | model={model or 'auto'} | timeout={timeout}s | workspace={workspace}",
            flush=True,
        )
        result = subprocess.run(
            args,
            input=prompt or "",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=workspace,
            env=build_cursor_cli_env(cfg),
        )
        duration = time.perf_counter() - started
        out = ""
        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout.strip())
                out = (data.get("result") or "").strip()
            except Exception:
                pass
        if not out and result.stderr:
            out = result.stderr.strip()
        print(
            f"[heartbeat-model] done | exit={result.returncode} | duration={duration:.1f}s | out_len={len(out)}",
            flush=True,
        )
        if out and result.returncode == 0:
            return out, True
        return out or f"管家bot 执行失败 (exit={result.returncode})", False
    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - started
        print(
            f"[heartbeat-model] timeout | model={model or 'auto'} | timeout={timeout}s | duration={duration:.1f}s",
            flush=True,
        )
        return "执行超时", False
    except Exception as e:
        duration = time.perf_counter() - started
        print(
            f"[heartbeat-model] exception | model={model or 'auto'} | duration={duration:.1f}s | error={e}",
            flush=True,
        )
        return f"管家bot 执行异常: {e}", False
