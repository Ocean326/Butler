---
name: feishu-doc-read
description: "读取飞书云文档内容（纯文本/富文本块/Markdown）。当用户分享飞书文档链接、要求获取/阅读/抓取/解析飞书云文档时使用。基于飞书开放平台 docx/v1 API，独立于主代码。"
family_id: feishu-doc
family_label: 飞书文档族
family_summary: 处理飞书云文档的读取、同步与双向落盘；命中后再区分读取还是写回。
family_trigger_examples: 飞书文档, 云文档读取, 文档同步
risk_level: low
variant_rank: 10
metadata:
  category: feishu
---

# Feishu Doc Read

基于 [飞书开放平台 - 新版文档 docx/v1](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/list) 实现：**读取飞书云文档**的纯文本、富文本块、或转换后的 Markdown 内容，供 Agent 或主程序按需调用。

## 使用场景

- 用户分享飞书文档链接，要 Butler 读取并理解/摘要/提炼内容
- 后台自动流程或巡检需要从某份云文档同步内容到本地
- 需要把飞书云文档导出为本地 Markdown / 纯文本文件
- 获取文档基本信息（标题、版本号）

## 快速开始

### 依赖

- Python 3.8+
- `requests`（与 butler_bot 主项目一致）

### 配置来源

与 `feishu_chat_history` 完全一致：

1. 函数入参 `app_id` / `app_secret`（优先）
2. `config_provider() -> dict`（复用主进程 CONFIG）
3. 环境变量 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
4. 兜底从 `butler_main/butler_bot_code/configs/butler_bot.json` 读取

### 飞书应用权限

需要在飞书开放平台为应用开通以下**任一**权限：

- `docx:document:readonly`（查看新版文档）— **推荐**
- `docx:document`（创建及编辑新版文档）

同时，调用身份（`tenant_access_token`）需有目标文档的阅读权限：
- 通过文档页面右上角「…」→「添加文档应用」为应用授权

### 在代码中调用

```python
from butler_bot_agent.skills.feishu_doc_read import (
    read_feishu_doc,
    download_doc_to_file,
    parse_document_id,
)

# 一站式读取（支持传 URL 或 document_id）
doc = read_feishu_doc(
    "https://xxx.feishu.cn/docx/QvXLdALtMoJcZrxL34vcsI1ynvT",
    mode="raw",  # "raw" | "markdown" | "blocks"
)
print(doc["title"])    # 文档标题
print(doc["content"])  # 纯文本 / Markdown 内容

# 导出到本地文件
path = download_doc_to_file(
    "https://xxx.feishu.cn/docx/QvXLdALtMoJcZrxL34vcsI1ynvT",
    output_path="./工作区/feishu_docs/会议纪要.md",
    mode="markdown",
)

# 只解析 document_id
doc_id = parse_document_id("https://xxx.feishu.cn/docx/QvXLdALtMoJcZrxL34vcsI1ynvT")
```

## 能力一览

| 能力 | 函数 | 说明 |
|------|------|------|
| 解析 URL/ID | `parse_document_id` | 从完整 URL 或纯 ID 中提取 document_id |
| 获取 tenant token | `get_tenant_token` | 内部鉴权用，也可供其他飞书 API 复用 |
| 文档基本信息 | `get_document_meta` | 标题、revision_id 等 |
| 纯文本内容 | `get_document_raw_content` | 调用 raw_content 接口，返回纯字符串 |
| 富文本块（分页） | `get_document_blocks` | 自动分页拉取全部 block |
| Block → Markdown | `blocks_to_markdown` | 将 block 列表转为可读 Markdown |
| 一站式读取 | `read_feishu_doc` | 解析 URL → 获取 meta → 按 mode 取内容 |
| 导出到文件 | `download_doc_to_file` | 读取后保存到本地 .md / .txt / .json |

## 三种 mode 对比

| mode | 返回 | 适合场景 |
|------|------|---------|
| `raw` | 纯文本字符串 | 快速获取文本、做摘要/检索 |
| `markdown` | Block 转 Markdown | 保留标题/列表/代码块/链接结构 |
| `blocks` | 原始 block JSON | 需要精确样式/布局信息 |

## 支持的文档元素

Markdown 转换支持：标题(1-9级)、文本、有序/无序列表、代码块、引用、待办事项、分割线、图片/文件/表格(占位标记)、公式、链接、@用户/@文档、加粗/斜体/删除线/行内代码。

## 权限与限制

- 需要 `docx:document:readonly` 或 `docx:document` 权限
- 调用身份需有目标文档阅读权限（通过「添加文档应用」授权）
- 频率限制：单应用 5 次/秒
- `raw_content` 接口有文档大小上限（飞书限制）
- blocks 接口单页最多 500 个 block，本 skill 已自动分页

## 与已有 skill 的关系

| skill | 职责 |
|-------|------|
| `feishu-doc-sync` | **写**：创建/更新云文档 |
| `feishu_doc_read` | **读**：获取云文档内容到本地 |
| `feishu_chat_history` | 获取聊天历史消息 |

三者共享同一套凭证解析逻辑，可直接复用 `butler_bot.json` 中的 `app_id` / `app_secret`。

## 常见故障与排查

- **403 forbidden**：应用未被授权访问该文档。去飞书文档页面「…」→「添加文档应用」。
- **404 not found**：document_id 错误或文档已删除。检查 URL 是否正确。
- **URL 解析失败**：确认是 `/docx/` 或 `/wiki/` 路径的飞书链接。
- **凭证缺失**：同 `feishu_chat_history` 排查流程，检查 `butler_bot.json` 或环境变量。

## 产出路径建议

- 与用户相关：`./工作区/with_user/feishu_docs/`
- 内部用途：`./工作区/feishu_docs/`

## 参考

- 飞书开放平台文档：
  - [获取文档纯文本内容](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/raw_content)
  - [获取文档所有块](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/list)
  - [文档概述（document_id 说明）](https://open.feishu.cn/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/document-docx/docx-overview)
  - [如何为应用开通文档权限](https://open.feishu.cn/document/ukTMukTMukTM/uczNzUjL3czM14yN3MTN#16c6475a)
