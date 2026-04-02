# 0320 工作区与 MyWorkSpace 重构及清理落地

## 目标

把 `工作区/` 从“混合文件池”收口成：

- 应用展示层
- 治理层
- 汇总层

同时把项目与研究空间拆到 `MyWorkSpace/`。

## 新结构

### `工作区/`

```text
工作区/
  Butler/
  Shared/
  Inbox/
  Archives/
  Recycle/
  README.md
  index.md
  heartbeat_upgrade_request.json
```

### `MyWorkSpace/`

```text
MyWorkSpace/
  Research/
  TargetProjects/
  MyProjects/
  Shared/
  Inbox/
  Archives/
  README.md
  index.md
```

## 长期规则

1. 过程态统一先写系统内控区 `task_workspaces/`。
2. `工作区/` 只承接 Butler 或其他应用的展示、治理、汇总、审批材料。
3. 研究、项目、BrainStorm 不再默认放进 `工作区/`。
4. `工作区/` 根目录禁止新增 Butler 运行散文件。
5. 语义重复、历史残留、暂不敢删的内容统一进 `Recycle/` 待人审。

## 0320 实际动作

1. 重写 `工作区/README.md` 与 `工作区/index.md`。
2. 新建 `工作区/Butler/README.md` 明确展示层边界。
3. 新建 `Desktop/MyWorkSpace/` 作为项目与研究空间。
4. 把 `Research/`、`TargetProjects/`、`MyProjects/` 迁到 `MyWorkSpace/`。
5. 把当前 `工作区/` 根层的旧目录、重复目录、散文件集中迁入 `Recycle/20260320_workspace_cleanup_review/`。
6. 给 Butler 注入新的 heartbeat workspace hint，明确：
   - 默认展示层写 `工作区/Butler/...`
   - 外部项目/研究写 `MyWorkSpace/...`
   - 过程态仍先写 `task_workspaces/`

## 当前兼容例外

- `heartbeat_upgrade_request.json` 仍暂留 `工作区/` 根层，作为现有代码与审批入口的兼容锚点。
- 后续 wave 再把它升级为 `工作区/Butler/governance/requests/` 并统一改引用。
