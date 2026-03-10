# xiaohongshutools - 安装与替代方案

## 安装状态（2026-03-08 更新）

**ChocomintX/xiaohongshutools** 与 **https://clawhub.ai/ChocomintX/xiaohongshutools** 为同一 skill，已**手动安装**到 `./butler_bot_agent/skills/xiaohongshutools/`，内容来自 openclaw/skills 的 chocomintx/xiaohongshutools。

### 已安装

- `SKILL.md`：完整使用说明（搜索、笔记详情、评论、用户信息等）
- `reference.md`：本文件

### 可选：获取 Python 脚本

如需运行预构建的 `create_xhs_session` 等模块，可从 GitHub 拉取 scripts：

```bash
git clone --depth 1 https://github.com/openclaw/skills.git _tmp
xcopy /E /I _tmp\skills\chocomintx\xiaohongshutools\scripts .cursor\skills\xiaohongshutools\scripts
rmdir /s /q _tmp
```

或使用 ClawHub（网络恢复后）：`npx clawhub@latest install xiaohongshutools --force`

### 历史尝试记录

| 操作 | 结果 |
|------|------|
| `clawhub install ChocomintX/xiaohongshutools` | Invalid slug |
| `clawhub install xiaohongshutools --force` | Rate limit exceeded |
| `playbooks add skill openclaw/skills --skill xiaohongshutools` | Windows raw mode 报错 |

## 推荐后续操作

1. **稍后重试**：过一段时间再试 `npx clawhub@latest install sonoscli`，再试安装目标 skill（若 ClawHub 站上 slug 有更新，以站内为准）。
2. **在 ClawHub 站内确认**：打开 <https://clawhub.ai/ChocomintX/xiaohongshutools> 查看是否有「安装」或 slug 说明。
3. **使用本工作区现有能力**：小红书相关能力可先用 **xiaohongshu-mcp**（需启动 `xiaohongshu-mcp-windows-amd64.exe`），见 `工作区/小红书探索学习/xiaohongshu-mcp_接入与使用指南_20260308.md`。

## 与本工作区其他小红书方案

| 方案 | 说明 |
|------|------|
| xiaohongshutools（本 skill） | 从链接提取标题/正文/图片，需通过 ClawHub 安装，当前安装未成功 |
| xiaohongshu-mcp | 本机 MCP，支持登录、发图文/视频、首页推荐、搜索、笔记详情、评论等，已接入飞书工作站 |
| redbook-scraper-mcp-server | 第三方 MCP，需 Docker，get_note_content 需站内 URL（xhslink 需先解析） |

详见 `工作区/小红书探索学习/读小红书与解析xhslink_方案整理_20260308.md`。
