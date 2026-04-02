# Magentic-One想到的agent验证外部化（抓取前置阻塞记录）

- **platform**: xiaohongshu  
- **id**: `null`（explore 页首屏无可用 `noteId`）  
- **source_url**: `https://www.xiaohongshu.com/explore?keyword=…`（见下文复试条目）  
- **resolved_url**: （随请求最终 URL，未解析出单帖）  
- **author**: Simon（索引侧假定，待单帖页验证）  
- **published_at**: `~2026-03-17`（见 `index.md` §3.1）  
- **updated_at**: `2026-03-20T12:00:00+08:00`（executor 记录，本地时钟）  
- **engagement**: 主页列表可见点赞约 `3`（仅以索引为据）  
- **tags**: `agent`, `Magentic-One`, `验证外部化`

## 序列定位（相对 2025-07 锚点）

对齐 `index.md` §3.1 **#1**（主页新→旧第一条 Agent 向帖）；索引态原为 **`pending_xhslink`**（缺 `http://xhslink.com/o/...`）。本轮在仍无分享短链前提下，按 `web-note-capture-cn` 对 **explore 关键词**做复试。

## Content

本轮执行 `skills/web-note-capture-cn/scripts/social_capture.py`（`py -3`，已在本机补齐 `requests` 依赖，**未**改 `butler_main/butler_bot_code`）：

1. **关键词 A（完整标题 URL 编码）**  
   `https://www.xiaohongshu.com/explore?keyword=Magentic-One%E6%83%B3%E5%88%B0%E7%9A%84agent%E9%AA%8C%E8%AF%81%E5%A4%96%E9%83%A8%E5%8C%96`  
   - **结果**：`{"status":"error","message":"小红书页面已打开，但没有定位到 note_id。"}`  

2. **关键词 B（缩短为英文核心词）**  
   `https://www.xiaohongshu.com/explore?keyword=Magentic-One`  
   - **结果**：同上。  

**含义**：搜索列表 / SSR 首屏未暴露与脚本解析规则一致的单帖 `noteId`，属 **入口 URL 类型不对**（与 `index.md` §6.1 一致），**非**脚本单路偶发失败。

## OCR / 结构化

- **OCR**：`ocr_not_started`（无 capture JSON / 无 `images`）  
- **是否已结构化**：`no`

## Status

| 字段 | 值 |
| --- | --- |
| `capture_status` | `failed_precondition_missing_single_url` |
| `failure_bucket` | **短链**：仍缺 `xhslink.com/o/...`；**换路**：关键词 explore 两路均无 `note_id` |
| `next_retry_entry` | 小红书 App → 该帖「分享 → 复制链接」→ 粘贴含 `http://xhslink.com/o/...` 或整段分享文案后再跑 `social_capture.py --output-dir BrainStorm/Raw/Simon_agent_xhs_series`；若 `images` 非空再判 `web-image-ocr-cn` |
| `capture_tool` | `web-note-capture-cn`（`social_capture.py`） |
| `ocr_tool_planned` | `web-image-ocr-cn`（仅捕获成功后） |
