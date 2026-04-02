---
name: web-article-extract
description: 抓取普通网页正文并生成结构化摘录，优先用于博客、公告页、论坛正文页和研究页的轻量提取。
category: general
trigger_examples: 网页正文提取, 抓一篇文章, 网页清洗, 博客页面抓取
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: true
requires_skill_read: true
status: active
source_candidate_id: trafilatura-web-extract
upstream_name: Trafilatura
upstream_repo_or_entry: https://github.com/adbar/trafilatura
---

# web-article-extract

这个 skill 是由 incubating 候选 `trafilatura-web-extract` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: Trafilatura
- repo or entry: https://github.com/adbar/trafilatura
- docs: https://trafilatura.readthedocs.io/en/latest/
- original candidate path: ./butler_main/sources/skills/pool/incubating/general/trafilatura-web-extract

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/general/web-article-extract/scripts/run.py' `
  --url 'https://example.com/post' --output-dir '工作区/Butler/runtime/skills/web-article-extract'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

