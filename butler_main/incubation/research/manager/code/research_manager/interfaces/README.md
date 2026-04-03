# research_manager interfaces

这里放 `research_manager` 的入口壳层。

建议后续承接：

- `orchestrator_entry.py`
- `talk_bridge.py`
- `codex_cli_entry.py`

说明：

- 当前统一由 `orchestrator_entry.py` 承接后台编排入口。

接口层只负责收发与同步，不负责发明新 runtime。

## 兼容目标

这里当前承接三种主要入口：

1. `orchestrator_entry.py`
   - 编排层/后台调度触发
   - 适合 daily paper finding / project push
2. `talk_bridge.py`
   - 用户在 Butler 对话中显式触发
   - 适合“现在帮我找论文”“基于这篇论文推进项目”
3. `codex_cli_entry.py`
   - 在 Codex/CLI 中直接调 research 单元
   - 适合开发期、手工推进、单元冒烟

## 统一要求

三种入口都不应该直接把业务逻辑写进入口文件。

它们都应做同一件事：

1. 把外部请求归一成统一 invocation
2. 调 `research_manager`
3. 返回结构化结果或可读摘要

如果未来还要接 API / webhook，也应该继续放在这里，而不是回流到 `units/`。
