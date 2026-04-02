# 多Agent系统的Harness Engineering(中-1)（抓取前置阻塞记录）

- **platform**: xiaohongshu  
- **id**: `null`（explore 页首屏无可用 `noteId`）  
- **source_url**: `https://www.xiaohongshu.com/explore?keyword=%E5%A4%9AAgent%E7%B3%BB%E7%BB%9F%E7%9A%84Harness%20Engineering%28%E4%B8%AD-1%29`  
- **resolved_url**: （随请求最终 URL，未解析出单帖）  
- **author**: Simon（索引侧假定，待单帖页验证）  
- **published_at**: `~2026-03-12`（见 `index.md` §3.1）  
- **updated_at**: `2026-03-20`（executor 记录 · 本地复试时刻）  
- **engagement**: 主页列表可见点赞约 `33`（仅以索引为据）  
- **tags**: `MAS`, `Harness`, `中-1`

## 序列定位

对齐 `index.md` §3.1 **#3**（Harness 系列 · 中-1）；原态 **`未抓取`（无短链）**。本轮在仍无 `xhslink.com/o/...` 前提下，对 **explore 全标题关键词**做 **1 次**复试（heartbeat 单步上限）。

## Content

执行 `butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py`，`--platform xiaohongshu`，`--output-dir BrainStorm/Raw/Simon_agent_xhs_series`：

1. **关键词（完整标题 URL 编码）**  
   见上文 `source_url`。  
   - **结果**：`{"status":"error","message":"小红书页面已打开，但没有定位到 note_id。"}`  

**含义**：与 `index.md` §6.1 一致——列表/SSR 首屏未暴露与脚本一致的单帖 `noteId`，**入口 URL 类型非单帖分享页**；腾讯云合集 [2638304](https://cloud.tencent.com/developer/article/2638304) 为站外长文，**本 skill 默认不对 `cloud.tencent.com` 走 capture**。

## OCR / 结构化

- **OCR**：`ocr_not_started`（无 capture JSON）  
- **是否已结构化**：`no`

## Status

| 字段 | 值 |
| --- | --- |
| `capture_status` | `failed_precondition_missing_single_url` |
| `failure_bucket` | **短链**：缺 `xhslink.com/o/...`；**换路**：explore 全标题 1 路无 `note_id` |
| `next_retry_entry` | 用户粘贴该帖分享文案（含短链）→ `social_capture.py`；或浏览器打开腾讯云长文作补充真源（非本脚本默认路径） |
| `capture_tool` | `web-note-capture-cn`（`social_capture.py`） |
