# 0402 Vibecoding Agent 默认收尾动作与 `vibe-close` 收口

日期：2026-04-02  
状态：已实施

关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [Project Map 入口](../../project-map/README.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)

## 1. 本轮目标

把 vibecoding agent 的“收尾动作”从临时口头约定升级成固定协议：

1. 每次改动结束后，先判断改动重量，而不是直接 `git commit`
2. 先回写最小真源文档，再做 git 收口
3. 重要改动默认保持 `branch / worktree / push` 最新，不把主工作区长期留在脏状态

## 2. 当前裁决

1. 默认收尾入口统一为 `./tools/vibe-close`，而不是让 agent 自己临时拼命令。
2. `vibe-close analyze` 是默认第一步，输出 JSON，供 agent 判断：
   - `change_level`
   - `doc_mode`
   - `doc_targets`
   - `requires_worktree`
   - `requires_push`
   - `suggested_commit_type`
   - `suggested_branch`
3. 当前改动分三级：
   - `light`
   - `normal`
   - `system`
4. 现役升级条件：
   - 命中多个主层级目录
   - 或任务本身是 plan-driven / 系统性升级
   - 或同时改 agent 协议 / project-map / tools 收口规则
   - 命中后按 `system` 收口
5. 文档回写分两档：
   - `minimal`：当天 `00_当日总纲.md` + 当天专题正文
   - `strict`：在 `minimal` 基础上，再补 `03_truth_matrix.md`、`04_change_packets.md`、`docs/README.md`
6. `system` 改动若当前在默认分支：
   - 先切到建议 branch
   - commit
   - 若存在 remote，则默认 push
   - 再创建同主题 sibling worktree
   - 最后把当前工作区切回默认分支，保持主工作区常干净
7. 若仓库没有 remote，push 只返回 `skipped`，不视为失败。
8. `vibe-close` 不代替 agent 写文档，它只负责把“本次必须回写哪里”变成明确的收尾合同。

## 3. agent 默认收尾协议

今后 agent 在 vibecoding 任务收尾时，默认按下面顺序执行：

1. 完成代码 / 文档 / 测试改动
2. 运行：
   - `./tools/vibe-close analyze`
   - 若任务是先计划再实施，补 `--planned`
3. 按 `doc_targets` 回写文档
4. 跑本次最小必要测试
5. 运行：
   - `./tools/vibe-close apply --topic <slug> --summary "<summary>"`
   - plan-driven 任务补 `--planned`
6. 最终回复必须包含：
   - `change_level`
   - 已回写文档
   - 测试
   - commit SHA
   - branch / worktree
   - push 结果
7. 若 `analyze.changed_paths` 明显混入与本轮目标无关的旧脏改动，agent 先报告，再决定是否继续收口，不允许盲目混提。

## 4. 代码与文档落点

- `AGENTS.md`
  - 新增 vibecoding 默认收尾协议
- `tools/vibe-close`
  - shell 入口
- `butler_main/vibe_close.py`
  - JSON analyze / apply / print-prompt 主逻辑
- `tools/README.md`
  - 把 `vibe-close` 收口为现役工具入口
- `docs/project-map/03_truth_matrix.md`
  - 增加“agent 默认收尾动作 / vibe-close 收口”真源条目
- `docs/project-map/04_change_packets.md`
  - 在 `docs-only` 读包里补 agent 协议与收尾工具

## 5. 当前实现口径

### 5.1 `analyze`

- 默认 stdout 为 JSON
- 用 `git diff` + `git ls-files --others --exclude-standard` 计算改动文件
- 不猜业务设计，只判断：
  - 改动命中了哪些主层级
  - 是否涉及文档治理 / 工具 / agent 协议
  - 本轮应该最小还是严格回写

### 5.2 `apply`

- 会执行：
  - `git add -A`
  - `git commit`
  - 条件满足时 `git push -u`
  - 条件满足时 `git worktree add`
- `system` 且当前位于默认分支时，现役动作是：
  - 在当前工作区切 branch 完成本次 commit
  - 新建 sibling worktree 挂载该 branch
  - 当前工作区切回默认分支

### 5.3 `print-prompt`

- 输出给 agent 直接复用的收尾提示模板
- 用于让 `AGENTS.md` 中的协议既有规则，也有现成工具输出

## 6. 验收

- `test_vibe_close.py`
  - 覆盖 docs/tool/agent 协议改动在 `--planned` 下升级为 `system`
  - 覆盖单层代码改动判定为 `normal`
  - 覆盖 `apply` 在默认分支下创建 branch、commit、worktree，并把当前工作区切回 `main`
  - 覆盖 CLI `analyze` 输出 JSON
