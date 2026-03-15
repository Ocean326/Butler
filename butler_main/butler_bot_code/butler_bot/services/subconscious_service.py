from __future__ import annotations

from datetime import datetime
import uuid


class SubconsciousConsolidationService:
    _LONG_TERM_HINTS = (
        "记住", "以后", "默认", "偏好", "必须", "统一", "固定", "长期", "沿用",
        "约定", "习惯", "风格", "希望", "尽量", "不要", "记下来", "后续",
        "always", "default", "remember", "preference", "must",
    )

    def __init__(self, now_factory=None) -> None:
        self._now_factory = now_factory or datetime.now

    def consolidate_turn(
        self,
        *,
        memory_id: str,
        candidate: dict,
        user_prompt: str,
        assistant_reply: str,
        existing_entries: list[dict] | None = None,
    ) -> dict:
        existing_entries = existing_entries or []
        primary_entry = self._build_primary_entry(memory_id, candidate, user_prompt, assistant_reply)
        companion_entries = self._build_companion_entries(primary_entry)
        primary_entry, implicit_signals = self._maybe_promote_implicit_long_term_candidate(primary_entry, companion_entries, existing_entries)
        trigger_level = self._infer_trigger_level(primary_entry, companion_entries, existing_entries)
        primary_entry["subconscious"] = {
            "trigger_level": trigger_level,
            "companion_count": len(companion_entries),
            "consolidated_at": self._timestamp(),
            "implicit_long_term_signals": implicit_signals,
        }
        return {
            "primary_entry": primary_entry,
            "companion_entries": companion_entries,
            "trigger_level": trigger_level,
        }

    def consolidate_heartbeat_run(
        self,
        *,
        plan: dict,
        branch_results: list[dict],
        execution_result: str,
        existing_entries: list[dict] | None = None,
        max_parallel: int = 1,
    ) -> dict:
        existing_entries = existing_entries or []
        primary_entry = self._build_heartbeat_primary_entry(plan, branch_results, execution_result, max_parallel=max_parallel)
        companion_entries = self._build_heartbeat_companion_entries(primary_entry, plan, branch_results, execution_result)
        trigger_level = self._infer_trigger_level(primary_entry, companion_entries, existing_entries)
        primary_entry["subconscious"] = {
            "trigger_level": trigger_level,
            "companion_count": len(companion_entries),
            "consolidated_at": self._timestamp(),
            "source": "heartbeat",
        }
        return {
            "primary_entry": primary_entry,
            "companion_entries": companion_entries,
            "trigger_level": trigger_level,
        }

    def _build_heartbeat_tell_user_intention(self, plan: dict, branch_results: list[dict], execution_result: str) -> dict:
        candidate = str(plan.get("tell_user_candidate") or plan.get("tell_user") or "").strip()
        reason = str(plan.get("tell_user_reason") or "").strip()
        share_type = str(plan.get("tell_user_type") or "").strip()
        priority = plan.get("tell_user_priority")
        try:
            priority = max(0, min(100, int(priority or 0)))
        except Exception:
            priority = 0

        complete_ids = set(str(value).strip() for value in ((plan.get("updates") or {}).get("complete_task_ids") or []) if str(value).strip())
        defer_ids = set(str(value).strip() for value in (plan.get("deferred_task_ids") or []) if str(value).strip())
        failed_count = 0
        success_count = 0
        for item in branch_results or []:
            if not isinstance(item, dict):
                continue
            if bool(item.get("ok")):
                success_count += 1
            else:
                failed_count += 1
            complete_ids.update(str(value).strip() for value in (item.get("complete_task_ids") or []) if str(value).strip())
            defer_ids.update(str(value).strip() for value in (item.get("defer_task_ids") or []) if str(value).strip())

        if not share_type:
            lowered = str(execution_result or "")
            if failed_count > 0 or defer_ids or any(word in lowered for word in ("风险", "阻塞", "失败", "需要确认")):
                share_type = "risk_share"
            elif complete_ids or success_count >= 2 or any(word in lowered for word in ("完成", "收口", "阶段")):
                share_type = "result_share"
            elif candidate or reason:
                share_type = "thought_share"

        if priority <= 0:
            if share_type == "risk_share":
                priority = 90
            elif share_type == "result_share":
                priority = 70
            elif share_type == "thought_share":
                priority = 55
            elif share_type == "growth_share":
                priority = 65
            elif share_type == "light_chat":
                priority = 35

        if not reason:
            if share_type == "risk_share":
                reason = "本轮出现风险、阻塞或需要确认的点"
            elif share_type == "result_share":
                reason = "本轮形成了值得同步的阶段性成果"
            elif share_type == "thought_share":
                reason = "本轮内在心理活动里留下了下一轮还想继续对用户说的点"
            elif share_type == "growth_share":
                reason = "本轮学会了一个值得告诉用户的新能力或新成长点"
            elif share_type == "light_chat":
                reason = "本轮形成了一个轻量、低压、适合主动找用户聊一下的话头"

        return {
            "candidate": candidate[:220],
            "reason": reason[:220],
            "share_type": share_type[:40],
            "priority": priority,
            "completed_task_count": len(complete_ids),
            "deferred_task_count": len(defer_ids),
            "failed_branch_count": failed_count,
            "successful_branch_count": success_count,
        }

    def normalize_recent_entry(self, entry: dict | None) -> dict:
        raw = dict(entry or {})
        stream = str(raw.get("memory_stream") or "").strip()
        if not stream:
            if str(raw.get("memory_scope") or "").strip() == "beat" or isinstance(raw.get("heartbeat_execution_snapshot"), dict):
                stream = "heartbeat_observation"
            else:
                stream = "talk"
        normalized = {
            "memory_id": str(raw.get("memory_id") or uuid.uuid4()),
            "timestamp": str(raw.get("timestamp") or self._timestamp()),
            "topic": str(raw.get("topic") or "本轮对话").strip()[:40],
            "summary": str(raw.get("summary") or "").strip()[:220],
            "scene_mode": str(raw.get("scene_mode") or "mixed").strip()[:20] or "mixed",
            "memory_scope": str(raw.get("memory_scope") or ("beat" if stream == "heartbeat_observation" else "talk")).strip(),
            "memory_stream": stream,
            "event_type": str(raw.get("event_type") or self._default_event_type(stream)).strip(),
            "raw_user_prompt": str(raw.get("raw_user_prompt") or "").strip()[:1000],
            "status": str(raw.get("status") or "completed").strip() or "completed",
            "next_actions": self._string_list(raw.get("next_actions"), limit=5, item_limit=60),
            "detail_points": self._string_list(raw.get("detail_points"), limit=6, item_limit=160),
            "unresolved_points": self._string_list(raw.get("unresolved_points"), limit=4, item_limit=120),
            "self_mind_cues": self._string_list(raw.get("self_mind_cues"), limit=4, item_limit=160),
            "heartbeat_tasks": [item for item in (raw.get("heartbeat_tasks") or []) if isinstance(item, dict)][:5],
            "heartbeat_long_term_tasks": [item for item in (raw.get("heartbeat_long_term_tasks") or []) if isinstance(item, dict)][:5],
            "long_term_candidate": self._normalize_long_term_candidate(raw.get("long_term_candidate")),
            "salience": self._normalize_float(raw.get("salience"), fallback=0.5),
            "confidence": self._normalize_float(raw.get("confidence"), fallback=0.5),
            "derived_from": self._string_list(raw.get("derived_from"), limit=6, item_limit=80),
            "context_tags": self._string_list(raw.get("context_tags"), limit=8, item_limit=30),
            "mental_notes": self._string_list(raw.get("mental_notes"), limit=4, item_limit=120),
            "relationship_signals": self._string_list(raw.get("relationship_signals"), limit=4, item_limit=120),
            "relation_signal": self._normalize_relation_signal(raw.get("relation_signal")),
            "active_window": str(raw.get("active_window") or "recent").strip() or "recent",
            "subconscious": raw.get("subconscious") if isinstance(raw.get("subconscious"), dict) else {},
        }
        if isinstance(raw.get("heartbeat_execution_snapshot"), dict):
            normalized["heartbeat_execution_snapshot"] = raw.get("heartbeat_execution_snapshot")
        return normalized

    def _build_primary_entry(self, memory_id: str, candidate: dict, user_prompt: str, assistant_reply: str) -> dict:
        raw = dict(candidate or {})
        raw["memory_id"] = memory_id
        raw.setdefault("memory_scope", "talk")
        raw.setdefault("memory_stream", "talk")
        raw.setdefault("event_type", "conversation_turn")
        raw.setdefault("raw_user_prompt", user_prompt)
        raw.setdefault("status", "completed")
        raw.setdefault("salience", 0.6 if str(raw.get("summary") or "").strip() else 0.3)
        raw.setdefault("confidence", 0.7 if str(assistant_reply or "").strip() else 0.5)
        raw.setdefault("active_window", "current")
        raw.setdefault("scene_mode", self._infer_scene_mode(user_prompt, assistant_reply, candidate))
        raw["derived_from"] = [part for part in ["turn", "assistant_reply" if str(assistant_reply or "").strip() else "user_prompt"] if part]
        return self.normalize_recent_entry(raw)

    def _infer_scene_mode(self, user_prompt: str, assistant_reply: str, candidate: dict) -> str:
        raw_mode = str((candidate or {}).get("scene_mode") or "").strip().lower()
        if raw_mode in {"work", "chat", "self_growth", "mixed", "other"}:
            return raw_mode
        text = f"{user_prompt}\n{assistant_reply}\n{candidate or {}}".lower()
        if any(keyword in text for keyword in ("工作", "任务", "实现", "修复", "代码", "测试", "文档", "heartbeat")):
            if any(keyword in text for keyword in ("聊天", "关系", "陪伴", "情绪", "心声")):
                return "mixed"
            return "work"
        if any(keyword in text for keyword in ("聊天", "关系", "陪伴", "情绪", "心声", "歌")):
            return "chat"
        if any(keyword in text for keyword in ("自我", "升级", "进化", "反思", "认知", "soul")):
            return "self_growth"
        return "mixed"

    def _build_heartbeat_primary_entry(self, plan: dict, branch_results: list[dict], execution_result: str, max_parallel: int) -> dict:
        parallel_count = len([item for item in (branch_results or []) if str(item.get("run_mode") or "") == "parallel"])
        serial_count = len([item for item in (branch_results or []) if str(item.get("run_mode") or "") != "parallel"])
        branch_count = len(branch_results or [])
        success_count = len([item for item in (branch_results or []) if bool(item.get("ok"))])
        deferred_ids = self._string_list(plan.get("deferred_task_ids"), limit=8, item_limit=80)
        chosen_mode = str(plan.get("chosen_mode") or "status").strip() or "status"
        reason = str(plan.get("reason") or "").strip()
        tell_user_intention = self._build_heartbeat_tell_user_intention(plan, branch_results, execution_result)
        summary = (
            f"心跳完成一轮 {chosen_mode} 规划与执行：分支 {branch_count}，成功 {success_count}，"
            f"并行 {parallel_count} / 串行 {serial_count}。"
        )
        if deferred_ids:
            summary += f" 延后任务 {len(deferred_ids)} 个。"
        raw = {
            "memory_id": str(uuid.uuid4()),
            "timestamp": self._timestamp(),
            "topic": "心跳规划与执行",
            "summary": summary[:220],
            "memory_scope": "beat",
            "memory_stream": "heartbeat_observation",
            "event_type": "heartbeat_snapshot",
            "raw_user_prompt": f"heartbeat-plan:{chosen_mode}",
            "status": "completed",
            "next_actions": [f"defer:{task_id}" for task_id in deferred_ids[:3]],
            "heartbeat_tasks": [],
            "heartbeat_long_term_tasks": [],
            "salience": 0.7 if success_count else 0.45,
            "confidence": 0.82 if success_count else 0.6,
            "derived_from": ["heartbeat", chosen_mode],
            "context_tags": [tag for tag in ["heartbeat", chosen_mode, str(plan.get("execution_mode") or "single").strip()] if tag],
            "mental_notes": [item for item in [reason[:160], str(execution_result or "").strip()[:220]] if item],
            "relationship_signals": [tell_user_intention.get("reason")] if str(tell_user_intention.get("reason") or "").strip() else [],
            "relation_signal": {},
            "active_window": "recent",
            "long_term_candidate": self._build_heartbeat_long_term_candidate(plan, branch_results, execution_result),
            "heartbeat_execution_snapshot": {
                "execution_mode": str(plan.get("execution_mode") or "single"),
                "max_parallel": int(max_parallel),
                "parallel_used": parallel_count >= 2,
                "parallel_branch_count": int(parallel_count),
                "serial_branch_count": int(serial_count),
                "chosen_mode": chosen_mode,
                "reason": reason[:200],
                "deferred_task_ids": deferred_ids,
                "defer_reason": str(plan.get("defer_reason") or "")[:200],
                "execution_summary": str(execution_result or "")[:1000],
                "tell_user_intention": tell_user_intention,
                "branches": self._build_heartbeat_branch_snapshots(branch_results),
            },
        }
        return self.normalize_recent_entry(raw)

    def _build_heartbeat_companion_entries(self, primary_entry: dict, plan: dict, branch_results: list[dict], execution_result: str) -> list[dict]:
        entries: list[dict] = []
        reason = str(plan.get("reason") or "").strip()
        if reason:
            entries.append(
                self.normalize_recent_entry(
                    {
                        "memory_id": str(uuid.uuid4()),
                        "timestamp": primary_entry.get("timestamp"),
                        "topic": "心跳内部判断",
                        "summary": f"规划判断：{reason[:180]}",
                        "memory_scope": "beat",
                        "memory_stream": "mental",
                        "event_type": "heartbeat_reflection",
                        "status": "completed",
                        "derived_from": [str(primary_entry.get("memory_id") or "")],
                        "context_tags": list(primary_entry.get("context_tags") or []),
                        "active_window": "recent",
                        "salience": float(primary_entry.get("salience") or 0.5),
                        "confidence": float(primary_entry.get("confidence") or 0.5),
                    }
                )
            )
        branch_titles = []
        for item in branch_results or []:
            branch_id = str(item.get("branch_id") or "").strip()
            outcome = "完成" if bool(item.get("ok")) else "失败"
            if branch_id:
                branch_titles.append(f"{branch_id}:{outcome}")
        if branch_titles:
            entries.append(
                self.normalize_recent_entry(
                    {
                        "memory_id": str(uuid.uuid4()),
                        "timestamp": primary_entry.get("timestamp"),
                        "topic": "心跳任务信号",
                        "summary": "；".join(branch_titles[:4]),
                        "memory_scope": "beat",
                        "memory_stream": "task_signal",
                        "event_type": "task_signal",
                        "status": "completed",
                        "derived_from": [str(primary_entry.get("memory_id") or "")],
                        "context_tags": list(primary_entry.get("context_tags") or []),
                        "active_window": "recent",
                        "salience": min(1.0, float(primary_entry.get("salience") or 0.5) + 0.05),
                        "confidence": float(primary_entry.get("confidence") or 0.5),
                    }
                )
            )
        tell_user_intention = self._build_heartbeat_tell_user_intention(plan, branch_results, execution_result)
        intention_candidate = str(tell_user_intention.get("candidate") or "").strip()
        intention_reason = str(tell_user_intention.get("reason") or "").strip()
        if intention_candidate or intention_reason:
            entries.append(
                self.normalize_recent_entry(
                    {
                        "memory_id": str(uuid.uuid4()),
                        "timestamp": primary_entry.get("timestamp"),
                        "topic": "关系与情绪信号",
                        "summary": f"心跳形成了下一轮可能主动开口的意图：{(intention_candidate or intention_reason)[:160]}",
                        "memory_scope": "beat",
                        "memory_stream": "relationship_signal",
                        "event_type": "relationship_observation",
                        "status": "completed",
                        "derived_from": [str(primary_entry.get("memory_id") or "")],
                        "context_tags": ["heartbeat-followup", str(tell_user_intention.get("share_type") or "thought_share")],
                        "active_window": "recent",
                        "salience": 0.55,
                        "confidence": 0.7,
                    }
                )
            )
        return entries

    def _build_heartbeat_long_term_candidate(self, plan: dict, branch_results: list[dict], execution_result: str) -> dict:
        summary_prompt = str(plan.get("summary_prompt") or "").strip()
        chosen_mode = str(plan.get("chosen_mode") or "status").strip() or "status"
        success_outputs = [str(item.get("output") or "").strip() for item in (branch_results or []) if bool(item.get("ok")) and str(item.get("output") or "").strip()]
        if not summary_prompt and chosen_mode not in {"explore", "long_task"}:
            return self._normalize_long_term_candidate({})
        if not summary_prompt and not success_outputs:
            return self._normalize_long_term_candidate({})
        summary_parts = []
        if summary_prompt:
            summary_parts.append(summary_prompt)
        if execution_result:
            summary_parts.append(str(execution_result).strip()[:220])
        if success_outputs:
            summary_parts.append("执行产出：" + "；".join(success_outputs[:2])[:260])
        title = f"心跳阶段结论_{chosen_mode}"[:60]
        return self._normalize_long_term_candidate(
            {
                "should_write": True,
                "title": title,
                "summary": "\n".join([part for part in summary_parts if str(part).strip()])[:400],
                "keywords": ["heartbeat", chosen_mode, "planner", "executor"],
            }
        )

    def _build_heartbeat_branch_snapshots(self, branch_results: list[dict]) -> list[dict]:
        snapshots = []
        for item in (branch_results or [])[:8]:
            if not isinstance(item, dict):
                continue
            snapshots.append(
                {
                    "branch_id": str(item.get("branch_id") or "").strip(),
                    "run_mode": str(item.get("run_mode") or "serial").strip(),
                    "ok": bool(item.get("ok")),
                    "duration_seconds": float(item.get("duration_seconds") or 0),
                    "selected_task_ids": self._string_list(item.get("selected_task_ids"), limit=8, item_limit=80),
                    "defer_task_ids": self._string_list(item.get("defer_task_ids"), limit=8, item_limit=80),
                    "output_preview": str(item.get("output") or item.get("error") or "").strip()[:120],
                }
            )
        return snapshots

    def _build_companion_entries(self, primary_entry: dict) -> list[dict]:
        entries: list[dict] = []
        for note in primary_entry.get("mental_notes") or []:
            entries.append(
                self.normalize_recent_entry(
                    {
                        "memory_id": str(uuid.uuid4()),
                        "timestamp": primary_entry.get("timestamp"),
                        "topic": "最近在想什么",
                        "summary": str(note).strip(),
                        "memory_scope": "talk",
                        "memory_stream": "mental",
                        "event_type": "post_turn_reflection",
                        "status": "completed",
                        "derived_from": [str(primary_entry.get("memory_id") or "")],
                        "context_tags": list(primary_entry.get("context_tags") or []),
                        "active_window": "current",
                        "salience": min(1.0, float(primary_entry.get("salience") or 0.5) + 0.05),
                        "confidence": float(primary_entry.get("confidence") or 0.5),
                    }
                )
            )
        relation_signal = primary_entry.get("relation_signal") if isinstance(primary_entry.get("relation_signal"), dict) else {}
        for signal in primary_entry.get("relationship_signals") or []:
            entries.append(
                self.normalize_recent_entry(
                    {
                        "memory_id": str(uuid.uuid4()),
                        "timestamp": primary_entry.get("timestamp"),
                        "topic": "关系与情绪信号",
                        "summary": str(signal).strip(),
                        "memory_scope": "talk",
                        "memory_stream": "relationship_signal",
                        "event_type": "relationship_observation",
                        "status": "completed",
                        "derived_from": [str(primary_entry.get("memory_id") or "")],
                        "relation_signal": relation_signal,
                        "context_tags": list(primary_entry.get("context_tags") or []),
                        "active_window": "recent",
                        "salience": min(1.0, float(primary_entry.get("salience") or 0.5) + 0.05),
                        "confidence": float(primary_entry.get("confidence") or 0.5),
                    }
                )
            )
        if primary_entry.get("next_actions") or primary_entry.get("heartbeat_tasks") or primary_entry.get("heartbeat_long_term_tasks"):
            task_titles = [str(item.get("title") or "").strip() for item in (primary_entry.get("heartbeat_tasks") or []) if isinstance(item, dict)]
            task_titles.extend([str(item.get("title") or "").strip() for item in (primary_entry.get("heartbeat_long_term_tasks") or []) if isinstance(item, dict)])
            task_titles.extend(primary_entry.get("next_actions") or [])
            task_titles = [item for item in task_titles if item][:4]
            if task_titles:
                entries.append(
                    self.normalize_recent_entry(
                        {
                            "memory_id": str(uuid.uuid4()),
                            "timestamp": primary_entry.get("timestamp"),
                            "topic": "任务信号",
                            "summary": "；".join(task_titles)[:220],
                            "memory_scope": "talk",
                            "memory_stream": "task_signal",
                            "event_type": "task_signal",
                            "status": "completed",
                            "derived_from": [str(primary_entry.get("memory_id") or "")],
                            "context_tags": list(primary_entry.get("context_tags") or []),
                            "active_window": "current",
                            "salience": min(1.0, float(primary_entry.get("salience") or 0.5) + 0.1),
                            "confidence": float(primary_entry.get("confidence") or 0.5),
                        }
                    )
                )
        return entries

    def _infer_trigger_level(self, primary_entry: dict, companion_entries: list[dict], existing_entries: list[dict]) -> int:
        long_term_candidate = primary_entry.get("long_term_candidate") if isinstance(primary_entry.get("long_term_candidate"), dict) else {}
        if bool(long_term_candidate.get("should_write")):
            return 2
        if companion_entries:
            return 1
        if primary_entry.get("next_actions"):
            return 1
        existing_companions = [item for item in existing_entries[-12:] if str((item or {}).get("memory_stream") or "") in {"mental", "relationship_signal", "task_signal"}]
        if existing_companions and str(primary_entry.get("memory_stream") or "") == "talk":
            return 1
        return 0

    def build_long_term_memory_profile(
        self,
        *,
        title: str,
        summary: str,
        keywords: list[str] | None = None,
        source_type: str = "",
        source_reason: str = "",
        source_topic: str = "",
        source_entry: dict | None = None,
    ) -> dict:
        entry = source_entry if isinstance(source_entry, dict) else {}
        fragments = self._semantic_fragments(summary, limit=4)
        current_conclusion = fragments[0] if fragments else str(summary or "").strip()[:220]
        scenarios = self._build_applicable_scenarios(keywords or [], source_type, source_reason, source_topic, entry)
        history = self._build_history_evolution(current_conclusion, source_type, source_reason, source_topic, entry)
        return {
            "current_conclusion": current_conclusion,
            "history_evolution": history,
            "applicable_scenarios": scenarios,
            "current_effective": current_conclusion,
            "keywords": self._string_list(keywords or [], limit=10, item_limit=30),
        }

    def _maybe_promote_implicit_long_term_candidate(self, primary_entry: dict, companion_entries: list[dict], existing_entries: list[dict]) -> tuple[dict, list[str]]:
        long_term_candidate = primary_entry.get("long_term_candidate") if isinstance(primary_entry.get("long_term_candidate"), dict) else {}
        if bool(long_term_candidate.get("should_write")):
            return primary_entry, []

        signals: list[str] = []
        raw_prompt = str(primary_entry.get("raw_user_prompt") or "")
        summary = str(primary_entry.get("summary") or "")
        relationship_signals = [str(item) for item in (primary_entry.get("relationship_signals") or []) if str(item).strip()]
        mental_notes = [str(item) for item in (primary_entry.get("mental_notes") or []) if str(item).strip()]
        relation_signal = primary_entry.get("relation_signal") if isinstance(primary_entry.get("relation_signal"), dict) else {}
        preference_shift = str(relation_signal.get("preference_shift") or "").strip()

        prompt_has_hint = any(hint.lower() in raw_prompt.lower() for hint in self._LONG_TERM_HINTS)
        if prompt_has_hint:
            signals.append("prompt_hint")
        if preference_shift:
            signals.append("preference_shift")
        if relationship_signals:
            signals.append("relationship_signal")
        if mental_notes:
            signals.append("mental_note")
        if companion_entries:
            signals.append("companion_entries")
        if any(str((item or {}).get("memory_stream") or "") in {"mental", "relationship_signal"} for item in existing_entries[-8:]):
            signals.append("recent_companion_pattern")

        if not signals:
            return primary_entry, []

        parts = [summary]
        if preference_shift:
            parts.append(f"偏好变化/长期约定：{preference_shift}")
        if relationship_signals:
            parts.append("关系与情绪线索：" + "；".join(relationship_signals[:2]))
        if mental_notes:
            parts.append("内部整理：" + "；".join(mental_notes[:2]))
        candidate_summary = "\n".join([part for part in parts if str(part).strip()]).strip()[:400]
        keywords = list(primary_entry.get("context_tags") or []) + self._extract_keyword_hints(raw_prompt + "\n" + summary)
        title = str(primary_entry.get("topic") or "长期记忆候选").strip()[:60] or "长期记忆候选"
        primary_entry["long_term_candidate"] = {
            "should_write": True,
            "title": title,
            "summary": candidate_summary,
            "keywords": self._string_list(keywords, limit=10, item_limit=30),
            "promoted_to_local_at": "",
            "promoted_source": "",
            "promoted_action": "",
        }
        return primary_entry, signals[:5]

    def _extract_keyword_hints(self, text: str) -> list[str]:
        found: list[str] = []
        for hint in self._LONG_TERM_HINTS:
            if hint.lower() in str(text or "").lower() and hint not in found:
                found.append(hint)
            if len(found) >= 6:
                break
        return found

    def _semantic_fragments(self, text: str, limit: int = 4) -> list[str]:
        values: list[str] = []
        for item in str(text or "").replace("\r", "\n").split("\n"):
            for part in item.replace("；", "。").split("。"):
                cleaned = str(part).strip(" -•\t")
                if not cleaned:
                    continue
                values.append(cleaned[:220])
                if len(values) >= limit:
                    return values
        return values

    def _build_applicable_scenarios(self, keywords: list[str], source_type: str, source_reason: str, source_topic: str, entry: dict) -> list[str]:
        scenarios: list[str] = []
        for item in self._string_list(list(keywords or []) + list(entry.get("context_tags") or []), limit=8, item_limit=30):
            if item not in scenarios:
                scenarios.append(item)
        if source_topic and source_topic not in scenarios:
            scenarios.append(source_topic[:60])
        if source_reason == "long_term_candidate":
            scenarios.append("对话中明确提出的长期约定")
        elif source_reason == "recent-sweep":
            scenarios.append("潜意识在 recent sweep 中恢复")
        elif source_type:
            scenarios.append(f"来源:{source_type}")
        return scenarios[:6]

    def _build_history_evolution(self, current_conclusion: str, source_type: str, source_reason: str, source_topic: str, entry: dict) -> list[str]:
        parts: list[str] = []
        prefix = self._timestamp()
        topic = source_topic or str(entry.get("topic") or "").strip()
        if topic:
            parts.append(f"{prefix}：围绕“{topic[:60]}”沉淀出当前结论：{current_conclusion[:120]}")
        else:
            parts.append(f"{prefix}：沉淀出当前结论：{current_conclusion[:120]}")
        if source_reason:
            parts.append(f"触发来源：{source_reason}")
        if source_type:
            parts.append(f"写入路径：{source_type}")
        return parts[:4]

    def _normalize_long_term_candidate(self, raw: dict | None) -> dict:
        item = raw if isinstance(raw, dict) else {}
        return {
            "should_write": bool(item.get("should_write")),
            "title": str(item.get("title") or "").strip()[:60],
            "summary": str(item.get("summary") or "").strip()[:400],
            "keywords": self._string_list(item.get("keywords"), limit=10, item_limit=30),
            "promoted_to_local_at": str(item.get("promoted_to_local_at") or "").strip(),
            "promoted_source": str(item.get("promoted_source") or "").strip(),
            "promoted_action": str(item.get("promoted_action") or "").strip(),
        }

    def _normalize_relation_signal(self, raw: dict | None) -> dict:
        item = raw if isinstance(raw, dict) else {}
        result = {
            "tone": str(item.get("tone") or "").strip()[:30],
            "preference_shift": str(item.get("preference_shift") or "").strip()[:120],
            "importance": self._normalize_float(item.get("importance"), fallback=0.5),
        }
        return {k: v for k, v in result.items() if v not in {"", None}}

    def _string_list(self, raw, limit: int, item_limit: int) -> list[str]:
        values = raw if isinstance(raw, list) else []
        output: list[str] = []
        for item in values:
            text = str(item or "").strip()
            if not text:
                continue
            output.append(text[:item_limit])
            if len(output) >= limit:
                break
        return output

    def _normalize_float(self, value, fallback: float) -> float:
        try:
            number = float(value)
        except Exception:
            number = fallback
        return max(0.0, min(1.0, number))

    def _default_event_type(self, stream: str) -> str:
        if stream == "mental":
            return "post_turn_reflection"
        if stream == "relationship_signal":
            return "relationship_observation"
        if stream == "task_signal":
            return "task_signal"
        if stream == "heartbeat_observation":
            return "heartbeat_snapshot"
        return "conversation_turn"

    def _timestamp(self) -> str:
        return self._now_factory().strftime("%Y-%m-%d %H:%M:%S")