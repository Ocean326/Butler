---
name: memory-curation
description: 盘点、整理并修复 Butler chat 记忆资产，覆盖 recent/local memory 的 hot/cold 分层、legacy 路径残留、可疑编码污染、镜像冗余与归档整理建议。用于 recent memory 迁移后巡检、local memory 治理、历史路径批量清洗、记忆数据整理报告生成。
category: operations
family_id: memory-governance
family_label: Memory 治理族
family_summary: 面向 chat 记忆资产的盘点、清洗、巡检与整理建议。
family_trigger_examples: 整理记忆, 清洗记忆, memory curation, memory cleanup
variant_rank: 10
trigger_examples: 整理 recent/local memory, 修复历史记忆路径, 盘点 chat data, 清洗 memory 数据
allowed_roles: feishu-workstation-agent, butler-continuation-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: active
---

# Memory Curation

当需要治理 `butler_main/chat/data/` 下的记忆资产时，使用本 skill。

它的目标不是“生成更多记忆”，而是先把现有记忆资产盘清楚，再决定哪些应该保留、归档、去重、清洗或重写。

## 核心能力

1. 盘点 `hot/` 与 `cold/` 下的文件数量、体积和最大文件
2. 扫描历史遗留路径文本，确认是否还残留 `butler_bot_agent/agents/*` 或旧 `skills/` 路径
3. 识别明显可疑的编码污染或乱码文件
4. 检查 `hot/` 与 `hot/recent_memory/` 之间的镜像冗余
5. 生成可审阅的 JSON + Markdown 报告
6. 在显式允许时，调用已有清洗脚本做 legacy 路径批量重写

## 入口脚本

- `./butler_main/sources/skills/pool/ops/memory-curation/scripts/curate_memory.py`

## 标准用法

只做巡检和报告：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/ops/memory-curation/scripts/curate_memory.py' `
  --workspace '.' `
  --output-dir '工作区/memory-curation'
```

巡检后顺带执行 legacy 路径重写：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/ops/memory-curation/scripts/curate_memory.py' `
  --workspace '.' `
  --output-dir '工作区/memory-curation' `
  --rewrite-legacy-paths
```

## 产出

1. `工作区/memory-curation/memory_curation_report.json`
2. `工作区/memory-curation/memory_curation_report.md`

## 工作原则

1. 默认只读，先产出报告，再决定是否改写
2. 不把 `hot` 和 `cold` 混成一锅；要显式区分“热上下文”和“冷沉淀”
3. 报告中把“事实”与“建议动作”分开
4. 发现可疑乱码时，先标注文件与症状，不自动猜测性修复
5. 批量清洗路径时，优先复用已有脚本 `tools/cleanup_chat_data_legacy_paths.ps1`

## 重点检查项

1. `hot/recent_memory` 是否仍承担主要热数据真源
2. `hot/` 下是否还存在过时 recent 镜像目录或重复副本
3. `cold/local_memory` 下是否有过大的日志、未归档材料或结构漂移
4. 历史数据文本中是否仍引用 `butler_bot_agent/agents/`、legacy skills 路径或已废弃说明
5. 是否存在明显 UTF-8/ANSI 错解后的污染文本

## 注意事项

- 本 skill 的 `--rewrite-legacy-paths` 只做路径文本替换，不负责语义重写。
- 如果要进一步做“记忆归档/合并/去重/重写摘要”，应基于本 skill 报告再执行定向改动，而不是盲目批处理。

