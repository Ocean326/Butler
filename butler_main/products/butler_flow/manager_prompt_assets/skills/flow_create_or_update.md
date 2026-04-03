技能：创建或更新 flow

适用场景：
- 用户已经明确确认了这次 flow 层动作

你要做的事：
- 简短重述：
  - 这次 flow 锚定哪个 template
  - 本次 run 的最终目标是什么
  - 这次交付给 supervisor 的控制画像是什么
  - 现在即将执行什么 mutation
- 如果这是一次性 one-off 路径，要明确说出来

阶段建议：
- 在确认落地前通常仍显示 `flow_confirm`
- 只有真正 ready 执行时才进入 `done`

动作建议：
- 设置 `action=manage_flow`
- 只有在 flow 层明确确认后，才设置 `action_ready=true`
- 新建 flow 用 `action_manage_target=new`
- 更新 flow 用具体实例 key
