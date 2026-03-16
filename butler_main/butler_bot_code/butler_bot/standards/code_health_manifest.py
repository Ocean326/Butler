from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileLineBudget:
    relative_path: str
    max_lines: int
    rationale: str


@dataclass(frozen=True)
class ForbiddenImportRule:
    relative_glob: str
    forbidden_modules: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class CodeHealthManifest:
    version: str
    forbidden_import_rules: tuple[ForbiddenImportRule, ...]
    file_line_budgets: tuple[FileLineBudget, ...]
    maintenance_principles: tuple[str, ...]


DEFAULT_CODE_HEALTH_MANIFEST = CodeHealthManifest(
    version="2026-03-15",
    forbidden_import_rules=(
        ForbiddenImportRule(
            relative_glob="services/*.py",
            forbidden_modules=("memory_manager",),
            rationale="服务层不应反向依赖总编排类，避免再次形成大一统回流。",
        ),
        ForbiddenImportRule(
            relative_glob="runtime/*.py",
            forbidden_modules=("memory_manager",),
            rationale="运行时层应独立于 MemoryManager，可被主进程与测试复用。",
        ),
        ForbiddenImportRule(
            relative_glob="execution/*.py",
            forbidden_modules=("memory_manager",),
            rationale="执行层只依赖能力接口，不直接依赖总编排实现。",
        ),
    ),
    file_line_budgets=(
        FileLineBudget(
            relative_path="memory_manager.py",
            max_lines=7250,
            rationale="阻止总编排类在继续拆分期间重新失控增长。",
        ),
        FileLineBudget(
            relative_path="services/self_mind_runtime_service.py",
            max_lines=160,
            rationale="运行调度服务应保持轻量。",
        ),
        FileLineBudget(
            relative_path="services/self_mind_state_service.py",
            max_lines=220,
            rationale="状态服务只处理路径/读写/目标解析，不继续混入业务流程。",
        ),
        FileLineBudget(
            relative_path="services/self_mind_prompt_service.py",
            max_lines=180,
            rationale="prompt 服务只保留文本组装，不膨胀为新编排器。",
        ),
        FileLineBudget(
            relative_path="services/message_delivery_service.py",
            max_lines=180,
            rationale="发送服务应聚焦发送契约，不承担业务决策。",
        ),
        FileLineBudget(
            relative_path="services/upgrade_governance_service.py",
            max_lines=260,
            rationale="升级治理服务应聚焦审批与闸门，不吸收其他维护流程。",
        ),
        FileLineBudget(
            relative_path="runtime/cursor_runtime_support.py",
            max_lines=180,
            rationale="Cursor 运行时支持层应只保留环境与路径解析。",
        ),
    ),
    maintenance_principles=(
        "拆分的目的不是文件变多，而是功能独立、依赖方向稳定、修改影响面可预测。",
        "新服务默认单一职责，先保证可替换、可测试，再考虑进一步细拆。",
        "发现反向依赖或总编排回流时，优先抽独立支持模块，而不是继续在主类打补丁。",
        "代码健康必须可自动检查，不能只靠口头约定。",
    ),
)
