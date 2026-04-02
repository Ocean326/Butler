# agent测评基准整理（抓取失败前置缺口记录）

- platform: xiaohongshu
- id: null（未能从主页定位到 noteId）
- source_url: https://xhslink.com/m/8o0d4Pck5Xw（主页标题列表核对）
- resolved_url: null
- author: Simon
- published_at: ~2025-11-20（来自 `index.md` 估计）
- updated_at: 2026-03-20T03:12:09+08:00
- engagement: null
- tags: agent, 测评, benchmark

## Content

本次尝试抓取单篇正文失败：`web-note-capture-cn` 需要输入里可解析的“单篇 URL”，脚本会从页面首屏定位到 `noteId` 与 `xsec_token` 才能导出 `images` 与正文。

但对 `Simon` 的主页入口（`xhslink.com/m/8o0d4Pck5Xw`）进行抓取后：
- 仅能获得“标题/点赞数/加载中”等文本信息
- 主页 HTML 中不存在可解析的 `xhslink.com/o/...` 短链
- 主页 HTML 中也不存在 `noteId` 与 `xsec_token` 字段

因此无法构造可直接交给 `web-note-capture-cn` 的单篇抓取 URL。

## Notes (关键证据)

- `WebFetch(https://xhslink.com/m/8o0d4Pck5Xw)`：输出仅包含笔记标题与点赞数，未出现 `http(s)://xhslink.com/o/...`。
- 本地 `python requests` 抓取主页 HTML 并正则统计：
  - `xhslink.com/o/<code>` 命中数量：0
  - `"noteId":"..."` 命中数量：0
  - `"xsec_token":"..."` 命中数量：0
- 备用重试（低依赖关键词入口）：
  - 输入：`https://www.xiaohongshu.com/explore?keyword=agent%E6%B5%8B%E8%AF%84%E5%9F%BA%E5%87%86%E6%95%B4%E7%90%86`
  - 工具：`web-note-capture-cn`（`social_capture.py`）
  - 报错：`小红书页面已打开，但没有定位到 note_id。`

## Status

- capture_status: failed_precondition_missing_single_url
- ocr_status: not_started
- structured_derivation: false
- next_retry_entry: 需要你在小红书 App 里把该笔记的分享链接复制为 `http://xhslink.com/o/...`（或任意可解析单篇 URL），我再跑 `web-note-capture-cn` +（如含图）`web-image-ocr-cn`
- capture_tool_planned: web-note-capture-cn
- ocr_tool_planned: web-image-ocr-cn

