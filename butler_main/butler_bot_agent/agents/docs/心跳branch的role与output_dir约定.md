# 心跳 branch 的 role 与 output_dir 约定

> **真源与完整配置在工作区**：公司目录 `./工作区` 下的约定与配置为唯一真源。本文档为**脑子层/主进程侧**的桥接说明，便于执行与排障时单页定位。

## 约定一句话

每条心跳 branch 在**规划 JSON** 中必须显式带 **role**（或 **agent_role**）与 **output_dir**；**执行器首条回复**须含三行：`role=...`、`output_dir=...`、`你作为 …-agent，…`。公司目录真源为 `./工作区`，output_dir 均相对于该根。

## 真源位置（工作区）

| 用途 | 路径 |
|------|------|
| 总览（单页） | `./工作区/心跳branch的role与output_dir约定.md` |
| 完整约定（TL;DR + schema） | `./工作区/agent_upgrade/心跳_branch元数据约定.md` |
| 一步速查 + 三行模板 | `./工作区/agent_upgrade/branch_role与output_dir_一步速查.md` |
| 规划器 branch 占位与枚举 | `./工作区/agent_upgrade/规划器_branch_占位.json` |
| role→output_dir 映射表 | `./工作区/agent_upgrade/角色-产出目录映射.json` |
| 索引与校验要点 | `./工作区/agent_upgrade/README_agent_upgrade.md`「心跳 branch 的 role / output_dir」 |

## 规划器 / 执行器侧

- **规划器**：生成每个 branch 时必填 `role`（或 `agent_role`）与 `output_dir`；枚举与占位见上表 `规划器_branch_占位.json`、`角色-产出目录映射.json`。
- **执行器**：首条回复须含三行（见「约定一句话」）；缺省 output_dir 时回退为 `./工作区`。三行模板与检查项见 `branch_role与output_dir_一步速查.md`、`执行侧首条回复三行_检查项.md`。
- **未指定 branch**：默认 `role=agent_upgrade`、`output_dir=./工作区/agent_upgrade`。

## 排障

- 规划器未带 role/output_dir → 工作区《下一步升级计划》§5.5、`心跳_branch元数据约定.md` §0；规划器 prompt 引用工作区约定的升级见 `./工作区/heartbeat_upgrade_request.json` 第二条。
- 执行器首条缺三行 → 工作区 `branch_role与output_dir_一步速查.md`、`执行侧首条回复三行_检查项.md`。

---
*2026-03-10 · 桥接文档 · 真源在 ./工作区*
