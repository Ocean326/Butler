# Supervisor Notes · managed_template_plan-imp-review

- Preserve the flow goal: 创建一个可复用的 managed_flow 模板，在可控风险下完成从计划到实现再到验证复核的闭环交付。
- Respect the guard condition: 不执行破坏性操作，不跳过验证步骤；当实现与目标不一致或验证失败时，必须回退到实现阶段修复后再复核。
- Apply shared-asset management constraints before mutating local runtime state.
