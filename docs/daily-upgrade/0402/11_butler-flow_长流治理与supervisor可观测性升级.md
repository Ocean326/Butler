# 0402 Butler Flow 长流治理与 supervisor 可观测性升级

日期：2026-04-02  
状态：已实施

## 1. 目标

- 让 supervisor stream 可读、可审计：明确展示 **Input / Output / Decision**。
- 让 heuristic supervisor 也能看到合成的 input/output 记录，避免只剩 decision。
- Transcript 过滤器增加 `supervisor`，但不影响现有 `all/assistant/system/judge/operator` 行为。

## 2. 本轮裁决

1. supervisor stream 必须显式输出 `input / output / decision` 三段式事件。
2. heuristic supervisor 也要补齐合成的 `input / output` 事件。
3. supervisor raw output 统一在流式界面标记为 `[supervisor/output]`。
4. Transcript filter 新增 `supervisor` 类别，不改变其他过滤器语义。

## 3. TUI 行为变化

- supervisor stream 新增：
  - `supervisor_input`：来自 `supervisor_decision.instruction`。
  - `supervisor_output`：基于 decision 摘要合成的 output；LLM supervisor raw output 仍可见。
  - `supervisor_decided`：保留 decision 事件与 reason。
- `/filter` 支持 `supervisor`，settings 中同样可轮换。

## 4. 代码落点

- `butler_main/butler_flow/tui/controller.py`
  - supervisor input/output 合成事件注入 timeline。
  - supervisor raw output 统一归类到 `output` family。
- `butler_main/butler_flow/tui/app.py`
  - transcript filter 增加 `supervisor`。
  - 事件分类与 tone 逻辑补齐 `input/output`。
- `butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py`
  - 覆盖 supervisor input/output 合成事件。
- `butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py`
  - supervisor raw output 分组展示更新。

## 5. 验收与回归

- 建议回归：
  - `python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py -q`
  - `python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py -q`
- 关注点：
  - supervisor stream 是否稳定输出三段式事件。
  - heuristic supervisor 是否有合成 input/output。
  - filter `supervisor` 是否可用且不影响其它 filter。
