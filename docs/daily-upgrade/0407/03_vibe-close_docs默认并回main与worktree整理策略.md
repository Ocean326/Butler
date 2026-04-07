# 0407 vibe-close：docs 默认并回 `main` 与 worktree 整理策略

日期：2026-04-07  
状态：已落代码 / 当前真源  
所属层级：仓库治理 / docs-only + tool policy

关联：

- [0407 当日总纲](./00_当日总纲.md)
- [0402 Vibecoding Agent 默认收尾动作与 `vibe-close` 收口](../0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)
- [`butler_main/vibe_close.py`](../../../butler_main/vibe_close.py)

## 1. 问题

当前 `vibe-close` 的现役策略是：

- 只要命中 `system`
- 且当前在默认分支
- 就默认创建 branch + sibling worktree

这在跨层代码施工时是合理的，但用于 docs-only 系统收口时会带来两个问题：

1. 文档留痕 worktree 会快速累积，形成噪音
2. docs-only 分支明明已经 push 且 clean，仍长期占据本地施工面

## 2. 当前裁决

从本轮开始，把 `system` 再拆成两类：

1. `docs-only system`
   - 仍按 `system` 做严格文档回写
   - 仍可默认 `commit / push`
   - 但不再默认创建 sibling worktree
   - 若当前在 `main`，允许直接把 docs-only 收口并回 `main`
2. `code system`
   - 继续保持现有策略
   - 在默认分支时切建议 branch
   - commit
   - push
   - 创建 sibling worktree
   - 当前工作区切回默认分支

## 3. `docs-only system` 的判定口径

当前口径是：

- `change_level == system`
- 没有命中 `matched_layers`
- `matched_features` 全部属于：
  - `agent-protocol`
  - `docs-governance`
  - `docs-daily`
  - `docs`
  - `repo-root`

补充裁决：

- `tools/README.md` 视作文档治理面，归到 `docs-governance`
- 只要命中真实代码层、运行时层或工具实现层，就不再视为 `docs-only system`

## 4. 当前实现变化

### 4.1 `analyze`

- 保留原有 `light / normal / system`
- 但新增 `docs_only_system` 内部判定
- `doc_mode` 仍保持 `system -> strict`
- `requires_worktree` 改为：
  - `system and not docs_only_system`

### 4.2 `apply`

由于 `apply_closeout()` 原本只在 `requires_worktree=true` 时才：

- 切 branch
- 建 worktree

因此这次改动后：

- docs-only `system` 在默认分支上会直接 commit
- 若存在 remote，继续按原逻辑 push
- 不再自动创建 sibling worktree

## 5. worktree 整理策略

当前本地 worktree 之后按下面规则治理：

1. `main`
   - 永远保留
2. 活跃实现 worktree
   - 默认只保留 1 个主施工面
3. 临时评审 / 落地 worktree
   - 最多再保留 1 个
4. docs-only worktree
   - 一旦内容已并回 `main` 且分支 clean/pushed，优先移除，不再长期保留
5. `~/.codex/worktrees/*`
   - 视为工具内部态，不计入人工 worktree 预算

## 6. 本轮现场处理

本轮现场的目标是：

1. 把 `0407` docs worktree 的成果并回 `main`
2. 让未来 docs-only 系统收口不再默认开新 tree
3. 再清理本地 docs-only worktree

当前已完成：

- `chore/canonical-team-runtime-finalization`
  - 内容已被后续 `main` 吸收
  - 对应 docs worktree 已移除
- `chore/canonical-team-runtime-roadmap-refine`
  - 内容已并回 `main`
  - 对应 docs worktree 已移除

## 7. 验收

- `test_vibe_close.py`
  - docs-only `system` 仍判为 `system`
  - docs-only `system` 不再要求 `requires_worktree`
  - 跨层代码 `system` 仍保持原 worktree 行为
- `AGENTS.md`
  - 已把新策略回写为现役协议
- `0402/09`
  - 已把这次策略变化补回稳定真源
