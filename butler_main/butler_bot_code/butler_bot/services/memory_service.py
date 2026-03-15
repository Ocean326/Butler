from __future__ import annotations

from datetime import datetime


class TurnMemoryExtractionService:
    def __init__(
        self,
        run_model_fn,
        json_extractor,
        heuristic_task_extractor,
        heuristic_long_term_candidate,
        normalize_heartbeat_tasks,
        now_factory=None,
    ) -> None:
        self._run_model_fn = run_model_fn
        self._json_extractor = json_extractor
        self._heuristic_task_extractor = heuristic_task_extractor
        self._heuristic_long_term_candidate = heuristic_long_term_candidate
        self._normalize_heartbeat_tasks = normalize_heartbeat_tasks
        self._now_factory = now_factory or datetime.now

    def _is_self_mind_task(self, raw_task, scene_mode: str) -> bool:
        if isinstance(raw_task, str):
            text = raw_task
        elif isinstance(raw_task, dict):
            text = " ".join(
                str(raw_task.get(key) or "")
                for key in ("title", "task", "detail", "summary", "reason")
            )
        else:
            return False
        normalized = str(text or "").strip().lower()
        if not normalized:
            return False
        explicit_markers = (
            "self_mind",
            "self mind",
            "自我意识",
            "自我认知",
            "自我思考",
            "自我升级",
            "反思",
            "复盘",
            "心理",
            "情绪",
            "人格",
            "价值观",
            "关系边界",
            "内在",
            "续思",
        )
        if any(marker in normalized for marker in explicit_markers):
            return True
        if scene_mode != "self_growth":
            return False
        reflective_markers = ("梳理", "想清楚", "理解自己", "回看", "沉淀", "认清")
        return any(marker in normalized for marker in reflective_markers)

    def _split_out_self_mind_tasks(self, tasks: list, scene_mode: str) -> tuple[list, list[str]]:
        kept = []
        cues = []
        for raw_task in tasks or []:
            if self._is_self_mind_task(raw_task, scene_mode):
                if isinstance(raw_task, str):
                    cue = raw_task
                elif isinstance(raw_task, dict):
                    cue = str(raw_task.get("detail") or raw_task.get("title") or raw_task.get("task") or "").strip()
                else:
                    cue = ""
                cue = cue[:160].strip()
                if cue and cue not in cues:
                    cues.append(cue)
                continue
            kept.append(raw_task)
        return kept, cues

    def extract_turn_candidates(self, user_prompt: str, assistant_reply: str, workspace: str, timeout: int, model: str) -> dict:
        prompt = (
            "你是记忆提炼器。请把本轮对话提炼为短期记忆，并且只输出 JSON，不要解释。\n"
            "不要硬套一个统一摘要模板。你只需要保证：工作/任务、聊天/关系、自我升级/反思至少能基本区分；如果场景混合，就如实输出 mixed。\n"
            "摘要应保留关键细节、未收口点、可进入 self_mind 的续思线索，而不是只给抽象结论。\n"
            "JSON schema:\n"
            "{\"topic\":\"\",\"summary\":\"\",\"scene_mode\":\"work|chat|self_growth|mixed|other\",\"detail_points\":[],\"unresolved_points\":[],\"self_mind_cues\":[],\"next_actions\":[],\"heartbeat_tasks\":[],\"heartbeat_long_term_tasks\":[],\"mental_notes\":[],\"relationship_signals\":[],\"context_tags\":[],\"relation_signal\":{\"tone\":\"\",\"preference_shift\":\"\",\"importance\":0.0},\"salience\":0.0,\"active_window\":\"current\",\"long_term_candidate\":{\"should_write\":false,\"title\":\"\",\"summary\":\"\",\"keywords\":[]}}\n"
            f"用户输入:\n{user_prompt[:3000]}\n\n助手输出:\n{assistant_reply[:3000]}"
        )
        out, ok = "", False
        try:
            out, ok = self._run_model_fn(prompt, workspace, min(max(30, timeout // 2), 120), model)
        except Exception:
            out, ok = "", False

        data = self._json_extractor(out if ok else "") or {}
        topic = str(data.get("topic") or "本轮对话").strip()[:18]
        summary = str(data.get("summary") or "").strip()
        if not summary and assistant_reply.strip():
            summary = (assistant_reply or user_prompt or "").strip().replace("\n", " ")[:120]
        actions = data.get("next_actions") if isinstance(data.get("next_actions"), list) else []
        actions = [str(x).strip()[:40] for x in actions if str(x).strip()][:3]
        mental_notes = data.get("mental_notes") if isinstance(data.get("mental_notes"), list) else []
        mental_notes = [str(x).strip()[:120] for x in mental_notes if str(x).strip()][:3]
        relationship_signals = data.get("relationship_signals") if isinstance(data.get("relationship_signals"), list) else []
        relationship_signals = [str(x).strip()[:120] for x in relationship_signals if str(x).strip()][:3]
        context_tags = data.get("context_tags") if isinstance(data.get("context_tags"), list) else []
        context_tags = [str(x).strip()[:30] for x in context_tags if str(x).strip()][:6]
        detail_points = data.get("detail_points") if isinstance(data.get("detail_points"), list) else []
        detail_points = [str(x).strip()[:160] for x in detail_points if str(x).strip()][:6]
        unresolved_points = data.get("unresolved_points") if isinstance(data.get("unresolved_points"), list) else []
        unresolved_points = [str(x).strip()[:120] for x in unresolved_points if str(x).strip()][:4]
        self_mind_cues = data.get("self_mind_cues") if isinstance(data.get("self_mind_cues"), list) else []
        self_mind_cues = [str(x).strip()[:160] for x in self_mind_cues if str(x).strip()][:4]
        scene_mode = str(data.get("scene_mode") or "mixed").strip()[:20] or "mixed"
        relation_signal = data.get("relation_signal") if isinstance(data.get("relation_signal"), dict) else {}
        salience = data.get("salience")
        active_window = str(data.get("active_window") or "current").strip() or "current"

        heuristic_short_tasks, heuristic_long_tasks = self._heuristic_task_extractor(user_prompt, assistant_reply)
        model_short_tasks = data.get("heartbeat_tasks") if isinstance(data.get("heartbeat_tasks"), list) else []
        model_long_tasks = data.get("heartbeat_long_term_tasks") if isinstance(data.get("heartbeat_long_term_tasks"), list) else []
        model_short_tasks, model_short_cues = self._split_out_self_mind_tasks(model_short_tasks, scene_mode)
        heuristic_short_tasks, heuristic_short_cues = self._split_out_self_mind_tasks(heuristic_short_tasks, scene_mode)
        model_long_tasks, model_long_cues = self._split_out_self_mind_tasks(model_long_tasks, scene_mode)
        heuristic_long_tasks, heuristic_long_cues = self._split_out_self_mind_tasks(heuristic_long_tasks, scene_mode)
        for cue in model_short_cues + heuristic_short_cues + model_long_cues + heuristic_long_cues:
            if cue and cue not in self_mind_cues:
                self_mind_cues.append(cue)

        lt = data.get("long_term_candidate") if isinstance(data.get("long_term_candidate"), dict) else {}
        heuristic_lt = self._heuristic_long_term_candidate(user_prompt, assistant_reply)
        should_write = bool(lt.get("should_write")) or bool(heuristic_lt.get("should_write"))
        lt_title = str(lt.get("title") or heuristic_lt.get("title") or "").strip()[:40]
        lt_summary = str(lt.get("summary") or heuristic_lt.get("summary") or "").strip()[:220]
        lt_keywords = [str(x).strip()[:20] for x in (lt.get("keywords") or heuristic_lt.get("keywords") or []) if str(x).strip()][:8]

        return {
            "timestamp": self._now_factory().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": topic,
            "summary": summary[:160],
            "scene_mode": scene_mode,
            "detail_points": detail_points,
            "unresolved_points": unresolved_points,
            "self_mind_cues": self_mind_cues,
            "next_actions": actions,
            "heartbeat_tasks": self._normalize_heartbeat_tasks(model_short_tasks, user_prompt, heuristic_short_tasks, long_term=False),
            "heartbeat_long_term_tasks": self._normalize_heartbeat_tasks(model_long_tasks, user_prompt, heuristic_long_tasks, long_term=True),
            "mental_notes": mental_notes,
            "relationship_signals": relationship_signals,
            "context_tags": context_tags,
            "relation_signal": relation_signal,
            "salience": salience,
            "active_window": active_window,
            "long_term_candidate": {
                "should_write": should_write,
                "title": lt_title,
                "summary": lt_summary,
                "keywords": lt_keywords,
            },
        }