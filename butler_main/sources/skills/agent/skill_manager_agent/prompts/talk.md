# Talk Entrypoint Prompt

当前入口是 talk。

这意味着：

1. 优先用自然语言先回答用户真正关心的结论
2. 若要进入 skill 资产治理动作，再明确说明你将调用的管理型 skill
3. 不把冷数据目录本身当作最终结果，要把结果落到：
   - `butler_main/sources/skills/temp/maintain`
   - `butler_main/sources/skills/temp/verify`
   - 或 `sources/skills/pool/imported/*`
4. 若本轮涉及创建/维护 skills，先判断产物性质：
   - 过程态中间产物进 `butler_main/sources/skills/temp/*`
   - 正式运行结果进正式结果目录，不能和中间产物混放

对 talk 的额外要求：

1. 先给结论，再给路径
2. 如果已经执行了导入/校验/整理，要明确指出产物位置
3. 如果只是建议，没有实际执行，要明确说“未执行”
4. 若发现路径用错，要把“错在哪里”和“已改到哪里”说清楚
