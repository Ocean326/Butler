# 探索产出：.cursor/skills 查阅与整理

> **探索日期**：2026-03-08  
> **方向**：自我升级 skills（查阅现有 skills，整理一条可复用内容）  
> **边界**：不涉及 LLM 训练/架构，仅 Agent 层技能与协作。

---

## 1. 现有 .cursor/skills 摘要

| 技能名 | 路径 | 用途 |
|--------|------|------|
| **daily-inspection** | `.cursor/skills/daily-inspection/` | 每日启动与收口例行巡检；按 WORKFLOW 调用 orchestrator、secretary、file-manager 等，产出到研究管理工作区。 |

- **入口**：`SKILL.md`（流程与调用约定）、`reference.md`（与 WORKFLOW 对应、检查清单、产出路径速查）、`DailyResearchOps.ps1`（脚本）。
- **与 subagent 的衔接**：该 skill 明确「调用子 Agent 时必须指定工作区」「产出写入 `./研究管理工作区/<agent 名>/`」，与前期探索的「Subagent 三要素 = 调用约定 + 任务/结果契约 + 边界与权限」一致；可作为「编排 + 主—子调用」的落地示例。

---

## 2. 本条落地记录（查阅 .cursor/skills）

- **查阅时间**：2026-03-08 本心跳
- **查阅内容**：`daily-inspection` 的 SKILL.md、reference.md
- **未新增** skill 文件，仅整理本条探索产出至本文件。
- **后续可做**：发现或新增技能时，在 work-tree/备份 下安全落地并在此或单独文件中记录。
