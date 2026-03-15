"""Guardian 执行层：对 approve 的请求执行补丁应用、测试、回滚并写入审计账本。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from guardian_bot.ledger_store import GuardianLedgerStore
from guardian_bot.request_models import GuardianRequest
from guardian_bot.test_selector import GuardianTestSelector


class GuardianExecutor:
    """对已批准的请求执行补丁、测试与回滚。"""

    def __init__(
        self,
        ledger: GuardianLedgerStore,
        workspace_root: Path,
        test_selector: GuardianTestSelector,
    ) -> None:
        self.ledger = ledger
        self.workspace_root = Path(workspace_root)
        self.test_selector = test_selector

    def can_execute_directly(self, request: GuardianRequest) -> bool:
        """低风险 record-only 或 auto-fix 可直接执行（或仅备案）。"""
        return request.risk_level == "low" and request.request_type in {"record-only", "auto-fix"}

    def should_execute(self, request: GuardianRequest) -> bool:
        """是否需要对 approve 的请求执行动作（补丁/测试）。"""
        if not self.can_execute_directly(request):
            return False
        if request.request_type == "record-only":
            return True
        if request.requires_code_change and not request.patch_plan:
            return False
        return True

    def execute(self, request: GuardianRequest) -> str:
        """
        执行已批准的请求。
        返回: "done" | "filed" | "rolled-back" | "skipped"
        """
        if request.request_type == "record-only":
            self.ledger.write_execution_event(
                request_id=request.request_id,
                status="filed",
                notes=["record-only: 已备案，无需执行动作"],
                request_payload=request.to_dict(),
                patch_applied=False,
                tests_passed=None,
                rollback_performed=False,
            )
            return "filed"

        if request.requires_code_change and request.patch_plan:
            return self._execute_with_patch(request)
        return self._execute_no_patch(request)

    def _execute_no_patch(self, request: GuardianRequest) -> str:
        """无代码变更：仅运行验证测试并记录。"""
        tests = self.test_selector.select_tests(request)
        passed = self._run_tests(tests)
        self.ledger.write_execution_event(
            request_id=request.request_id,
            status="done" if passed else "skipped",
            notes=[f"无补丁，测试: {'通过' if passed else '跳过或失败'}"],
            request_payload=request.to_dict(),
            patch_applied=False,
            tests_passed=passed,
            rollback_performed=False,
        )
        return "done" if passed else "skipped"

    def _execute_with_patch(self, request: GuardianRequest) -> str:
        """有补丁：备份 → 应用 → 测试 → 失败则回滚。"""
        patch_plan = request.patch_plan or {}
        edits = patch_plan.get("edits") or []
        if not edits:
            self.ledger.write_execution_event(
                request_id=request.request_id,
                status="skipped",
                notes=["patch_plan 无 edits，跳过执行"],
                request_payload=request.to_dict(),
                patch_applied=False,
                tests_passed=None,
                rollback_performed=False,
            )
            return "skipped"

        backups: dict[str, str] = {}
        err_msg = "测试未通过"
        try:
            for edit in edits:
                if not isinstance(edit, dict):
                    continue
                file_path = edit.get("file") or edit.get("path")
                old_text = edit.get("old_text") or edit.get("old")
                new_text = edit.get("new_text") or edit.get("new")
                if not file_path:
                    continue
                full_path = self.workspace_root / file_path
                if not full_path.exists():
                    continue
                content = full_path.read_text(encoding="utf-8")
                if old_text not in content:
                    raise ValueError(f"patch 中 old_text 未在文件中找到: {file_path}")
                backups[str(full_path)] = content
                new_content = content.replace(old_text, new_text, 1)
                full_path.write_text(new_content, encoding="utf-8")

            tests = self.test_selector.select_tests(request)
            passed = self._run_tests(tests)
            if passed:
                self.ledger.write_execution_event(
                    request_id=request.request_id,
                    status="done",
                    notes=["补丁已应用，测试通过"],
                    request_payload=request.to_dict(),
                    patch_applied=True,
                    tests_passed=True,
                    rollback_performed=False,
                )
                return "done"
        except Exception as exc:
            err_msg = str(exc)

        for path_str, content in backups.items():
            Path(path_str).write_text(content, encoding="utf-8")
        self.ledger.write_execution_event(
            request_id=request.request_id,
            status="rolled-back",
            notes=[f"测试失败或异常，已回滚: {err_msg}"],
            request_payload=request.to_dict(),
            patch_applied=True,
            tests_passed=False,
            rollback_performed=True,
        )
        return "rolled-back"

    def _run_tests(self, test_names: list[str]) -> bool:
        """运行测试，返回是否全部通过。"""
        tests_dir = self.workspace_root / "butler_bot_code" / "tests"
        if not tests_dir.exists():
            return True
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", str(tests_dir), "-v", "--tb=short", "-q"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
