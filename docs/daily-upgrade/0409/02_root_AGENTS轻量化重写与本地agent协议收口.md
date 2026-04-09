# 0409 Root `AGENTS.md` 轻量化重写与本地 agent 协议收口

日期：2026-04-09
状态：已落文档 / 当前真源
所属层级：仓库治理 / docs-only

关联：

- [0409 当日总纲](./00_当日总纲.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)
- [0402 Vibecoding Agent 默认收尾动作与 `vibe-close` 收口](../0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md)
- [0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决](../0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)
- [0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级](../0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)
- [0402 GitHub / ChatGPT 网页端阅读入口增强](../0402/10_github_chatgpt网页端阅读入口增强.md)
- [0403 仓库级重构实施稿：三产品 / Platform / Repo Governance](../0403/04_仓库级重构实施稿_三产品_platform_repo治理.md)

## 1. 问题

旧版根 `AGENTS.md` 同时混了三类职责：

1. 仓库结构与网页端阅读壳
2. 本地 agent 的改前读包与收尾协议
3. 容易被误读成 runtime 环境会天然继承的 repo 制度

结果是：

- 与根 `README.md`、`docs/project-map/` 出现大量重复
- 与 `04_change_packets.md` 的入口关系不够清楚
- 旧 PowerShell 风格命令块与当前实际环境不一致
- “当天 `00_当日总纲.md` 必然存在”的写法缺少 fallback
- 容易把根 `AGENTS.md` 误解成 butler-flow 的 ambient runtime authority
- 当前分支上的 `vibe_close.py` 也还停在旧策略，`docs-only system` 会被误判成需要 sibling worktree

## 2. 当前裁决

本轮把根 `AGENTS.md` 的现役定位固定为：

> **只服务仓库内本地 agent 的轻量路由协议。**

具体裁决如下：

1. 根 `README.md` 继续承担 GitHub / ChatGPT 网页端阅读壳。
2. `docs/project-map/` 继续承担当前导航层、真源矩阵与改前读包。
3. `docs/daily-upgrade/` 继续承担时间线与当日裁决。
4. 根 `AGENTS.md` 只保留：
   - 本地 agent 的最小读包
   - 任务定位流程
   - repo contract 边界提醒
   - `vibe-close` 默认收尾协议
   - 文件落位纪律
5. 根 `AGENTS.md` 不是 butler-flow 的 ambient runtime authority；只有显式进入 `control_profile.repo_contract_paths` 时，才算 repo contract。
6. 日更读取协议不再写成“当天总纲一定存在”；若当天总纲未建立，统一按 `docs/project-map/04_change_packets.md` 当前标注的最新总纲 fallback。

## 3. 新版 `AGENTS.md` 保留与删除

### 3.1 保留的现役内容

- 开始改前先明确四件事
- 旧术语映射入口
- 系统级审计与并行升级入口
- `vibe-close analyze -> 文档回写 -> 最小验证 -> vibe-close apply`
- 文档与文件落位纪律

### 3.2 删除或强压缩的内容

- 与根 `README.md` 重复的网页端阅读叙事
- 与 `project-map` 重复的深功能说明
- 长篇仓库目录解说
- 纯 Windows / PowerShell 风格命令示例
- 没有 fallback 的“当天总纲必须存在”写法

## 4. 新版结构

新版根 `AGENTS.md` 固定收成 6 个短章节：

1. 文件定位与边界
2. 必读顺序与 fallback 规则
3. 任务定位流程
4. 运行边界与 repo contract 规则
5. 修改、验证与 `vibe-close` 收尾
6. 文档与文件落位纪律

这份文件明确不再承担 feature 正文职责；深功能真源继续通过 `project-map` 与 `daily-upgrade` 跳转命中。

## 5. 本轮回写范围

- 根 `AGENTS.md`
  - 原地重写为轻量路由协议
- `0409/00_当日总纲.md`
  - 记录本轮 docs-only 补充结论
- `0409/02_root_AGENTS轻量化重写与本地agent协议收口.md`
  - 作为本专题当前真源
- `butler_main/vibe_close.py`
  - 补回 `docs_only_system` 的判定与 `requires_worktree=false` 的现役逻辑
- `butler_main/butler_bot_code/tests/test_vibe_close.py`
  - 补 docs-only system 与 code system 的回归
- `docs/project-map/03_truth_matrix.md`
  - 明确 `AGENTS.md` 是本地 agent 协议与收尾合同真源之一
  - 明确它不是 butler-flow 的 ambient runtime authority
- `docs/project-map/04_change_packets.md`
  - 在 `docs-only` 检查项中补 `AGENTS.md` 轻量协议、深功能跳转、显式 repo contract 与日更 fallback
- `docs/README.md`
  - 补 `0409/02` 入口与使用提示

## 6. 验收口径

文案验收：

1. 打开根 `AGENTS.md` 前半屏就能看懂它是什么、先读什么、什么不归它管、怎么收尾。
2. 根 `README.md` 继续承担网页端阅读入口壳，`AGENTS.md` 不再重复那套说明。
3. `AGENTS.md` 的 repo contract 表述与 `0403/01`、`0403/02` 当前真源一致。

结构验收：

1. 仓库中不新增 `agent.md`
2. 不改 `vibe-close` JSON 字段，只修正文档与当前实现的逻辑漂移
3. 不改 butler-flow 的 `repo_contract_paths` 运行语义

命令验收：

1. `git diff --check`
2. `./tools/vibe-close analyze --planned`
3. 期望结果：
   - `change_level=system`
   - `doc_mode=strict`
   - `requires_worktree=false`
