# Tools

`tools/` 是仓库根目录的现役脚本入口，不是临时脚本堆放区。

## 当前分类

### 现役 CLI 入口

- `butler`
  - 仓库内后台 / chat / manager 统一入口
- `butler-flow`
  - 前台 workflow shell / butler-flow CLI 入口
- `flow-desktop`
  - 直达 Butler Flow Desktop launcher 的仓库内入口；缺正式配置时会经 `butler-flow` 自动生成 machine-local bootstrap config
- `install-butler-flow`
  - 把 `butler-flow` / `flow-desktop` 安装到 `~/.local/bin/`
- `vibe-close`
  - 给 vibecoding agent 用的默认收尾入口：分析改动重量、给出文档回写目标，并执行 commit / push / worktree 收口

### 运维 / 联通脚本

- `console-relay-179`
  - 内网 console 反向代理 / relay 辅助脚本

### 审计 / 迁移辅助脚本

- `orchestrator_layer_audit.py`
  - 检查 orchestrator 分层壳与接口导入边界
- `runtime_os_codemod.py`
  - `agents_os` / `multi_agents_os` 到 `runtime_os` 的迁移辅助 codemod

## 维护规则

1. 只有现役 CLI、运维脚本、审计脚本允许长期留在 `tools/`
2. 一次性排障脚本和临时输出不要直接落到 `tools/`
3. 新增脚本时，必须同步更新本文件，写清是否现役、用途和边界
4. 若脚本已退役，优先迁到 `过时/` 或对应专题目录，而不是继续留名占位
