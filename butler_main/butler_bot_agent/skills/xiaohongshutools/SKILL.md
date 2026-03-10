---
name: xiaohongshutools
description: "XiaoHongShu (Little Red Book) data collection and interaction toolkit. Use when working with XiaoHongShu (小红书) platform for: (1) Searching and scraping notes/posts, (2) Getting user profiles and details, (3) Extracting comments and likes, (4) Following users and liking posts, (5) Fetching home feed and trending content. Automatically handles encryption parameters. Supports guest mode and authenticated sessions via web_session cookie. Source: ChocomintX/xiaohongshutools on ClawHub (https://clawhub.ai/ChocomintX/xiaohongshutools)."
metadata:
    category: research
---

# Xiaohongshu Skill (ChocomintX/xiaohongshutools)

小红书（XiaoHongShu / Little Red Book）数据采集和交互工具包。来源：**ChocomintX/xiaohongshutools**（ClawHub：<https://clawhub.ai/ChocomintX/xiaohongshutools>），基于 RedCrack 纯 Python 逆向工程实现。

## 安装

### 依赖

```bash
pip install aiohttp loguru pycryptodome getuseragent
```

### 获取脚本（可选）

完整脚本位于 openclaw/skills：<https://github.com/openclaw/skills/tree/main/skills/chocomintx/xiaohongshutools>。若需预构建模块，可克隆该目录的 scripts 到本地，并在代码中调整 `sys.path`。

## Quick Start

```python
import asyncio
import sys
# 若已克隆 scripts，调整为本地路径：
# sys.path.insert(0, r'path/to/butler_bot_agent/skills/xiaohongshutools/scripts')

from request.web.xhs_session import create_xhs_session

async def main():
    xhs = await create_xhs_session(proxy=None, web_session="YOUR_WEB_SESSION_OR_NONE")
    res = await xhs.apis.note.search_notes("美妆")
    data = await res.json()
    print(data)
    await xhs.close_session()

asyncio.run(main())
```

## Core Capabilities

### 1. Search & Discovery

- `search_notes(keyword)` - 关键词搜索
- `get_homefeed(category)` - 首页推荐
- `note_detail(note_id, xsec_token)` - 笔记详情

### 2. User Interactions

- `get_self_simple_info()` - 当前用户信息
- `follow_user(user_id)` - 关注用户
- `like_note(note_id)` - 点赞笔记

### 3. Comments

- `get_comments(note_id, xsec_token)` - 获取评论

## Configuration

- **proxy**：非必须，`proxy=None` 可运行；网络不稳或风控时建议配置
- **web_session**：登录态 cookie，搜索报 code=-104 时需提供

## Links & IDs

- note_id 为十六进制字符串（如 `697cc945000000000a02cdad`）
- note_detail、get_comments 需要 `note_id` + `xsec_token`（搜索结果 item 中）
- xhslink 短链需在 App 内分享获得，接口通常不直接返回

## Troubleshooting

- **461**：风控，降低频率、加 sleep、换代理或 web_session
- **401/403**：web_session 过期或风控更新
- **Import errors**：确认依赖已安装，`sys.path` 指向 scripts 目录

## 与本工作区

- 产出写入 `工作区/小红书探索学习/`
- 与 xiaohongshu-mcp、redbook-scraper-mcp 等方案可配合使用，见 `读小红书与解析xhslink_方案整理_20260308.md`
