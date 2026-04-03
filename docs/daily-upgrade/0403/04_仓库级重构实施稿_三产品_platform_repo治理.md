# 0403 仓库级重构实施稿：三产品 / Platform / Repo Governance

日期：2026-04-03  
状态：实施稿 / 未落代码  
所属层级：文档治理 / 仓库治理

关联：

- [0403 当日总纲](./00_当日总纲.md)
- [仓库级重构远景规划（产品 / Platform / Repo Governance 版）](../../远景草稿/仓库级重构.md)
- [0331 根目录归档整理收口](../0331/05_根目录归档整理收口.md)
- [0402 Vibecoding Agent 默认收尾动作与 `vibe-close` 收口](../0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md)
- [跨机器开发仓库收口与私有层隔离](./03_跨机器开发仓库收口与私有层隔离.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 把仓库级重构从“目录终态草图”改成可分波执行的实施稿，明确三产品、platform 与 repo governance 的分工，并给出目录迁移顺序与验收口径。 |
| 所属层级 | 仓库治理 / docs-only / 跨层。 |
| 当前真源文档 | 仓库根 `README.md`、`docs/README.md`、`docs/project-map/03_truth_matrix.md`、`docs/project-map/04_change_packets.md`、`0403/03_跨机器开发仓库收口与私有层隔离.md`。 |
| 计划查看的代码目录和测试 | 代码只做目录映射参考：`butler_main/`、`tools/`、根 `runtime_os/`；本轮不改代码，不跑功能测试。 |

## 1. 一句话实施裁决

仓库级重构的实施顺序固定为：

> 先固定三产品与 repo governance 叙事，再做 `butler_main/` 内部产品 / platform / compat 归类，最后才处理根目录 compat surface 和候选命名。

本稿固定的三条并列产品线：

1. `butler-flow`
2. `chat`
3. `campaign + orchestrator`

本稿固定的 repo governance plane：

- 根 `AGENTS.md`
- `docs/project-map/`
- `tools/vibe-close`
- cross-machine / private overlay / runtime artifact 边界

## 2. 当前现状与实施边界

## 2.1 当前必须承认的现役事实

1. 根目录 `runtime_os/` 仍是现役 compatibility surface。
2. 根目录 `tools/` 仍是现役 CLI / 运维 / 审计入口。
3. 根目录 `工作区/`、`过时/` 仍是现役目录名。
4. `butler_main/butler_bot_code/` 仍承载后台 Butler 运行体、配置、run/tests。
5. `agents_os/`、`multi_agents_os/` 仍是兼容期核心目录。

## 2.2 本稿明确不做

1. 不把根目录 `runtime_os/` 直接写成第一波删除对象。
2. 不把 `tools/`、`工作区/`、`过时/` 直接改名。
3. 不在第一波重写所有 import path。
4. 不在第一波调整所有运行脚本与安装入口。
5. 不把 `campaign + orchestrator` 提前降格为 legacy。

## 3. 结构实施的目标图

## 3.1 仓库顶层

第一阶段保持当前现役根目录名不动，只强化职责：

```text
Butler/
├─ README.md
├─ AGENTS.md
├─ docs/
├─ butler_main/
├─ runtime_os/
├─ tools/
├─ 工作区/
└─ 过时/
```

顶层职责固定为：

- `README.md` / `AGENTS.md`
  - 仓库入口与 agent 治理入口
- `docs/`
  - 正式文档与导航
- `butler_main/`
  - 程序主体
- `runtime_os/`、`tools/`
  - 根级 compat / CLI 入口
- `工作区/`、`过时/`
  - 活跃工作区与归档区

## 3.2 `butler_main/` 内部远景结构

后续多波迁移的内部目标结构固定为：

```text
butler_main/
├─ products/
│  ├─ butler_flow/
│  ├─ chat/
│  └─ campaign_orchestrator/
├─ platform/
│  ├─ host_runtime/
│  ├─ runtime/
│  ├─ execution/
│  ├─ durability/
│  ├─ protocols/
│  ├─ skills/
│  ├─ storage/
│  ├─ shared_assets/
│  └─ common/
├─ compat/
│  ├─ runtime_os/
│  ├─ agents_os/
│  └─ multi_agents_os/
└─ incubation/
   └─ research/
```

## 3.3 当前目录到目标结构的实施映射

| 当前目录 | 目标归属 | 实施说明 |
| --- | --- | --- |
| `butler_main/butler_flow/` | `products/butler_flow/` | 第一条产品线，优先搬 |
| `butler_main/chat/` | `products/chat/` | 第二条产品线，优先搬 |
| `butler_main/orchestrator/` | `products/campaign_orchestrator/` | 第三条产品线外壳 |
| `butler_main/domains/campaign/` | `products/campaign_orchestrator/` | 第三条产品线领域真源 |
| `butler_main/console/` | `products/campaign_orchestrator/` | 第三条产品线 operator surface |
| `butler_main/butler_bot_code/` | `platform/host_runtime/` | 运行体与服务包装层 |
| `butler_main/runtime_os/` | `platform/runtime/` | 现役 runtime 主体 |
| `butler_main/agents_os/` | `compat/agents_os/` | 兼容层 |
| `butler_main/multi_agents_os/` | `compat/multi_agents_os/` | 兼容层 |
| `butler_main/sources/skills/` | `platform/skills/` | skill 真源 |
| `butler_main/research/` | `incubation/research/` | 研究/孵化目录 |

## 4. Repo Governance Plane 的实施口径

“避免 vibe coding 后仓库变乱”的能力，不在产品树里解决，而在仓库治理层固定下来。

必须先固化的治理对象：

1. 根 `AGENTS.md`
   - 改前读包
   - 术语裁决
   - 文档冲突顺序
   - vibecoding 默认收尾动作
2. `docs/project-map/`
   - 功能地图
   - 真源矩阵
   - 改前读包
3. `tools/vibe-close`
   - `analyze -> doc_targets -> apply`
4. 仓库分发边界
   - `.gitignore`
   - `.env.example`
   - `.codex/config.template.toml`
   - runtime artifact / private overlay 隔离

仓库级硬规则：

1. agent 新增文件前，必须先判断它属于产品、platform、governance、工作区还是归档。
2. 运行态实例、machine-local 配置、私有层记忆，不得再混入版本库。
3. 文档回写必须优先更新 `project-map` 与当日真源，而不是只写一份孤立计划。
4. 目录迁移必须晚于边界裁决和导航收口。

## 5. 分波次实施方案

## Wave 0：叙事定型

目标：

- 固定三产品并列
- 固定 platform 不是产品
- 固定 repo governance plane 不属于任何单一产品

动作：

- 重写远景稿
- 补实施稿
- 回写 `docs/README.md`、`03_truth_matrix.md`、`04_change_packets.md`

验收：

- 新读者读完文档后，能说清 Butler 不是“单产品 + 一堆底座”

## Wave 1：根目录治理面收口

目标：

- 让根目录首先成为“仓库入口 + agent 治理入口”

动作：

- 固定根目录保留项
- 补根 `AGENTS.md`、`project-map/`、`vibe-close` 的互相引用
- 固化 `.env.example`、`.codex/config.template.toml`、runtime artifact 边界

验收：

- 新 agent 不需要全文扫库，也能知道读什么、改哪里、不能提交什么

## Wave 2：`butler_main/` 内部产品分层

目标：

- 先把三产品的目录边界讲清楚，再开始物理迁移

动作：

- 以 `products/` 为目标树整理：
  - `butler_flow`
  - `chat`
  - `campaign_orchestrator`
- 同步明确 `console` 归第三产品线

验收：

- 任何产品相关改动，都能一跳定位到单条产品线

## Wave 3：platform / compat 分层

目标：

- 把共享能力和兼容能力从产品树里拆出来

动作：

- 收口 `platform/`
- 收口 `compat/`
- 明确 `butler_bot_code` 的 host runtime 地位
- 明确 `research` 的 incubation 地位

验收：

- runtime / execution / durability / protocol / skill 相关改动不再先去产品目录里找

## Wave 4：根级 compat 与命名清理

目标：

- 在结构稳定后，再清根级 compat surface 和候选命名

动作：

- 视 compat 状态决定是否退出根 `runtime_os/`
- 视工具入口状态决定是否把 `tools/` 迁成 `scripts/`
- 视工作区治理状态决定是否把 `工作区/`、`过时/` 迁成英文命名

前置条件：

- import 兼容、CLI 入口、文档导航、测试路径都已稳定

验收：

- 根目录变薄，但不丢 compat 能力、不丢 agent 治理入口

## 6. 具体执行顺序

后续真正进入代码和目录实施时，顺序固定为：

1. 先做文档和治理协议回写
2. 再做目录 alias / compat 桥接
3. 再做物理目录搬迁
4. 再做 import path 清理
5. 最后清旧 alias 和候选目录名

禁止的错误顺序：

1. 先 rename 根目录
2. 先删根 `runtime_os/`
3. 先把 `tools/` 写成历史目录
4. 先把 `campaign` 写成 legacy

## 7. 验收口径

仓库级重构每一波都至少要满足以下验收：

1. 文档导航能一跳命中当前真源与目标目录。
2. agent 可以根据根 `AGENTS.md` 判断文件落位、文档回写和收尾协议。
3. runtime artifact / private overlay 边界不回退。
4. 不把未来候选命名写成当前事实。
5. 不把三条产品线重新混成“大而全主工程”。

## 8. 最终口径

仓库级重构真正要收口的，不是“目录看起来更像成熟项目”，而是三件事：

1. **产品清楚**
   - `butler-flow`
   - `chat`
   - `campaign + orchestrator`
2. **平台清楚**
   - runtime / execution / durability / protocol / skills / host runtime
3. **agent 治理清楚**
   - 根 `AGENTS.md`
   - `docs/project-map/`
   - `tools/vibe-close`
   - 分发边界与 runtime artifact 边界

只有这三件事成立，后面的文件树重构才不会再次把仓库带回“vibecoding 后变乱”的状态。
