from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtocolSpec:
    protocol_id: str
    title: str
    relative_path: str
    applies_to: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class ArchitectureManifest:
    version: str
    core_runtime_root_modules: tuple[str, ...]
    grouped_subpackages: dict[str, str]
    protocol_specs: tuple[ProtocolSpec, ...]
    invariants: tuple[str, ...]
    next_split_targets: tuple[str, ...]


PROTOCOL_SPECS: tuple[ProtocolSpec, ...] = (
    ProtocolSpec(
        protocol_id="task_collaboration",
        title="任务协作协议",
        relative_path="protocols/task_collaboration.md",
        applies_to=("dialogue", "heartbeat", "task_ledger"),
        summary="统一任务入口、状态真源、验收回执与任务收口口径。",
    ),
    ProtocolSpec(
        protocol_id="heartbeat_executor",
        title="heartbeat 执行协议",
        relative_path="protocols/heartbeat_executor.md",
        applies_to=("heartbeat", "branch_executor"),
        summary="约束心跳执行者优先做成事、先诊断再报错、输出证据与风险。",
    ),
    ProtocolSpec(
        protocol_id="update_agent_maintenance",
        title="统一维护入口协议",
        relative_path="protocols/update_agent_maintenance.md",
        applies_to=("maintenance", "update_agent"),
        summary="统一 role/prompt/code/config 收敛口径，先找单一真源再改。",
    ),
    ProtocolSpec(
        protocol_id="self_update",
        title="自我更新协作协议",
        relative_path="protocols/self_update.md",
        applies_to=("maintenance", "upgrade", "governor"),
        summary="约束自我升级必须走方案、审批、验证、回执链路。",
    ),
    ProtocolSpec(
        protocol_id="self_mind_collaboration",
        title="自我认识协作协议",
        relative_path="protocols/self_mind_collaboration.md",
        applies_to=("dialogue", "self_mind", "heartbeat"),
        summary="统一 self_mind 与身体层、任务层之间的分工和交接边界。",
    ),
)


DEFAULT_ARCHITECTURE_MANIFEST = ArchitectureManifest(
    version="2026-03-15",
    core_runtime_root_modules=(
        "agent.py",
        "butler_bot.py",
        "butler_paths.py",
        "governor.py",
        "heartbeat_orchestration.py",
        "heartbeat_service_runner.py",
        "memory_cli.py",
        "memory_manager.py",
    ),
    grouped_subpackages={
        "services": "状态、记忆、任务、提示词装配等业务服务层。",
        "runtime": "CLI 执行与运行时路由层。",
        "registry": "skills / sub-agents / teams 的注册与发现层。",
        "execution": "协作执行层，例如 agent team 执行器。",
        "utils": "低耦合工具与安全写入等基础能力。",
        "standards": "长期有效的工程边界、协议真源与架构清单。",
        "obsolete": "已退出主链路但保留参考价值的过时代码。",
    },
    protocol_specs=PROTOCOL_SPECS,
    invariants=(
        "代码根目录仅保留主机制入口，非主链路模块必须归类到职责子目录。",
        "任务状态真源为 task_ledger，任务工作区是可读投影，不再反向发明第二套状态机。",
        "自我升级不得绕过 governor 与 upgrade_request 入口直接改身体层高风险目标。",
        "self_mind 负责认知与续思，不单独维护平行执行系统，进入执行必须交接到任务层或 heartbeat。",
        "协议文本必须有单一真源，禁止长期散落在多个 prompt 硬编码副本中。",
    ),
    next_split_targets=(
        "memory_manager.self_mind_loop",
        "memory_manager.upgrade_request_flow",
        "memory_manager.delivery_and_reply_flow",
    ),
)


def protocol_spec_map() -> dict[str, ProtocolSpec]:
    return {item.protocol_id: item for item in PROTOCOL_SPECS}
