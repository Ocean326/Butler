---
name: discourse-topic-read
description: 读取 Discourse 最新话题或指定 topic，用于社区论坛公告、支持贴和讨论串整理。
category: forum
trigger_examples: 读discourse论坛, 社区公告抓取, discourse topic, 官方论坛整理
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: active
source_candidate_id: discourse-api-monitor
upstream_name: Discourse API
upstream_repo_or_entry: https://meta.discourse.org/t/discourse-rest-api-documentation/22706
---

# discourse-topic-read

这个 skill 是由 incubating 候选 `discourse-api-monitor` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: Discourse API
- repo or entry: https://meta.discourse.org/t/discourse-rest-api-documentation/22706
- docs: https://meta.discourse.org/t/discourse-rest-api-documentation/22706
- original candidate path: ./butler_main/sources/skills/pool/incubating/forum/discourse-api-monitor

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/forum/discourse-topic-read/scripts/run.py' `
  --base-url 'https://meta.discourse.org' --limit 5 --output-dir '工作区/Butler/runtime/skills/discourse-topic-read'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

