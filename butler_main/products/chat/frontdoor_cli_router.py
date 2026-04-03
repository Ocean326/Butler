from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from agents_os.contracts import Invocation
from butler_main.agents_os.execution import cli_runner

from .config_runtime import get_config
from .feature_switches import chat_frontdoor_tasks_enabled
from .router_plan import (
    RouterCompilePlan,
    canonical_frontdoor_action,
    canonical_route,
    canonical_runtime_lane,
    resolve_router_compile_plan,
    runtime_lane_defaults,
)
from .routing import ChatRouter, RouteDecision
from .session_modes import canonical_main_mode, canonical_project_phase


_TRUE_VALUES = {"1", "true", "yes", "on"}
_DEFAULT_GOVERNANCE = {
    "eligible_turn_count": 0,
    "last_review_turn_count": 0,
    "last_review_at": "",
    "last_review_summary": "",
    "prompt_appendix": "",
}
_NEGATIVE_FEEDBACK_HINTS = (
    "不是这个意思",
    "不对",
    "答非所问",
    "太慢",
    "卡住",
    "失败",
    "报错",
    "别用",
    "不要用",
    "不要这样",
    "别这样",
    "没让你",
    "不要协商",
)
_POSITIVE_FEEDBACK_HINTS = (
    "可以",
    "对",
    "继续",
    "很好",
    "不错",
    "靠谱",
    "就是这样",
)
_JSON_RE = re.compile(r"\{[\s\S]*\}")
_STATUS_QUERY_HINTS = (
    "任务进度",
    "任务进展",
    "后台任务进度",
    "后台任务进展",
    "progress",
    "status",
    "进度",
    "进展",
    "状态",
    "做到哪",
    "到哪了",
    "怎么样了",
)


@dataclass(slots=True, frozen=True)
class FrontDoorRouterCompileResult:
    route_decision: RouteDecision
    compile_plan: RouterCompilePlan
    intake_decision: dict[str, Any]
    router_source: str
    review_applied: bool = False


