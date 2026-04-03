# 0403 仓库级重构实施稿：三产品 / Platform / Repo Governance

日期：2026-04-03
状态：已完成落地 / 0404 验收通过 / 当前真源
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
| 目标功能 | 把仓库级重构从“目录终态草图”推进到第一波真实代码实施：落 canonical tree，先迁 `butler-flow`，其余高耦合目录先保 compat 壳。 |
| 所属层级 | 仓库治理 / 跨层。 |
| 当前真源文档 | 仓库根 `README.md`、`docs/README.md`、`docs/project-map/02_feature_map.md`、`docs/project-map/03_truth_matrix.md`、`docs/project-map/04_change_packets.md`、`0403/03_跨机器开发仓库收口与私有层隔离.md`。 |
| 计划查看的代码目录和测试 | `butler_main/products/`、`butler_main/platform/`、`butler_main/compat/`、`butler_main/incubation/`、`butler_main/butler_flow/` compat 壳、`tools/butler-flow`；测试至少跑 `test_repo_product_namespace.py`、`test_butler_flow.py`、`test_butler_flow_surface.py`、`test_butler_flow_tui_app.py`、`test_butler_flow_tui_controller.py`、`test_chat_cli_runner.py`、`test_butler_cli.py`、`test_chat_module_exports.py`。 |

## 0. 本轮已落代码

`0404` 收口后，本稿对应实施已完成：

1. 已新增 canonical 目录树：
   - `butler_main/products/`
   - `butler_main/platform/`
   - `butler_main/compat/`
   - `butler_main/incubation/`
2. 已把以下目录真实迁移到 canonical tree：
   - `butler_main/butler_flow/ -> butler_main/products/butler_flow/`
   - `butler_main/chat/ -> butler_main/products/chat/`
   - `butler_main/orchestrator/ -> butler_main/products/campaign_orchestrator/orchestrator/`
   - `butler_main/console/ -> butler_main/products/campaign_orchestrator/console/`
   - `butler_main/domains/campaign/ -> butler_main/products/campaign_orchestrator/campaign/`
3. 已为旧入口补 compat 包或 compat 壳：
   - `butler_main/butler_flow/__init__.py`
   - `butler_main/butler_flow/__main__.py`
4. `platform/skills` 与 `incubation/research` 已完成 canonical-first 收口，不再依赖旧产品树定位。
5. `tools/butler-flow`、`butler_main/__main__.py`、`butler_main/butler_cli.py` 与测试入口已优先走 canonical tree。
6. `vibe_close` 已识别新目录前缀，避免收口时把 `products/platform/compat/incubation` 当成未知路径。

## 0.1 `0404` 收口结果：已关闭的主要路径隐患

本轮最终关闭的主要隐患如下：

### P0. `chat` 仍有物理路径合同，不能只靠 import alias 物理搬迁

代表文件：

- `butler_main/chat/pathing.py`
- `butler_main/chat/config_runtime.py`
- `butler_main/chat/prompting.py`
- `butler_main/chat/core_client.py`
- `butler_main/chat/feishu_bot/transport.py`

问题：

1. 仍大量把 `butler_main/chat/` 当成真实磁盘目录，而不是逻辑产品名。
2. 仍大量依赖 `Path(__file__).resolve().parents[...]` 推导 Butler 根目录。
3. prompt 与资产引用里仍会直接生成 `./butler_main/products/chat/...` 字面路径。

结论：

- 下一版若要真实迁 `chat -> products/chat`，必须先统一 path contract，不能只保留 `products/chat/__init__.py` alias 包。

### P0. `campaign + orchestrator` 仍与 host runtime 目录强耦合

代表文件：

- `butler_main/orchestrator/paths.py`
- `butler_main/orchestrator/runtime_paths.py`
- `butler_main/orchestrator/feedback_notifier.py`
- `butler_main/orchestrator/__init__.py`

问题：

1. 运行态目录仍固定写到 `butler_main/butler_bot_code/run/...`。
2. 包初始化仍显式把 `butler_bot_code/butler_bot` 注入 `sys.path`。
3. 根定位逻辑仍把 `chat / orchestrator / sources / butler_bot_code` 当成 `butler_main` 下现役兄弟目录。

结论：

- 下一版若要真实迁 `orchestrator / console / domains/campaign`，必须把“产品目录”和“host runtime 落盘目录”彻底拆开。

### P0. `sources/skills` 与其测试/注册表仍大量写死旧路径

代表文件：

- `butler_main/platform/skills/shared/workspace_layout.py`
- `butler_main/platform/skills/collections/registry.json`
- `butler_main/butler_bot_code/tests/test_skill_workspace_layout.py`
- `butler_main/butler_bot_code/tests/test_skill_registry.py`
- `butler_main/butler_bot_code/tests/test_skill_upstream_registry.py`

