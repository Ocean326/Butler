from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from butler_paths import AGENT_HOME_REL, BODY_HOME_REL, COMPANY_HOME_REL, SPACE_HOME_REL, STATE_DIR_REL


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class GovernedAction:
    action_type: str
    target_path: str
    summary: str = ""
    requires_restart: bool = False


@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    risk_level: RiskLevel
    approval_required: bool
    rationale: str


class Governor:
    def evaluate(self, action: GovernedAction) -> GovernanceDecision:
        target = Path(str(action.target_path or "").replace("\\", "/"))
        target_text = target.as_posix().lower()

        if action.requires_restart or action.action_type in {"restart", "deploy", "launch"}:
            return GovernanceDecision(False, RiskLevel.HIGH, True, "涉及重启、上线或运行切换，必须人工批准。")

        if BODY_HOME_REL.as_posix().lower() in target_text:
            suffix = target.suffix.lower()
            if suffix in {".py", ".ps1", ".json"}:
                return GovernanceDecision(False, RiskLevel.HIGH, True, "涉及身体层代码或核心配置，必须人工批准。")
            return GovernanceDecision(False, RiskLevel.MEDIUM, True, "涉及身体层非核心文件，默认进入批准流。")

        if STATE_DIR_REL.as_posix().lower() in target_text:
            return GovernanceDecision(True, RiskLevel.LOW, False, "属于任务账本或代理状态层写入，可自动执行。")

        if AGENT_HOME_REL.as_posix().lower() in target_text:
            suffix = target.suffix.lower()
            if suffix in {".md", ".json", ".txt"}:
                return GovernanceDecision(True, RiskLevel.LOW, False, "属于脑子层记忆或说明写入，可自动执行。")
            return GovernanceDecision(False, RiskLevel.MEDIUM, True, "脑子层的非常规文件改动，默认要求批准。")

        if COMPANY_HOME_REL.as_posix().lower() in target_text or SPACE_HOME_REL.as_posix().lower() in target_text:
            return GovernanceDecision(True, RiskLevel.LOW, False, "属于工作区/家目录的低风险整理，可自动执行。")

        if target.suffix.lower() in {".md", ".txt"}:
            return GovernanceDecision(True, RiskLevel.LOW, False, "仅文档改动，可自动执行并留痕。")

        return GovernanceDecision(False, RiskLevel.MEDIUM, True, "目标风险未明确，默认要求批准。")
