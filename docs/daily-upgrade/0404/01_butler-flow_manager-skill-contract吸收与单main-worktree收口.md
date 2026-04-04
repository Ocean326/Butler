# 0404 Butler Flow manager skill-contract 吸收与单 `main` worktree 收口

日期：2026-04-04
状态：已落代码 / 已验收 / 当前真源
所属层级：L1 `Agent Execution Runtime` + 仓库治理

## 1. 本轮目标

把根工作区尚未提交的 `butler-flow` manager chat 改动安全吸收到 canonical `main`，同时完成本轮文档迁移与仓库收口前置动作：

1. 把旧物理路径 `butler_main/butler_flow/manage_agent.py` 上的脏改动移植到现役 `butler_main/products/butler_flow/manage_agent.py`
2. 同步把对应测试与 `0402` 正文补齐
3. 把 `docs/每日/0403` 迁到 `docs/每日头脑风暴/0403`
4. 清掉迁移后残留的旧路径引用，避免另一台机器继续开发时命中失效文档路径
5. 以“根目录最终回到唯一 `main` worktree”为收口目标，先完成可提交状态

## 2. 代码侧吸收裁决

manager chat 本轮继续收口到“代码机制优先”：

- `manager skill registry` 成为当前 skill scope / target / draft ownership / action capability 的真源
- prompt payload 改为轻量 `current_target_summary + asset_catalog + session/draft/pending_action summary`
- `references/` 改为按 skill 按需注入，不再把完整 asset definition / bundle manifest 整包塞入上下文
- `draft` 合并前按当前 skill 的 ownership 过滤
- `action=manage_flow` 在 app 层进入提交前，会先过 skill contract validator；`discuss` skill 不再越权准备 mutation
- 若 session 已进入 `confirmation_scope=template|flow`，skill 选择优先沿用当前确认语义，而不是被表面 instruction 误切回其他阶段

## 3. 文档与路径迁移裁决

- `docs/每日/0403` 现统一迁到 `docs/每日头脑风暴/0403`
- 抓取素材、handoff 与引用路径已同步改成新目录
- 0403 脑暴/资料稿不再继续写回旧 `docs/每日/` 落点
- 继续开发与跨机器同步时，`docs/每日头脑风暴/` 只承接研究/脑暴材料，不替代 `daily-upgrade/` 的正式真源职责

## 4. 影响文件

- `butler_main/products/butler_flow/manage_agent.py`
- `butler_main/butler_bot_code/tests/test_butler_flow.py`
- `docs/daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md`
- `docs/每日头脑风暴/0403/`
- `docs/project-map/03_truth_matrix.md`
- `docs/project-map/04_change_packets.md`
- `docs/README.md`

## 5. 验收

- `/home/ocean/Desktop/SuperButler/.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow.py -q`
- `/home/ocean/Desktop/SuperButler/.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_chat_cli_runner.py -q`
- `/home/ocean/Desktop/SuperButler/.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py -q`
- `/home/ocean/Desktop/SuperButler/.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py -q`
