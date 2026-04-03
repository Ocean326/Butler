# Manager Notes · managed_template_plan-imp-review

## Asset Identity
- asset_kind: template
- asset_id: template_flow_20260402035457_a942afd7
- goal: 创建一个可复用的 managed_flow 模板，在可控风险下完成从计划到实现再到验证复核的闭环交付。
- guard_condition: 不执行破坏性操作，不跳过验证步骤；当实现与目标不一致或验证失败时，必须回退到实现阶段修复后再复核。

## Reuse Guidance
- 适合计划→实现→复核的通用交付任务。
- 新需求默认先看是否可复用该模板，再决定是否只做 template 轻改。

## Manager Checklist
- 在实例化前先确认：本轮目标、验收条件、phase 名称与职责是否仍适合 plan-imp-review 主骨架。
- 如果用户需要更强的研究/探索阶段或更细的验证环节，先改 template 再建 flow。
- 若 phase 责任或验收口径变化明显，检查 `supervisor.md` 同步。