问题：

1. `skill_source_root()` 仍直接返回 `butler_main/platform/skills`。
2. 大量 registry、fixture、断言仍写死 `./butler_main/platform/skills/...`。
3. skill 工具脚本默认输出目录也仍写死旧树。

结论：

- 下一版若要真实迁 `sources/skills -> platform/skills`，必须在同一轮里一起改 runtime helper、registry 和测试。

### P1. `research` 已能被 canonical alias 包承接，但物理迁移前仍要先清旧路径

代表文件：

- `butler_main/incubation/research/manager/code/research_manager/services/scenario_registry.py`
- `butler_main/incubation/research/manager/code/research_manager/services/scenario_instance_store.py`
- `butler_main/incubation/research/manager/code/research_manager/contracts.py`

问题：

1. scenario registry 仍写死 `butler_main/incubation/research/...`。
2. instance store 仍靠固定父级层数回到 repo 根。

结论：

- `research -> incubation/research` 是可做的，但必须在同一轮补完 registry/path helper。

### P1. 工具链和文档收口逻辑仍保留旧树语义

代表文件：

- `butler_main/vibe_close.py`
- `tools/runtime_os_codemod.py`

结论：

- 下一版真实迁移不能只改业务代码；同一轮必须同步更新工具分类、默认扫描目录和收口口径。

### 当前正向结论

1. `products/butler_flow/`、`products/chat/`、`products/campaign_orchestrator/*` 已完成真实迁移。
2. `platform/skills` 与 `incubation/research` 已完成 path / registry / import / test 收口。
3. 旧路径保 compat 壳的组合已被现有回归覆盖。
4. `0404` acceptance 已证明这次限定范围内的“一次性跑完”成立。

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
| `butler_main/butler_flow/` | `products/butler_flow/` | 已真实迁移；旧路径保留 compat 包 |
| `butler_main/chat/` | `products/chat/` | 已真实迁移；旧路径保 compat 壳 |
| `butler_main/orchestrator/` | `products/campaign_orchestrator/orchestrator/` | 已真实迁移；旧路径保 compat 壳 |
| `butler_main/domains/campaign/` | `products/campaign_orchestrator/campaign/` | 已真实迁移；旧路径保 compat 壳 |
| `butler_main/console/` | `products/campaign_orchestrator/console/` | 已真实迁移；旧路径保 compat 壳 |
| `butler_main/butler_bot_code/` | `platform/host_runtime/` | 已落 canonical alias；物理目录暂不迁 |
| `butler_main/runtime_os/` | `platform/runtime/` | 已落 canonical alias；物理目录暂不迁 |
| `butler_main/agents_os/` | `compat/agents_os/` | 已落 canonical alias；物理目录暂不迁 |
| `butler_main/multi_agents_os/` | `compat/multi_agents_os/` | 已落 canonical alias；物理目录暂不迁 |
| `butler_main/platform/skills/` | `platform/skills/` | 现位即 canonical 主树；已完成 registry/test 收口 |
| `butler_main/incubation/research/` | `incubation/research/` | 现位即 canonical 主树；已完成 path/import 收口 |

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

当前回写：

- canonical `products/` 目录树已落
- `products/butler_flow/`、`products/chat/` 与 `products/campaign_orchestrator/*` 已真实承接现役代码
- 旧产品路径全部退为 compat surface

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

本轮实际执行到：

1. 文档和治理协议已先回写
2. canonical tree 与 compat alias 已落
3. `butler-flow`、`chat`、`campaign + orchestrator` 已完成真实物理迁移
4. `platform/skills`、`incubation/research` 已完成 canonical-first 收口
5. 旧路径当前只保 compat 与导入稳定面

## 7. 下一版一次性执行计划

这里的“一次性跑完”，定义为：

> 一次性完成 `butler_main/` 内部剩余主结构重构，使 canonical tree 成为真实主树；旧路径全部退为 compat 壳；但**不**在同一轮追求根目录 rename、root `runtime_os/` 退出、`tools/` 改名或 compat 完全删除。

### 7.1 本轮一次性跑完的明确范围

下一版要在同一轮里完成的物理迁移：

1. `butler_main/chat/ -> butler_main/products/chat/`
2. `butler_main/orchestrator/ -> butler_main/products/campaign_orchestrator/orchestrator/`
3. `butler_main/console/ -> butler_main/products/campaign_orchestrator/console/`
4. `butler_main/domains/campaign/ -> butler_main/products/campaign_orchestrator/campaign/`
5. `butler_main/platform/skills/ -> butler_main/platform/skills/`
6. `butler_main/incubation/research/ -> butler_main/incubation/research/`

下一版明确**不**在同一轮里做真实物理迁移的目录：

