# research_manager

`research_manager/` 是 Butler 内研究业务主管的落点。

职责：

- 维护研究主题、项目状态、论文池等业务真源映射
- 选择并调度 `butler_main/incubation/research/units/` 中的标准动作
- 面向 orchestrator、talk、CLI 等入口提供统一研究推进能力

边界：

- 不重造 `agents_os` runtime core
- 不把研究 prompt 资产放进代码目录
- 不把通用 harness contract 写成 Butler 私有字段

## 当前最小架构

```text
orchestrator / talk / codex
  -> interfaces/*
    -> ResearchInvocation
      -> ResearchManager.invoke()
        -> services/unit_registry.py
          -> research units
```

当前意思是：

- `interfaces/` 只负责入口归一
- `manager.py` 只负责选 unit 与统一回执
- `services/unit_registry.py` 负责把 `unit_id` 映射到实际 handler

这样可以保证：

- 多入口
- 同一业务核
- 后续新增 API/webhook 时不破坏现有结构
