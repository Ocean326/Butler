# Repository Guidelines

## 项目结构与模块组织
`butler_main/` 是主代码区。优先从 `runtime_os/` 理解当前运行时命名空间；`agents_os/`、`multi_agents_os/` 仍是迁移期核心目录；`orchestrator/` 负责控制面；`butler_bot_code/` 承载 Butler 运行体，包括 `butler_bot/`、`configs/`、`run/`、`logs/`、`tests/`。`docs/` 是唯一正式文档入口；其中 `docs/project-map/` 是当前给人和 agent 共用的导航层。`BrainStorm/` 用于研究、记忆和工作稿，不是正式架构真源。临时工作放 `工作区/`，工具脚本放 `tools/`，历史资产放 `过时/`。

## 架构入口
当前按 `3 -> 2 -> 1` 理解系统：
- `3`：`orchestrator` control plane
- `2`：`runtime_os / process runtime`
- `1`：`runtime_os / agent runtime`

新代码应保持这个依赖方向。做较大改动前，先读仓库根 `README.md`，再读 `docs/README.md`，然后补读当天的 `docs/daily-upgrade/<MMDD>/00_当日总纲.md`。

## 改动前读取协议
1. 固定先读：
   - 仓库根 `README.md`
   - `docs/README.md`
   - 当天 `docs/daily-upgrade/<MMDD>/00_当日总纲.md`
2. 再读 `docs/project-map/00_current_baseline.md`，确认当前现役术语。
3. 再读 `docs/project-map/01_layer_map.md`，先判主层级。
4. 再读 `docs/project-map/02_feature_map.md`，命中功能条目与改前读包。
5. 最后按 `docs/project-map/04_change_packets.md` 补读目标专题，不要自由扩散式扫 `docs/` 或整包扫 `concepts/`。
6. 开始改前，先在回复里明确四件事：
   - 目标功能
   - 所属层级
   - 当前真源文档
   - 计划查看的代码目录和测试
7. 如果需求里出现 `heartbeat`、`guardian`、`sidecar` 等旧词，先做“历史别名 -> 当前功能”映射，再继续定位代码。
8. 如果问题跨 `frontdoor -> negotiation/query -> mission/campaign -> runner -> feedback`，或用户明确说“系统性不符合设计预期”，必须补读 `docs/project-map/06_system_audit_and_upgrade_loop.md`，先建链路矩阵，再开始改。
9. 系统级升级固定按：
   - 第一波并行
   - 再规划
   - 第二波并行
   - acceptance 与文档回写
10. 系统级升级结束前，必须至少同步更新：
   - 当天 `00_当日总纲.md`
   - 对应专题正文
   - `docs/project-map/03_truth_matrix.md`
   - `docs/project-map/04_change_packets.md`
   - `docs/README.md`

## 文档冲突裁决顺序
1. `docs/project-map/` 当前条目
2. 最新 `00_当日总纲.md` 及其明确链接的当日真源
3. `docs/runtime/` 稳定合同文档
4. `docs/concepts/` 现役文档
5. `docs/concepts/` 兼容期资料
6. `docs/concepts/history/` 与其他历史文档

`docs/concepts/history/` 和历史快照桩文件只用于追溯，不直接作为当前设计依据。

## 构建、测试与开发命令
仓库未提供独立 build 流程，默认使用虚拟环境和现有管理脚本：

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest butler_main\butler_bot_code\tests\test_chat_cli_runner.py -q
.\butler_main\butler_bot_code\manager.ps1 status
.\butler_main\butler_bot_code\manager.ps1 restart butler_bot
.\butler_main\butler_bot_code\watch_stack.ps1
git status --short
```

## 代码风格与命名
Python 使用 4 空格缩进，优先遵循周边文件既有风格，避免无关大改。仓库当前没有提交统一 formatter 或 linter 配置。模块、函数、测试文件用 `snake_case`，类名用 `PascalCase`。文档命名沿用现有模式，例如 `docs/daily-upgrade/0325/00_当日总纲.md`、`BrainStorm/Working/YYYYMMDD_topic_to_brainstorm.md`。

## 测试规范
默认测试框架是 `pytest`。自动化回归测试放在 `butler_main/butler_bot_code/tests/`，文件名必须是 `test_*.py`。一次性脚本或强依赖环境的脚本放 `tests/manual/`，不要进入默认收集。改 runtime 边界、导入面、协议或路径布局时，必须同步补一条对应回归测试。

## 提交与 Pull Request 规范
近期提交前缀以小写动词类别为主：`feat:`、`fix:`、`refactor:`、`chore:`、`test:`，后接简短祈使式摘要，例如 `refactor: extract orchestrator governance bridge`。单个提交只做一件事。PR 需说明影响层级，关联对应计划文档或 issue，列出已执行测试；涉及运维可见行为、日志或观测输出变化时，附日志片段或截图。

## Vibecoding 默认收尾动作
从 `2026-04-02` 起，vibecoding agent 在**完成实现后、最终回复前**，默认要执行一轮固定收口，不再只做口头总结。

默认顺序：

1. 先完成代码、文档和测试改动
2. 运行 `./tools/vibe-close analyze`
   - 若本轮是“先计划再实施”的任务，补 `--planned`
3. 读取输出 JSON，按 `doc_mode` / `doc_targets` 回写文档
4. 跑本次最小必要测试
5. 运行 `./tools/vibe-close apply --topic <slug> --summary "<summary>"`
   - 若本轮是“先计划再实施”的任务，补 `--planned`
6. 最终回复必须明确：
   - `change_level`
   - 已更新文档
   - 已执行测试
   - commit SHA
   - branch / worktree / push 结果

现役裁决：

- `vibe-close analyze` 只负责判断收口级别与文档目标，不代替 agent 写文档正文
- 若 `vibe-close analyze` 的 `changed_paths` 明显包含与本轮任务无关的旧脏改动，先停下说明，不要盲目 `apply`
- `change_level=system` 且当前在默认分支时，`vibe-close apply` 会：
  - 若是 `docs-only system`，默认直接在当前分支完成 `commit / push`，不再自动创建 sibling worktree
  - 若是跨层代码系统升级，切到建议 branch
  - commit
  - 若存在 remote，默认 push
  - 仅对跨层代码系统升级创建 sibling worktree
  - 若发生 branch/worktree 收口，再把当前工作区切回默认分支，保持主工作区常干净
- 若仓库无 remote，push 返回 `skipped`，不视为失败
- 普通小改动不强制新开 worktree，但仍应保持 commit 可追踪

相关真源：

- `tools/vibe-close`
- `docs/daily-upgrade/0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md`
- `docs/project-map/03_truth_matrix.md`
- `docs/project-map/04_change_packets.md`

## 文档与仓库纪律
不要把临时 `.md`、`.json`、`.txt` 或辅助脚本直接丢到仓库根目录。正式方案进 `docs/`，长期研究沉淀进 `BrainStorm/`，进行中的材料放 `工作区/` 或对应模块目录。新增文件前先看最近的 `README.md`，按现有落位规则放置，不要新开语义重复的顶层目录。项目处于持续开发中，历史文档可能已经过时；阅读和引用时要主动甄别是否仍与当前代码、目录边界和主线计划一致，发现失效、重复或误导性的文档时，应及时反馈，并建议更新内容、补“已过时”标记，或迁移到 `过时/`。

文档维护额外规则：
1. 当前导航和改前读包统一维护在 `docs/project-map/`。
2. `docs/daily-upgrade/` 只做时间线，不承担快速导航职责。
3. `docs/concepts/` 只保留长期原则、仍有效概念和接入说明；历史材料迁到 `docs/concepts/history/`。