1. `butler_main/runtime_os/`
2. `butler_main/agents_os/`
3. `butler_main/multi_agents_os/`
4. `butler_main/butler_bot_code/`
5. 根目录 `runtime_os/`
6. 根目录 `tools/`
7. 根目录 `工作区/`
8. 根目录 `过时/`

理由：

- 这些目录当前承担 runtime / host-runtime / compat 主锚点，若与产品树一起全搬，会把“产品重构”和“平台兼容退出”两类高风险工作耦在同一轮。

### 7.2 下一版固定批次

下一版必须按下面批次一次性做完，不再拆成半迁移状态：

#### Batch A：先统一 path contract

目标：

- 把所有“目录位置事实”收口到少量 resolver / constants，不再散落在各产品模块里。

必须改的第一批文件：

1. `butler_main/chat/pathing.py`
2. `butler_main/orchestrator/paths.py`
3. `butler_main/platform/skills/shared/workspace_layout.py`
4. `butler_main/incubation/research/manager/.../scenario_registry.py`
5. `butler_main/incubation/research/manager/.../scenario_instance_store.py`

交付标准：

- 这些文件不再把 `chat / orchestrator / research / sources` 是否位于 `butler_main/` 下当作硬前提。

#### Batch B：再统一 registry / literal path / tool defaults

目标：

- 把 JSON、测试、脚本里所有“旧物理路径即真源”的字符串改成新 canonical 口径或兼容双写口径。

必须改的对象：

1. `sources/skills` collections/registry
2. `research` scenario registry / unit contracts
3. `test_agent_soul_prompt.py` 等直接断言 `./butler_main/products/chat/...`、`./butler_main/platform/skills/...` 的测试
4. `tools/runtime_os_codemod.py`
5. `butler_main/vibe_close.py`

交付标准：

- 字面路径不再阻止物理目录迁移。

#### Batch C：一次性做剩余物理搬迁

目标：

- 在 Batch A/B 完成后，一次性完成 `chat / campaign_orchestrator / skills / research` 的真实目录迁移。

动作：

1. 真实 `mv` 到 canonical tree
2. 原路径全部改为 compat 壳
3. 入口脚本与主 CLI 改为优先走 canonical tree

交付标准：

- `products/*`、`platform/skills`、`incubation/research` 成为真实主目录，而不是 alias 壳。

#### Batch D：清 canonical-first 的导入与文档

目标：

- 新代码默认看 canonical tree，旧路径只保兼容。

动作：

1. 调整受影响 import
2. 回写 `project-map`
3. 回写当日真源与专题正文

#### Batch E：统一验收与运行复核

目标：

- 同一轮完成后，不留下“代码搬了、功能没验”的半成品。

### 7.3 下一版最小验收矩阵

#### chat

- `test_chat_router_frontdoor.py`
- `test_talk_mainline_service.py`
- `test_chat_long_task_frontdoor_regression.py`
- `test_chat_engine_model_controls.py`
- `test_chat_cli_runner.py`
- `test_chat_module_exports.py`
- `test_agent_soul_prompt.py`
- `test_chat_recent_memory_runtime.py`

#### butler-flow

- `test_butler_flow.py`
- `test_butler_flow_surface.py`
- `test_butler_flow_tui_app.py`
- `test_butler_flow_tui_controller.py`
- `test_butler_cli.py`

#### campaign + orchestrator

- `test_orchestrator_campaign_service.py`
- `test_orchestrator_runner.py`
- `test_orchestrator_campaign_observe.py`
- `test_orchestrator_workflow_ir.py`
- `test_orchestrator_workflow_vm.py`

#### platform / compat / skills / research

- `test_runtime_os_namespace.py`
- `test_agents_os_wave1.py`
- `test_skill_workspace_layout.py`
- `test_skill_registry.py`
- `test_skill_upstream_registry.py`
- `test_skill_exposure.py`
- `test_research_scenario_runner.py`

### 7.4 下一版成败裁决

只有同时满足以下条件，才算“这次一次性跑完”：

1. `butler-flow`、`chat`、`campaign + orchestrator` 都已在 canonical tree 有真实主目录。
2. `platform/skills` 与 `incubation/research` 已真实承接现役代码。
3. 旧路径全部只剩 compat 壳，不再承载真实实现。
4. `runtime_os / agents_os / multi_agents_os / butler_bot_code` 仍保持现役位置，不强行在同轮退出。
5. 上述验收矩阵通过。
6. 文档真源完成回写。

### 7.5 下一版禁止事项

1. 不允许把 `runtime_os / agents_os / multi_agents_os / butler_bot_code` 的真实物理迁移混进同一轮。
2. 不允许在 path contract 未统一前先 `mv chat` 或 `mv orchestrator`。
3. 不允许只迁代码，不迁 registry / tests / tool defaults。
4. 不允许把“旧路径还能 import”误判成“物理迁移已经安全完成”。

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