class FrontDoorCliRouter:
    def __init__(self, *, chat_router: ChatRouter | None = None) -> None:
        self._chat_router = chat_router or ChatRouter()

    def compile(
        self,
        *,
        invocation: Invocation,
        workspace: str,
        mode_state: Mapping[str, Any] | None,
        explicit_main_mode: str,
        explicit_project_phase: str,
        explicit_override_source: str,
        session_selection,
        intake_decision: Mapping[str, Any] | None,
        legacy_route_decision: RouteDecision,
        explicit_frontdoor_mode: str = "",
    ) -> FrontDoorRouterCompileResult:
        normalized_intake = dict(intake_decision or {})
        legacy_frontdoor_action = self._legacy_frontdoor_action(
            user_text=str(invocation.user_text or ""),
            intake_decision=normalized_intake,
        )
        explicit_runtime_override = self._normalize_runtime_override(
            (invocation.metadata or {}).get("runtime_request_override")
        )
        legacy_plan = resolve_router_compile_plan(
            invocation.user_text,
            mode_state=mode_state,
            explicit_main_mode=explicit_main_mode,
            explicit_project_phase=explicit_project_phase,
            explicit_override_source=explicit_override_source,
            runtime_cli=str(explicit_runtime_override.get("cli") or "").strip(),
            runtime_model=str(explicit_runtime_override.get("model") or "").strip(),
            runtime_profile=str(explicit_runtime_override.get("profile") or "").strip(),
            runtime_extra_args=explicit_runtime_override.get("extra_args") or (),
            router_session_action=str(getattr(session_selection, "action", "") or "continue_current"),
            router_session_confidence=str(getattr(session_selection, "confidence", "") or "medium"),
            router_session_reason_flags=str(
                getattr(session_selection, "reason_flags_text", lambda: "")() or ""
            ).strip(),
            chat_session_id=str(getattr(session_selection, "chat_session_id", "") or "").strip(),
            route=str(legacy_route_decision.route or "chat"),
            frontdoor_action=legacy_frontdoor_action,
            router_source="legacy",
            router_reason=str(legacy_route_decision.reason or "").strip(),
            router_confidence="medium",
            request_intake_mode=str(normalized_intake.get("mode") or "").strip(),
            should_discuss_mode_first=bool(normalized_intake.get("should_discuss_mode_first")),
            external_execution_risk=bool(normalized_intake.get("external_execution_risk")),
        )
        decision_payload = self._call_router_model(
            invocation=invocation,
            workspace=workspace,
            legacy_route_decision=legacy_route_decision,
            legacy_plan=legacy_plan,
            intake_decision=normalized_intake,
            explicit_runtime_override=explicit_runtime_override,
        )
        merged = self._merge_model_decision(
            invocation=invocation,
            mode_state=mode_state,
            explicit_main_mode=explicit_main_mode,
            explicit_project_phase=explicit_project_phase,
            explicit_override_source=explicit_override_source,
            session_selection=session_selection,
            intake_decision=normalized_intake,
            legacy_route_decision=legacy_route_decision,
            legacy_plan=legacy_plan,
            model_decision=decision_payload,
            explicit_frontdoor_mode=explicit_frontdoor_mode,
            explicit_runtime_override=explicit_runtime_override,
        )
        compile_plan = merged.compile_plan
        updated_intake = {
            **normalized_intake,
            "frontdoor_action": compile_plan.frontdoor_action,
            "mode": compile_plan.request_intake_mode or str(normalized_intake.get("mode") or "").strip(),
            "should_discuss_mode_first": bool(compile_plan.should_discuss_mode_first),
            "external_execution_risk": bool(compile_plan.external_execution_risk),
        }
        return FrontDoorRouterCompileResult(
            route_decision=merged.route_decision,
            compile_plan=compile_plan,
            intake_decision=updated_intake,
            router_source=compile_plan.router_source,
        )

    def record_outcome(
        self,
        *,
        workspace: str,
        compile_plan: RouterCompilePlan,
        invocation: Invocation,
        assistant_text: str,
        result_metadata: Mapping[str, Any] | None = None,
    ) -> bool:
        if not workspace:
            return False
        state = self._load_governance_state(workspace)
        state["eligible_turn_count"] = int(state.get("eligible_turn_count") or 0) + 1
        entry = {
            "timestamp": _utc_now_text(),
            "user_text": str(invocation.user_text or "").strip(),
            "assistant_text": str(assistant_text or "").strip(),
            "route": compile_plan.route,
            "frontdoor_action": compile_plan.frontdoor_action,
            "main_mode": compile_plan.main_mode,
            "project_phase": compile_plan.project_phase,
            "runtime_lane": compile_plan.runtime_lane,
            "runtime_cli": compile_plan.runtime_cli,
            "runtime_model": compile_plan.runtime_model,
            "router_source": compile_plan.router_source,
            "router_reason": compile_plan.router_reason,
            "feedback_signal": self._feedback_signal(str(invocation.user_text or "")),
            "hard_failure": self._hard_failure_signal(result_metadata),
        }
        self._append_journal_entry(workspace, entry)
        review_applied = False
        if self._review_enabled() and int(state["eligible_turn_count"]) % 50 == 0:
            review_applied = self._run_periodic_review(workspace=workspace, state=state)
        self._save_governance_state(workspace, state)
        return review_applied

    def _merge_model_decision(
        self,
        *,
        invocation: Invocation,
        mode_state: Mapping[str, Any] | None,
        explicit_main_mode: str,
        explicit_project_phase: str,
        explicit_override_source: str,
        session_selection,
        intake_decision: Mapping[str, Any],
        legacy_route_decision: RouteDecision,
        legacy_plan: RouterCompilePlan,
        model_decision: Mapping[str, Any] | None,
        explicit_frontdoor_mode: str,
        explicit_runtime_override: Mapping[str, Any],
    ) -> FrontDoorRouterCompileResult:
        decision = dict(model_decision or {})
        router_source = "legacy"
        router_reason = str(legacy_plan.router_reason or legacy_route_decision.reason or "").strip()
        router_confidence = "medium"
        selected_main_mode = canonical_main_mode(decision.get("main_mode") or legacy_plan.main_mode)
        selected_project_phase = canonical_project_phase(decision.get("project_phase") or legacy_plan.project_phase)
        selected_session_action = str(
            decision.get("session_action") or getattr(session_selection, "action", "") or legacy_plan.router_session_action
        ).strip() or "continue_current"
        frontdoor_action = canonical_frontdoor_action(decision.get("frontdoor_action") or legacy_plan.frontdoor_action)
        route = canonical_route(decision.get("route") or legacy_plan.route)
        runtime_lane = canonical_runtime_lane(decision.get("runtime_lane") or legacy_plan.runtime_lane)
        if decision:
            router_source = "model_router"
            router_reason = str(decision.get("reason") or decision.get("router_reason") or router_reason).strip() or router_reason
            router_confidence = str(decision.get("confidence") or "medium").strip() or "medium"
        if frontdoor_action == "mission_ingress":
            route = "mission_ingress"
        elif route == "mission_ingress":
            frontdoor_action = "mission_ingress"
        if not chat_frontdoor_tasks_enabled() and frontdoor_action in {"background_entry", "mission_ingress"}:
            frontdoor_action = "normal_chat"
            route = "chat"
        if explicit_frontdoor_mode == "status":
            frontdoor_action = "query_status"
            route = "chat"
        elif explicit_frontdoor_mode == "govern":
            frontdoor_action = "govern"
            route = "chat"
        runtime_cli = str(explicit_runtime_override.get("cli") or "").strip()
        runtime_model = str(explicit_runtime_override.get("model") or "").strip()
        runtime_profile = str(explicit_runtime_override.get("profile") or "").strip()
        runtime_extra_args = tuple(
            str(item).strip() for item in (explicit_runtime_override.get("extra_args") or ()) if str(item).strip()
        )
        if not runtime_cli:
            lane_defaults = runtime_lane_defaults(runtime_lane)
            runtime_cli = str(lane_defaults["cli"] or "")
            runtime_model = runtime_model or str(lane_defaults["model"] or "")
            runtime_profile = runtime_profile or str(lane_defaults["profile"] or "")
            runtime_extra_args = runtime_extra_args or tuple(lane_defaults["extra_args"] or ())
        compile_plan = resolve_router_compile_plan(
            invocation.user_text,
            mode_state=mode_state,
            explicit_main_mode=selected_main_mode,
            explicit_project_phase=selected_project_phase,
            explicit_override_source="model_router" if router_source == "model_router" else explicit_override_source,
            runtime_cli=runtime_cli,
            runtime_model=runtime_model,
            runtime_profile=runtime_profile,
            runtime_extra_args=runtime_extra_args,
            router_session_action=selected_session_action,
            router_session_confidence=str(getattr(session_selection, "confidence", "") or "medium"),
            router_session_reason_flags=str(getattr(session_selection, "reason_flags_text", lambda: "")() or "").strip(),
            chat_session_id=str(getattr(session_selection, "chat_session_id", "") or "").strip(),
            route=route,
            frontdoor_action=frontdoor_action,
            router_source=router_source,
            router_reason=router_reason,
            router_confidence=router_confidence,
            request_intake_mode=str(decision.get("request_intake_mode") or intake_decision.get("mode") or "").strip(),
            should_discuss_mode_first=bool(
                decision.get("should_discuss_mode_first", intake_decision.get("should_discuss_mode_first"))
            ),
            external_execution_risk=bool(
                decision.get("external_execution_risk", intake_decision.get("external_execution_risk"))
            ),
        )
        route_decision = self._chat_router.make_route_decision(
            invocation,
            compile_plan.route,
            reason=f"{compile_plan.router_source}:{compile_plan.router_reason}".strip(":"),
            metadata_extra={
                "frontdoor_action": compile_plan.frontdoor_action,
                "router_confidence": compile_plan.router_confidence,
            },
        )
        return FrontDoorRouterCompileResult(
            route_decision=route_decision,
            compile_plan=compile_plan,
            intake_decision=dict(intake_decision or {}),
            router_source=compile_plan.router_source,
        )

    def _call_router_model(
        self,
        *,
        invocation: Invocation,
        workspace: str,
        legacy_route_decision: RouteDecision,
        legacy_plan: RouterCompilePlan,
        intake_decision: Mapping[str, Any],
        explicit_runtime_override: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if not self._router_model_enabled():
            return None
        prompt = self._build_router_prompt(
            invocation=invocation,
            legacy_route_decision=legacy_route_decision,
            legacy_plan=legacy_plan,
            intake_decision=intake_decision,
            explicit_runtime_override=explicit_runtime_override,
            workspace=workspace,
        )
        payload = self._run_router_prompt(prompt, workspace=workspace)
        if not payload:
            return None
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _build_router_prompt(
        self,
        *,
        invocation: Invocation,
        legacy_route_decision: RouteDecision,
        legacy_plan: RouterCompilePlan,
        intake_decision: Mapping[str, Any],
        explicit_runtime_override: Mapping[str, Any],
        workspace: str,
    ) -> str:
        governance = self._load_governance_state(workspace)
        appendix = str(governance.get("prompt_appendix") or "").strip()
        lines = [
            "你是 Butler chat 前门 router。只输出一个 JSON 对象，不要解释。",
            "目标：一次决定 frontdoor_action、main_mode、project_phase、session_action、runtime_lane。",
            "runtime_lane 规则：cursor_fast=日常/简单问题，cursor ask + composer-2-fast；cursor_exec=一般执行/代码修改/排查，cursor + composer-2；codex_deep=复杂/长程/高风险/后台，codex + gpt-5.4。",
            "默认偏向 cursor_fast；只有明显复杂、长程、后台、高风险、外部系统执行时才升级到 codex_deep。",
            "session_action 只有在明显换题时才用 reopen_new_session，否则 continue_current。",
            '可选 frontdoor_action：normal_chat/query_status/govern/background_entry/mission_ingress。',
            '可选 main_mode：chat/share/brainstorm/project/background；project_phase 只能是 ""/plan/imp/review。',
            '可选 runtime_lane：cursor_fast/cursor_exec/codex_deep。',
        ]
        if appendix:
            lines.append(f"补充策略：{appendix}")
        lines.extend(
            [
                "上下文：",
                json.dumps(
                    {
                        "user_text": str(invocation.user_text or "").strip(),
                        "channel": str(invocation.channel or "").strip(),
                        "legacy_route": legacy_route_decision.route,
                        "legacy_frontdoor_action": legacy_plan.frontdoor_action,
                        "legacy_main_mode": legacy_plan.main_mode,
                        "legacy_project_phase": legacy_plan.project_phase,
                        "legacy_session_action": legacy_plan.router_session_action,
                        "legacy_runtime_lane": legacy_plan.runtime_lane,
                        "intake": {
                            "mode": str(intake_decision.get("mode") or "").strip(),
                            "frontdoor_action": str(intake_decision.get("frontdoor_action") or "").strip(),
                            "should_discuss_mode_first": bool(intake_decision.get("should_discuss_mode_first")),
                            "external_execution_risk": bool(intake_decision.get("external_execution_risk")),
                            "estimated_scale": str(intake_decision.get("estimated_scale") or "").strip(),
                        },
                        "explicit_runtime_override": dict(explicit_runtime_override or {}),
                    },
                    ensure_ascii=False,
                ),
                '输出 JSON：{"route":"chat|mission_ingress","frontdoor_action":"...","main_mode":"...","project_phase":"","session_action":"continue_current|reopen_new_session","runtime_lane":"cursor_fast|cursor_exec|codex_deep","reason":"<=80字","confidence":"low|medium|high"}',
            ]
        )
        return "\n".join(lines)

    def _run_router_prompt(self, prompt: str, *, workspace: str) -> str:
        cfg = get_config()
        receipt = cli_runner.run_prompt_receipt(
            prompt,
            workspace or str(cfg.get("workspace_root") or "."),
            timeout=45,
            cfg=cfg,
            runtime_request={
                "cli": "cursor",
                "model": "composer-2-fast",
                "extra_args": ["--mode", "ask"],
                "_disable_runtime_fallback": True,
            },
            stream=False,
        )
        output = str(getattr(receipt, "summary", "") or "").strip()
        bundle = getattr(receipt, "output_bundle", None)
        if bundle is not None:
            for block in list(getattr(bundle, "text_blocks", []) or []):
                text = str(getattr(block, "text", "") or "").strip()
                if text:
                    output = text
                    break
        match = _JSON_RE.search(output)
        return match.group(0) if match else ""

    def _router_model_enabled(self) -> bool:
        env_value = os.getenv("BUTLER_CHAT_FRONTDOOR_MODEL_ROUTER_ENABLED")
        if env_value is not None and str(env_value).strip():
            return str(env_value).strip().lower() in _TRUE_VALUES
        if os.getenv("PYTEST_CURRENT_TEST"):
            return False
        features = (get_config() or {}).get("features") or {}
        if isinstance(features, Mapping) and "chat_frontdoor_model_router_enabled" in features:
            return bool(features.get("chat_frontdoor_model_router_enabled"))
        return True

    def _review_enabled(self) -> bool:
        env_value = os.getenv("BUTLER_CHAT_FRONTDOOR_ROUTER_REVIEW_ENABLED")
        if env_value is not None and str(env_value).strip():
            return str(env_value).strip().lower() in _TRUE_VALUES
        if os.getenv("PYTEST_CURRENT_TEST"):
            return False
        return True

    def _run_periodic_review(self, *, workspace: str, state: dict[str, Any]) -> bool:
        if not self._router_model_enabled():
            return False
        journal = self._load_recent_journal_entries(workspace, limit=24)
        if not journal:
            return False
        prompt = "\n".join(
            [
                "你在复盘 Butler chat router 最近若干轮的 CLI 路由是否合理。",
                "重点只看三件事：是否误把简单问题升到重 CLI、是否把需要执行/长程的任务放得太轻、用户是否表达明显不满或出现硬失败。",
                "根据输入生成一个极短 JSON，只返回：",
                '{"prompt_appendix":"<=180字，可为空","summary":"<=120字","confidence":"low|medium|high"}',
                json.dumps({"recent_turns": journal}, ensure_ascii=False),
            ]
        )
        payload = self._run_router_prompt(prompt, workspace=workspace)
        if not payload:
            return False
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return False
        if not isinstance(parsed, dict):
            return False
        appendix = str(parsed.get("prompt_appendix") or "").strip()[:180]
        summary = str(parsed.get("summary") or "").strip()[:120]
        state["prompt_appendix"] = appendix
        state["last_review_summary"] = summary
        state["last_review_turn_count"] = int(state.get("eligible_turn_count") or 0)
        state["last_review_at"] = _utc_now_text()
        return True

    def _governance_dir(self, workspace: str) -> Path:
        root = Path(workspace or ".").resolve()
        path = root / "butler_main" / "chat" / "data" / "hot" / "frontdoor_cli_router"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _governance_state_path(self, workspace: str) -> Path:
        return self._governance_dir(workspace) / "governance_state.json"

    def _review_journal_path(self, workspace: str) -> Path:
        return self._governance_dir(workspace) / "review_journal.jsonl"

    def _load_governance_state(self, workspace: str) -> dict[str, Any]:
        path = self._governance_state_path(workspace)
        if not path.exists():
            return dict(_DEFAULT_GOVERNANCE)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(_DEFAULT_GOVERNANCE)
        if not isinstance(payload, dict):
            return dict(_DEFAULT_GOVERNANCE)
        return {**_DEFAULT_GOVERNANCE, **payload}

    def _save_governance_state(self, workspace: str, state: Mapping[str, Any]) -> None:
        path = self._governance_state_path(workspace)
        path.write_text(json.dumps(dict(state or {}), ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_journal_entry(self, workspace: str, entry: Mapping[str, Any]) -> None:
        path = self._review_journal_path(workspace)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(entry or {}), ensure_ascii=False) + "\n")

    def _load_recent_journal_entries(self, workspace: str, *, limit: int) -> list[dict[str, Any]]:
        path = self._review_journal_path(workspace)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    rows.append(dict(payload))
        except Exception:
            return []
        return rows[-max(1, int(limit or 0)) :]

    @staticmethod
    def _normalize_runtime_override(value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {}
        payload = dict(value)
        normalized: dict[str, Any] = {}
        for key in ("cli", "model", "profile", "speed"):
            text = str(payload.get(key) or "").strip()
            if text:
                normalized[key] = text
        extra_args = [str(item).strip() for item in payload.get("extra_args") or [] if str(item).strip()]
        if extra_args:
            normalized["extra_args"] = extra_args
        return normalized

    @staticmethod
    def _feedback_signal(user_text: str) -> str:
        lowered = str(user_text or "").lower()
        if any(token in lowered for token in _NEGATIVE_FEEDBACK_HINTS):
            return "negative"
        if any(token in lowered for token in _POSITIVE_FEEDBACK_HINTS):
            return "positive"
        return "neutral"

    @staticmethod
    def _hard_failure_signal(result_metadata: Mapping[str, Any] | None) -> bool:
        metadata = dict(result_metadata or {})
        failure_class = str(metadata.get("failure_class") or "").strip()
        if failure_class:
            return True
        execution_metadata = dict(metadata.get("execution_metadata") or {})
        if str(execution_metadata.get("failure_class") or "").strip():
            return True
        return False

    @staticmethod
    def _legacy_frontdoor_action(*, user_text: str, intake_decision: Mapping[str, Any]) -> str:
        lowered = str(user_text or "").lower()
        intake_action = str(intake_decision.get("frontdoor_action") or "").strip().lower()
        if any(token in lowered for token in _STATUS_QUERY_HINTS):
            return "query_status"
        if intake_action in {"query_status", "status"}:
            return "query_status"
        if intake_action in {"discuss_backend_entry", "choose_execution_mode", "background_entry"}:
            return "background_entry"
        if bool(intake_decision.get("explicit_backend_request")) or bool(intake_decision.get("should_discuss_mode_first")):
            return "background_entry"
        return "normal_chat"


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


__all__ = ["FrontDoorCliRouter", "FrontDoorRouterCompileResult"]
