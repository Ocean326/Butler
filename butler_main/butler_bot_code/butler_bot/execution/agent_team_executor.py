from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time

from registry.agent_capability_registry import load_team_definition
from butler_paths import (
    HEARTBEAT_EXECUTOR_AGENT_ROLE_FILE_REL,
    HEARTBEAT_EXECUTOR_WORKSPACE_HINT_FILE_REL,
    SUBAGENT_HOME_REL,
    UPDATE_AGENT_ROLE_FILE_REL,
    resolve_butler_root,
)


class AgentTeamExecutor:
    def __init__(self, run_model_fn):
        self._run_model_fn = run_model_fn

    def execute_request(self, request: dict, workspace: str, timeout: int, model: str) -> dict:
        request_type = str(request.get("request_type") or "").strip().lower()
        task = str(request.get("task") or request.get("prompt") or "").strip()
        if request_type == "subagent":
            role_name = str(request.get("agent_role") or request.get("role_name") or "").strip()
            return self.execute_subagent(role_name, task, workspace, timeout, model, request_context=request)
        if request_type == "team":
            team_id = str(request.get("team_id") or "").strip()
            return self.execute_team(team_id, task, workspace, timeout, model, request_context=request)
        return {
            "ok": False,
            "request_type": request_type,
            "error": f"unsupported request_type: {request_type or '(empty)'}",
            "output": "",
        }

    def execute_subagent(
        self,
        role_name: str,
        task: str,
        workspace: str,
        timeout: int,
        model: str,
        *,
        request_context: dict | None = None,
        shared_context: str = "",
    ) -> dict:
        started = time.time()
        normalized_role = str(role_name or "").strip() or "heartbeat-executor-agent"
        role_excerpt = self._load_subagent_role_excerpt(workspace, normalized_role)
        if not role_excerpt:
            return {
                "ok": False,
                "agent_role": normalized_role,
                "error": f"sub-agent role not found: {normalized_role}",
                "output": "",
                "duration_seconds": round(time.time() - started, 2),
            }
        prompt = self._build_subagent_prompt(normalized_role, role_excerpt, task, shared_context, request_context=request_context)
        output = ""
        ok = False
        error_text = ""
        try:
            output, ok = self._run_model_fn(prompt, workspace, timeout, model)
        except Exception as exc:
            error_text = str(exc)
        return {
            "ok": bool(ok and str(output or "").strip()),
            "agent_role": normalized_role,
            "task": task,
            "output": str(output or "").strip(),
            "error": error_text,
            "duration_seconds": round(time.time() - started, 2),
        }

    def execute_team(
        self,
        team_id: str,
        task: str,
        workspace: str,
        timeout: int,
        model: str,
        *,
        request_context: dict | None = None,
    ) -> dict:
        started = time.time()
        definition = load_team_definition(workspace, team_id)
        if not definition:
            return {
                "ok": False,
                "team_id": team_id,
                "error": f"team definition not found: {team_id}",
                "output": "",
                "duration_seconds": round(time.time() - started, 2),
            }
        steps = definition.get("steps") if isinstance(definition.get("steps"), list) else []
        if not steps:
            return {
                "ok": False,
                "team_id": team_id,
                "error": f"team has no steps: {team_id}",
                "output": "",
                "duration_seconds": round(time.time() - started, 2),
            }
        max_parallel = max(1, min(4, int(definition.get("max_parallel") or 3)))
        all_results: list[dict] = []
        shared_context = ""
        for step in steps:
            if not isinstance(step, dict):
                continue
            members = [member for member in (step.get("members") or []) if isinstance(member, dict)]
            if not members:
                continue
            mode = str(step.get("mode") or "serial").strip().lower() or "serial"
            if mode == "parallel" and len(members) > 1:
                with ThreadPoolExecutor(max_workers=min(max_parallel, len(members))) as pool:
                    future_map = {}
                    for member in members[:max_parallel]:
                        rendered_task = self._format_member_task(str(member.get("task") or "{task}"), task, shared_context)
                        future = pool.submit(
                            self.execute_subagent,
                            str(member.get("role") or "").strip(),
                            rendered_task,
                            workspace,
                            timeout,
                            model,
                            request_context=request_context,
                            shared_context=shared_context,
                        )
                        future_map[future] = member
                    for future in as_completed(future_map):
                        item = self._resolve_parallel_member_result(future_map[future], future, started=started)
                        item["step_id"] = str(step.get("step_id") or "step")
                        item["run_mode"] = "parallel"
                        all_results.append(item)
            else:
                for member in members:
                    rendered_task = self._format_member_task(str(member.get("task") or "{task}"), task, shared_context)
                    item = self.execute_subagent(
                        str(member.get("role") or "").strip(),
                        rendered_task,
                        workspace,
                        timeout,
                        model,
                        request_context=request_context,
                        shared_context=shared_context,
                    )
                    item["step_id"] = str(step.get("step_id") or "step")
                    item["run_mode"] = "serial"
                    all_results.append(item)
            shared_context = self._render_team_results(all_results)
        final_output = self._render_team_report(team_id, definition, task, all_results)
        return {
            "ok": any(bool(item.get("ok")) for item in all_results),
            "team_id": team_id,
            "task": task,
            "output": final_output,
            "member_results": all_results,
            "duration_seconds": round(time.time() - started, 2),
            "error": "",
        }

    def _resolve_parallel_member_result(self, member: dict, future, *, started: float) -> dict:
        try:
            return future.result()
        except Exception as exc:
            role_name = str((member or {}).get("role") or "").strip() or "unknown-agent"
            task = str((member or {}).get("task") or "").strip()
            return {
                "ok": False,
                "agent_role": role_name,
                "task": task,
                "output": "",
                "error": str(exc),
                "duration_seconds": round(time.time() - started, 2),
            }

    def _format_member_task(self, template: str, task: str, team_results: str) -> str:
        mapping = {
            "task": task,
            "team_results": team_results or "(暂无前序结果)",
        }
        try:
            return template.format_map(mapping).strip()
        except Exception:
            return f"{template.strip()}\n\n原始任务：{task}\n\n前序团队结果：\n{team_results or '(暂无前序结果)'}"

    def _build_subagent_prompt(
        self,
        role_name: str,
        role_excerpt: str,
        task: str,
        shared_context: str,
        *,
        request_context: dict | None = None,
    ) -> str:
        workspace_hint = self._load_workspace_hint()
        reason = str((request_context or {}).get("why") or "").strip()
        parts = []
        if workspace_hint:
            parts.append(workspace_hint)
        parts.append(f"【子Agent角色】\nrole={role_name}\n{role_excerpt}")
        parts.append(
            "【运行约束】\n"
            "你当前是被主入口临时调用的 sub-agent。\n"
            "1. 只完成这轮被分配的局部任务。\n"
            "2. 不得再次调用 sub-agent、agent team、planner of planners 或任何递归分派。\n"
            "3. 如果需要额外协作，只能在 unresolved 里明确提出，而不是自行扩张链路。\n"
            "4. 结果必须可被上级入口直接汇总。"
        )
        if reason:
            parts.append(f"【调用原因】\n{reason}")
        if shared_context:
            parts.append(f"【前序团队上下文】\n{shared_context}")
        parts.append(
            "【输出契约】\n"
            "请用以下四段输出：\n"
            "- result\n"
            "- evidence\n"
            "- unresolved\n"
            "- next_step"
        )
        parts.append(f"【本轮任务】\n{task}")
        return "\n\n".join(part for part in parts if str(part or "").strip()) + "\n"

    def _render_team_results(self, results: list[dict]) -> str:
        lines: list[str] = []
        for item in results[-8:]:
            role_name = str(item.get("agent_role") or "agent")
            step_id = str(item.get("step_id") or "step")
            if bool(item.get("ok")):
                preview = str(item.get("output") or "").strip()
                lines.append(f"- [{step_id}] {role_name}: {preview[:240]}")
            else:
                lines.append(f"- [{step_id}] {role_name}: FAILED {str(item.get('error') or '').strip()[:180]}")
        return "\n".join(lines).strip()

    def _render_team_report(self, team_id: str, definition: dict, task: str, results: list[dict]) -> str:
        lines = [
            f"## Team Result\n- team_id: {team_id}\n- team_name: {str(definition.get('name') or team_id).strip()}\n- task: {task}",
            "## Member Outputs",
        ]
        for item in results:
            role_name = str(item.get("agent_role") or "agent")
            step_id = str(item.get("step_id") or "step")
            if bool(item.get("ok")):
                lines.append(f"### [{step_id}] {role_name}\n{str(item.get('output') or '').strip()}")
            else:
                lines.append(f"### [{step_id}] {role_name}\nFAILED: {str(item.get('error') or 'unknown error').strip()}")
        return "\n\n".join(lines).strip()

    def _load_workspace_hint(self) -> str:
        try:
            root = resolve_butler_root()
            path = root / HEARTBEAT_EXECUTOR_WORKSPACE_HINT_FILE_REL
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _load_subagent_role_excerpt(self, workspace: str, role_name: str, max_chars: int = 1800) -> str:
        path = self._resolve_subagent_role_file(workspace, role_name)
        if path is None or not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n..."

    def _resolve_subagent_role_file(self, workspace: str, role_name: str) -> Path | None:
        normalized = str(role_name or "").strip()
        if not normalized:
            return None
        root = resolve_butler_root(workspace)
        if normalized in {"executor", "heartbeat-executor-agent"}:
            return root / HEARTBEAT_EXECUTOR_AGENT_ROLE_FILE_REL
        if normalized == "update-agent":
            return root / UPDATE_AGENT_ROLE_FILE_REL
        direct = root / SUBAGENT_HOME_REL / f"{normalized}.md"
        if direct.exists():
            return direct
        fallback = root / SUBAGENT_HOME_REL / f"{normalized}-agent.md"
        if fallback.exists():
            return fallback
        return None

