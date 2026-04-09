# Local Agent Protocol

本文件只服务于**在本仓库内执行工作的本地 agent**。

- 它负责：本地 agent 的最小读包、任务定位、收尾协议、文件落位纪律。
- 它不负责：GitHub / ChatGPT 网页端阅读入口；那部分统一看根 `README.md`。
- 它不是 butler-flow 的 ambient runtime authority；只有显式进入 `control_profile.repo_contract_paths` 时，才算 repo contract。

## 1. 文件定位与边界

- 仓库入口与网页端阅读壳：`README.md`
- 正式文档入口：`docs/`
- 当前导航层与改前读包：`docs/project-map/`
- 时间线与当日裁决：`docs/daily-upgrade/`

当前最小目录心智只保留这些：

- `butler_main/`
  - 主代码区；现役 canonical tree 统一收口在 `products/`、`platform/`、`compat/`、`incubation/`
- `docs/`
  - 唯一正式文档入口
- `runtime_os/`、`tools/`
  - 根级 compat / CLI surface，当前仍是现役入口
- `工作区/`
  - 进行中的工作材料
- `过时/`
  - 历史归档

## 2. 必读顺序与 fallback 规则

所有改动默认按下面顺序读取：

1. 根 `README.md`
2. `docs/README.md`
3. `docs/project-map/04_change_packets.md`
   - 先看其中“通用基础包”当前指向的 `00_当日总纲.md`
   - 若当天总纲已建立，优先读当天
   - 若当天总纲尚未建立，按 `04_change_packets.md` 当前标注的最新日更总纲执行，不要让入口失效
4. 再按最小导航继续：
   - `docs/project-map/00_current_baseline.md`
   - `docs/project-map/01_layer_map.md`
   - `docs/project-map/02_feature_map.md`
   - `docs/project-map/03_truth_matrix.md`
   - `docs/project-map/04_change_packets.md`
   - `docs/project-map/06_system_audit_and_upgrade_loop.md` 仅系统级排查/升级必读

不要自由扩散式扫 `docs/`、`docs/concepts/` 或整包按时间翻 `daily-upgrade/`。

文档冲突默认按下面顺序裁决：

1. `docs/project-map/` 当前条目
2. 最新 `00_当日总纲.md` 及其明确链接的当日真源
3. `docs/runtime/` 稳定合同文档
4. `docs/concepts/` 现役文档
5. `docs/concepts/` 兼容期资料
6. `docs/concepts/history/` 与其他历史文档

## 3. 任务定位流程

开始改前，先在回复里明确四件事：

- 目标功能
- 所属层级
- 当前真源文档
- 计划查看的代码目录和测试

然后按下面流程定位：

1. 先在 `01_layer_map.md` 判主层级
2. 再在 `02_feature_map.md` 命中功能条目
3. 最后按 `04_change_packets.md` 选最小必读包

若需求里出现旧词，先做历史别名映射再继续：

- `heartbeat`
- `guardian`
- `sidecar`

若问题跨 `frontdoor -> negotiation/query -> mission/campaign -> runner -> feedback`，或用户明确说“系统性不符合设计预期”，必须补读 `docs/project-map/06_system_audit_and_upgrade_loop.md`，先建链路矩阵，再开始改。

系统级升级固定按下面顺序收口：

1. 第一波并行
2. 再规划
3. 第二波并行
4. acceptance 与文档回写

## 4. 运行边界与 repo contract 规则

- 根 `AGENTS.md` 当前只服务仓库内本地 agent 的工作协议，不承担网页端导航职责。
- 在 butler-flow 中，repo contract 只在 `control_profile.repo_contract_paths` 显式绑定后生效。
- `repo_bound` 只表示执行位置，不再自动等于“继承仓库根 `AGENTS.md`”。
- 对非 `repo_bound` / `isolated` 的 flow，不要假设运行时天然会读到本文件。
- 若任务确实需要 repo 级约束，应显式绑定 repo contract 路径，而不是把本文件当 ambient authority。

运行时与 repo contract 的当前真源：

- `docs/daily-upgrade/0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md`
- `docs/daily-upgrade/0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md`

## 5. 修改、验证与 `vibe-close` 收尾

默认代码与文档约定只保留短规则：

- Python 使用 4 空格缩进
- 模块、函数、测试文件用 `snake_case`
- 类名用 `PascalCase`
- 测试框架默认是 `pytest`
- 自动化回归测试默认放 `butler_main/butler_bot_code/tests/test_*.py`
- 提交前缀默认用 `feat:`、`fix:`、`refactor:`、`chore:`、`test:`

从 `2026-04-02` 起，vibecoding 默认收尾顺序固定为：

1. 先完成代码、文档和测试改动
2. 运行 `./tools/vibe-close analyze`
   - 若本轮是“先计划再实施”的任务，补 `--planned`
3. 读取输出 JSON，按 `doc_mode` / `doc_targets` 回写文档
4. 跑本次最小必要验证
5. 运行 `./tools/vibe-close apply --topic <slug> --summary "<summary>"`
   - 若本轮是“先计划再实施”的任务，补 `--planned`

现役裁决：

- `vibe-close analyze` 只负责判断收口级别与文档目标，不代替 agent 写文档正文
- 若 `analyze.changed_paths` 明显混入与本轮无关的旧脏改动，先停下说明，不要盲目 `apply`
- `docs-only system` 仍按 `strict` 文档回写，但不默认创建 sibling worktree
- 跨层代码 `system` 升级才默认走 branch + worktree 收口
- 若仓库无 remote，push 返回 `skipped`，不视为失败

最终回复必须明确：

- `change_level`
- 已更新文档
- 已执行测试
- commit SHA
- branch / worktree / push 结果

## 6. 文档与文件落位纪律

- 不要把临时 `.md`、`.json`、`.txt` 或辅助脚本直接丢到仓库根目录
- 正式方案进 `docs/`
- 长期研究沉淀进 `BrainStorm/`
- 进行中的材料放 `工作区/` 或对应模块目录
- 退出主链路的历史材料放 `过时/`
- 新增内容前先看最近的 `README.md`，不要新开语义重复的顶层目录

文档职责固定为：

- `docs/project-map/`
  - 当前导航层与改前读包
- `docs/daily-upgrade/`
  - 时间线、当日裁决、阶段推进记录
- `docs/runtime/`
  - 稳定合同和复用接入
- `docs/concepts/`
  - 长期原则、仍有效概念、接入说明
- `docs/concepts/history/`
  - 历史材料；只用于追溯，不直接作为当前设计依据
