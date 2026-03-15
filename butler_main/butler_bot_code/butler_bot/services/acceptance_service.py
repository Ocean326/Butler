from __future__ import annotations

import re


class AcceptanceService:
    def build_task_receipt(
        self,
        *,
        task_id: str,
        item: dict,
        plan: dict,
        execution_result: str,
        branch_results: list[dict],
        selected_ids: set[str],
        complete_ids: set[str],
        defer_ids: set[str],
        touched_long_ids: set[str],
    ) -> dict:
        task_id_text = str(task_id or "").strip()
        relevant = [
            branch
            for branch in branch_results or []
            if isinstance(branch, dict) and task_id_text in self._branch_task_targets(branch)
        ]
        successful = [branch for branch in relevant if bool(branch.get("ok"))]
        acceptance_branch = next(
            (
                branch
                for branch in reversed(successful)
                if str(branch.get("process_role") or "").strip().lower() == "acceptance"
                or str(branch.get("execution_kind") or "").strip().lower() == "acceptance"
            ),
            None,
        )
        runtime_source = acceptance_branch or (successful[-1] if successful else (relevant[-1] if relevant else {}))
        runtime_profile = dict(runtime_source.get("runtime_profile") or {}) if isinstance(runtime_source.get("runtime_profile"), dict) else {}
        branch_ids = [str(branch.get("branch_id") or "").strip() for branch in relevant if str(branch.get("branch_id") or "").strip()]

        process_roles: list[str] = []
        for branch in relevant:
            role = str(branch.get("process_role") or "").strip()
            if role and role not in process_roles:
                process_roles.append(role)

        acceptance_status = "pending"
        decision = "continue"
        if task_id_text in defer_ids:
            acceptance_status = "deferred"
            decision = "defer"
        elif task_id_text in complete_ids:
            decision = "accept" if acceptance_branch else "complete"
            acceptance_status = "accepted" if acceptance_branch else "completed"
        elif task_id_text in selected_ids or task_id_text in touched_long_ids:
            acceptance_status = "in_progress"

        return {
            "program_id": str(plan.get("program_id") or plan.get("run_id") or item.get("program_id") or "").strip(),
            "manager_state": {
                "decision": decision,
                "mode": str(plan.get("chosen_mode") or "").strip(),
                "execution_mode": str(plan.get("execution_mode") or "").strip(),
                "reason": self._compact_text(str(plan.get("reason") or ""), limit=280),
            },
            "acceptance_status": acceptance_status,
            "acceptance_summary": self._build_summary(task_id_text, plan, execution_result, relevant, acceptance_status),
            "runtime_profile": runtime_profile,
            "process_roles": process_roles,
            "last_branch_id": branch_ids[-1] if branch_ids else "",
            "branch_ids": branch_ids,
        }

    def _branch_task_targets(self, branch: dict) -> set[str]:
        result: set[str] = set()
        for key in ("selected_task_ids", "complete_task_ids", "defer_task_ids", "touch_long_task_ids"):
            for value in branch.get(key) or []:
                text = str(value or "").strip()
                if text:
                    result.add(text)
        return result

    def _build_summary(self, task_id: str, plan: dict, execution_result: str, relevant: list[dict], acceptance_status: str) -> str:
        plan_reason = self._compact_text(str(plan.get("reason") or plan.get("user_message") or ""), limit=160)
        result_preview = self._compact_text(str(execution_result or ""), limit=220)
        branch_bits = []
        for branch in relevant[-3:]:
            branch_id = str(branch.get("branch_id") or "branch").strip() or "branch"
            role = str(branch.get("process_role") or branch.get("agent_role") or "").strip()
            preview = self._compact_text(str(branch.get("output") or branch.get("error") or ""), limit=120)
            branch_bits.append(f"{branch_id}/{role}: {preview}".strip(": "))
        parts = [f"task={task_id}", f"status={acceptance_status}"]
        if plan_reason:
            parts.append(f"manager={plan_reason}")
        if result_preview:
            parts.append(f"result={result_preview}")
        if branch_bits:
            parts.append(f"branches={' | '.join(branch_bits)}")
        return "；".join(part for part in parts if part)

    def _compact_text(self, text: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"
