# Raw 资料区说明

`Raw/` 现在按“资料类型”分三层：

- `daily/YYYYMMDD/`：按日期整理的人类可读 Raw 笔记
- 根目录平铺：平台抓取原件、`*_ocr.*`、少量无明确日期的兼容文件
- 专题子目录：长期系列资料，如 `Simon_agent_xhs_series/`

---

## 推荐放置规则

- 你或 agent 手工整理的一天资料汇总：
  - `Raw/daily/YYYYMMDD/YYYYMMDD_主题.md`
- 抓取脚本直接产出的平台文件：
  - `Raw/{platform}_{id}.md`
  - `Raw/{platform}_{id}.json`
  - `Raw/{platform}_{id}_ocr.md`
  - `Raw/{platform}_{id}_ocr.json`
- 图片资产：
  - `Raw/images/`
- 长期专题：
  - 进入独立子目录，不和 `daily/` 混放

---

## 一句话原则

- 有日期、有人整理、能按天回看：进 `daily/`
- 以平台 id 为主、偏脚本产物：留在 `Raw/` 根下
- 已经是一条长期系列：单独开专题目录