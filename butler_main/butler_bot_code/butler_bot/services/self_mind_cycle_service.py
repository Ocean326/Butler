from __future__ import annotations

import time
import uuid
from datetime import datetime


class SelfMindCycleService:
    def __init__(self, manager) -> None:
        self._manager = manager

    def execute_reflect(self, workspace: str, proposal: dict) -> bool:
        manager = self._manager
        if str(proposal.get("action_type") or "") != "reflect":
            return False
        manager._clear_pending_self_lane_item(workspace)
        manager._append_self_mind_log(
            workspace,
            "self_mind_reflect_completed",
            {
                "candidate": str(proposal.get("candidate") or proposal.get("focus") or "")[:220],
                "self_mind_note": str(proposal.get("self_note") or proposal.get("reason") or "")[:500],
                "share_type": "reflect",
            },
        )
        manager._route_self_mind_domain_signal(workspace, proposal, self_mind_note=str(proposal.get("self_note") or ""))
        manager._refresh_self_mind_context(
            workspace,
            None,
            last_event="self_mind_reflect_completed",
            self_mind_note=str(proposal.get("self_note") or proposal.get("reason") or ""),
        )
        return True

    def execute_direct_talk(self, workspace: str, proposal: dict) -> bool:
        manager = self._manager
        if not manager._self_mind_direct_talk_enabled():
            manager._append_self_mind_suppression_event(workspace, proposal, "direct-talk-disabled")
            return False
        if str(proposal.get("decision") or "") != "talk":
            return False
        priority = int(proposal.get("priority") or 0)
        min_priority = manager._self_mind_direct_talk_priority_threshold()
        if priority < min_priority:
            manager._append_self_mind_suppression_event(
                workspace,
                proposal,
                "priority-below-threshold",
                priority=priority,
                min_priority=min_priority,
            )
            return False
        state = manager._load_self_mind_state(workspace)
        try:
            last_epoch = float(state.get("last_direct_talk_epoch") or 0.0)
        except Exception:
            last_epoch = 0.0
        min_interval = manager._self_mind_direct_talk_min_interval_seconds()
        if last_epoch > 0 and min_interval > 0 and (time.time() - last_epoch) < min_interval:
            manager._append_self_mind_suppression_event(
                workspace,
                proposal,
                "direct-talk-cooldown",
                min_interval_seconds=min_interval,
                cooldown_remaining_seconds=max(0, int(min_interval - (time.time() - last_epoch))),
            )
            return False
        recent_talk_defer_seconds = manager._self_mind_direct_talk_recent_talk_defer_seconds()
        if manager._talk_window_is_active(workspace, {"defer_if_recent_talk_seconds": recent_talk_defer_seconds}):
            manager._append_self_mind_suppression_event(
                workspace,
                proposal,
                "talk-window-active",
                defer_if_recent_talk_seconds=recent_talk_defer_seconds,
            )
            return False
        cfg = dict(manager._latest_runtime_cfg or {})
        cfg.update(manager._config_provider() or {})
        talk_receive_id, talk_receive_id_type = manager._self_mind_talk_target(cfg)
        if not talk_receive_id:
            manager._append_self_mind_suppression_event(workspace, proposal, "talk-target-missing")
            return False
        text = manager._strip_lane_marker(str(proposal.get("talk") or proposal.get("candidate") or "").strip(), "talk")
        if not str(text or "").strip():
            manager._append_self_mind_suppression_event(workspace, proposal, "talk-text-empty")
            return False
        sent = manager._send_private_message(
            cfg,
            text[:4000],
            receive_id=talk_receive_id,
            receive_id_type=talk_receive_id_type,
            fallback_to_startup_target=False,
            heartbeat_cfg=manager._self_mind_talk_delivery_override(),
        )
        if not sent:
            manager._append_self_mind_suppression_event(workspace, proposal, "direct-talk-send-failed")
            return False
        manager._append_self_mind_listener_turn(
            workspace,
            "",
            text,
            source="self_mind_direct_talk",
        )
        state["last_direct_talk_epoch"] = time.time()
        state["last_direct_talk_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["last_direct_talk_preview"] = text[:220]
        manager._save_self_mind_state(workspace, state)
        manager._append_heartbeat_tell_user_audit(
            workspace,
            intent={"share_type": "thought_share", "candidate": proposal.get("candidate"), "share_reason": proposal.get("why") or proposal.get("reason")},
            text=text,
            status="sent",
            reason="self-mind-direct-talk",
            receive_id=talk_receive_id,
            receive_id_type=talk_receive_id_type,
        )
        manager._append_self_mind_log(
            workspace,
            "self_mind_direct_talk_sent",
            {
                "candidate": str(proposal.get("candidate") or "")[:220],
                "message_preview": text[:220],
                "share_type": "thought_share",
            },
        )
        manager._clear_pending_self_lane_item(workspace)
        manager._refresh_self_mind_context(
            workspace,
            None,
            last_event="self_mind_direct_talk_sent",
            rendered_text=text,
            self_mind_note=str(proposal.get("self_note") or ""),
        )
        return True

    def remember_pending_item(self, workspace: str, proposal: dict) -> None:
        manager = self._manager
        if not isinstance(proposal, dict):
            return
        candidate = str(proposal.get("candidate") or proposal.get("focus") or "").strip()
        if not candidate:
            return
        state = manager._load_self_mind_state(workspace)
        state["pending_self_lane_item"] = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
            "action_type": str(proposal.get("action_type") or "reflect").strip() or "reflect",
            "priority": int(proposal.get("priority") or 0),
            "focus": str(proposal.get("focus") or "").strip()[:220],
            "candidate": candidate[:260],
            "reason": str(proposal.get("reason") or proposal.get("self_note") or "").strip()[:320],
        }
        manager._save_self_mind_state(workspace, state)

    def clear_pending_item(self, workspace: str) -> None:
        manager = self._manager
        state = manager._load_self_mind_state(workspace)
        if "pending_self_lane_item" not in state:
            return
        state.pop("pending_self_lane_item", None)
        manager._save_self_mind_state(workspace, state)

    def run_cycle_once(self, workspace: str, timeout: int | None = None, model: str | None = None) -> dict:
        manager = self._manager
        if not manager._self_mind_enabled():
            return {}
        with manager._self_mind_lock:
            prompt = manager._build_self_mind_cycle_prompt(workspace)
            effective_timeout = max(20, int(timeout or manager._self_mind_cycle_timeout_seconds()))
            effective_model = str(model or manager._self_mind_cycle_model() or "auto").strip() or "auto"
            try:
                with manager.runtime_request_scope({"cli": manager._self_mind_cycle_cli(), "model": effective_model}):
                    out, ok = manager._run_model_fn(prompt, workspace, effective_timeout, effective_model)
            except Exception as exc:
                manager._append_self_mind_log(workspace, "self_mind_cycle_failed", {"reason": str(exc)[:220]})
                return {}
            data = manager._extract_json_block(out if ok else "") or {}
            proposal = manager._normalize_self_mind_cycle_output(data)
            cycle_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
            proposal["cycle_id"] = cycle_id
            state = manager._load_self_mind_state(workspace)
            focus_text = str(proposal.get("focus") or proposal.get("candidate") or "")
            focus_key = manager._self_mind_focus_key(focus_text)
            last_focus_key = manager._self_mind_focus_key(str(state.get("last_focus_key") or ""))
            try:
                same_focus_streak = int(state.get("same_focus_streak") or 0)
            except Exception:
                same_focus_streak = 0
            if focus_key and focus_key == last_focus_key:
                same_focus_streak += 1
            else:
                same_focus_streak = 1 if focus_key else 0
            proposal["same_focus_streak"] = same_focus_streak

            if same_focus_streak >= 3 and proposal.get("decision") == "hold":
                proposal["decision"] = "agent"
                proposal["action_channel"] = "agent"
                proposal["action_type"] = "agent_task"
                proposal["priority"] = max(int(proposal.get("priority") or 0), manager._self_mind_heartbeat_handoff_priority_threshold())
                if not str(proposal.get("done_when") or proposal.get("acceptance_criteria") or "").strip():
                    proposal["done_when"] = "至少在 self_mind agent_space 留下一条可执行结果、证据或下一步。"
                    proposal["acceptance_criteria"] = proposal["done_when"]
                if not str(proposal.get("agent_task") or "").strip():
                    candidate = str(proposal.get("candidate") or proposal.get("focus") or "").strip()[:220]
                    proposal["agent_task"] = f"把这个重复焦点转成 self_mind 自己的一条可执行小实验并把结果写进 agent_space：{candidate}。"
                proposal["suppression_reason"] = "same-focus-streak-breakout"
            elif same_focus_streak >= 3 and proposal.get("decision") == "hold":
                candidate_text = str(proposal.get("talk") or proposal.get("candidate") or proposal.get("focus") or "").strip()
                if candidate_text:
                    spoken = manager._strip_lane_marker(candidate_text, "talk")
                    proposal["decision"] = "talk"
                    proposal["action_channel"] = "self"
                    proposal["action_type"] = "talk"
                    proposal["talk"] = f"【talk】{spoken}"
                    proposal["priority"] = max(int(proposal.get("priority") or 0), 35)
                    proposal["suppression_reason"] = "same-focus-talk-breakout"

            if proposal.get("decision") == "heartbeat":
                proposal["decision"] = "agent"
                proposal["action_channel"] = "agent"
                proposal["action_type"] = str(proposal.get("action_type") or "agent_task").strip() or "agent_task"
                proposal["agent_task"] = str(proposal.get("agent_task") or proposal.get("heartbeat") or proposal.get("heartbeat_instruction") or "").strip()
                proposal["heartbeat"] = ""
                proposal["heartbeat_instruction"] = ""

            if not str(
                proposal.get("candidate")
                or proposal.get("focus")
                or proposal.get("reason")
                or proposal.get("talk")
                or proposal.get("agent_task")
                or proposal.get("heartbeat")
                or ""
            ).strip():
                proposal["decision"] = "hold"
                proposal["action_channel"] = "hold"
            state["last_cycle_epoch"] = time.time()
            state["last_cycle_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["last_cycle_id"] = cycle_id
            state["last_focus"] = str(proposal.get("focus") or proposal.get("candidate") or "")[:220]
            state["last_focus_key"] = focus_key
            state["same_focus_streak"] = same_focus_streak
            state["last_action_channel"] = str(proposal.get("decision") or proposal.get("action_channel") or "hold")
            manager._save_self_mind_state(workspace, state)
            manager._append_self_mind_log(
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
                if manager._execute_self_mind_direct_talk(workspace, proposal):
                    manager._clear_pending_self_lane_item(workspace)
                    proposal["status"] = "self-executed"
                    return proposal
                proposal["status"] = "hold"
                proposal["suppression_reason"] = "direct-talk-deferred-or-unavailable"

            elif proposal.get("decision") == "agent":
                proposal["agent_task"] = str(proposal.get("agent_task") or proposal.get("heartbeat") or proposal.get("heartbeat_instruction") or "").strip()
                proposal["done_when"] = str(proposal.get("done_when") or proposal.get("acceptance_criteria") or "").strip()
                if proposal["agent_task"]:
                    manager._remember_pending_self_lane_item(workspace, proposal)
                    proposal["status"] = "agent-pending"
                else:
                    proposal["status"] = "hold"
                    proposal["suppression_reason"] = "agent-task-empty"
            else:
                manager._remember_pending_self_lane_item(workspace, proposal)
            manager._refresh_self_mind_context(
                workspace,
                None,
                last_event="self_mind_cycle",
                self_mind_note=str(proposal.get("self_note") or ""),
            )
            return proposal
