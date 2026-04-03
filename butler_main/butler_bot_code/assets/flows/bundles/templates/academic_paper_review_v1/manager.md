# Manager Notes · 论文四维评估

## Asset Identity
- asset_kind: template
- asset_id: academic_paper_review_v1
- goal: 对输入论文进行结构化学术评估，产出语言、成果、逻辑、学术内容四类分项结果，以及最终综合评估报告。
- guard_condition: 四类分项结果、A1-A4 学术内容子结论、加权综合结论和最终评估报告均已产出，且可以回溯到章节证据。

## Reuse Guidance
- 这是一个可复用的论文评审模板。默认应先在模板层明确评估框架，再为单次论文创建具体 flow。
- 如果用户只是想了解模板阶段、评审逻辑或静态字段，先解释，不要直接创建 flow。
- 如果用户这次的论文类型、输出格式或评估重点和默认模板不同，优先先改 template。

## Manager Checklist
- 创建 flow 前，先确认是否沿用这套“四维评估”模板，还是需要为特定论文类型做模板层调整。
- 若评审要求变化影响评估维度、阶段顺序或输出结构，应先修改 template，再创建 flow。
- 若本轮会影响 runtime 判断标准、输出口径或阶段侧重，检查 `supervisor.md` 是否也需要同步更新。
