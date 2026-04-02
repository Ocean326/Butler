---
name: skill-library-explore
description: 从公开技能库与代码仓库（GitHub / PyPI / npm / Skills.sh）搜索可复用工具或 skill，产出结构化探索报告（含安全审阅要点）。用于 Butler 缺能力时"先找轮子再造轮子"的首轮探索。
category: research
family_id: skill-discovery
family_label: Skill 发现族
family_summary: 在公开技能库、代码仓库和包生态中搜索可复用能力，给后续导入或自建提供线索。
family_trigger_examples: 找个技能, 找轮子, 搜技能库
variant_rank: 10
trigger_examples: 找个技能, 有没有能做X的skill, 从技能库搜, 找个Python库处理XX, explore skills
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
---

# Skill Library Explore

当 Butler 需要新能力（skill / 工具 / 库）时，先用本 skill 做多源搜索和初步安全评估，再决定是否引入。

## 本 skill 的边界

- 只做**只读搜索和报告生成**，不自动安装任何依赖。
- 搜索走公开 API（GitHub REST / PyPI JSON / npm Registry / Skills.sh），无需鉴权。
- 产出为结构化 JSON + 可读 Markdown 报告，包含安全审阅要点（许可证、star 数、活跃度、依赖量）。
- 不替代人工审阅决策；报告是"线索"，引入需走正常审批。

## 入口脚本

- 脚本路径：`./butler_main/sources/skills/pool/chat/skill-library-explore/scripts/explore.py`
- 运行方式：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/chat/skill-library-explore/scripts/explore.py' `
  --query '图片OCR识别' `
  --output-dir 'butler_main/sources/skills/temp/explore'
```

## 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--query` | 是 | 搜索关键词（中文会自动补充英文同义词） |
| `--sources` | 否 | 搜索源，逗号分隔，默认 `github,pypi,npm` |
| `--limit` | 否 | 每个源返回的最大结果数，默认 5 |
| `--output-dir` | 否 | 输出目录，默认 `butler_main/sources/skills/temp/explore` |
| `--lang` | 否 | 偏好语言过滤（如 `python`），仅 GitHub 生效 |

## 输出

脚本在 `--output-dir` 下生成：

- `explore_<timestamp>.json`：结构化结果
- `explore_<timestamp>.md`：可读报告

每条结果包含：

- `source`：来源（github / pypi / npm）
- `name`：包名 / 仓库名
- `description`：简述
- `url`：链接
- `popularity`：star 数 / 下载量
- `license`：许可证
- `last_updated`：最后更新时间
- `safety_notes`：自动安全评估要点

## 使用场景

1. **后台自我升级**：planner 识别到能力缺口 → 安排 executor 用本 skill 搜索 → 报告回传 planner 决策是否引入。
2. **用户对话**：用户说"找个能做 X 的工具" → agent 用本 skill 搜索 → 向用户展示候选。
3. **补能力闭环**：搜索 → 安全审阅 → 落地为本地 skill 或 MCP → 回到原任务重试。

## 与 skills.md 的关系

本 skill 覆盖了 `skills.md` 中提到的 `openclaw-find-skills` 场景，并扩展到更通用的多源搜索。

