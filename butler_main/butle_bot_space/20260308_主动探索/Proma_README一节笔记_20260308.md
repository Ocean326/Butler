# Proma README 一节笔记（心跳执行·单步）

> **执行时间**：2026-03-08（管家 bot 心跳）  
> **对应**：学习计划 3.2「通读 README + 配置指南」之 README 首节  
> **来源**：https://github.com/ErlichLiu/Proma（main 分支 README）

---

## 本节覆盖范围

已读：**核心能力**、**快速开始**、**配置指南**（添加渠道 / Agent 模式 / 特殊供应商）、**技术栈**。

---

## 要点摘要

### 快速开始

- 从 [Releases](https://github.com/ErlichLiu/Proma/releases) 下载对应平台最新版本即可，无需从源码构建即可体验。

### 配置指南（与 3 分钟飞书配置呼应）

- **渠道**：设置 → 渠道管理 → 添加渠道 → 选供应商 + API Key → 测试连接 → 获取模型。
- **Agent 模式**：仅支持 **Anthropic** 渠道；设置 → Agent → 选渠道与模型（推荐 Claude Sonnet 4 / Opus 4）；底层为 Claude Agent SDK。
- **特殊端点**：MiniMax / Kimi / 智谱 使用专用 Base URL，且各有 Chat 与 Anthropic 兼容端点，README 表格已列出。

### 与当前管家工作流的直接对照

- **飞书**：Proma 支持 /workspace、/new，工作区可配置 Skills/MCP；与本工作区「飞书 → 管家 Agent」可对比体验。
- **记忆**：Chat 与 Agent 共享记忆，数据在 `~/.proma/`；可与本工作区 recent_memory + local_memory 对照。
- **技术栈**：Bun · Electron + React 18 · Jotai · Tailwind + shadcn/ui · Vite · TypeScript；记忆实现致谢 MemOS。

---

## 下一步建议（供后续心跳）

- 3.2 续：若有需要可再读 README.en.md 或仓库内配置/飞书相关 doc。
- 3.1：若需本地跑起来，从 Releases 下载并安装运行一次。
- 3.3：配置飞书 bot 并体验远程 Agent（与当前管家对比）。

---

*本笔记为单步产出，仅读 README 一节并提炼，未执行多步。*
