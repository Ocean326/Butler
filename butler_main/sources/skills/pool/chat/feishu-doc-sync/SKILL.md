---
name: feishu-doc-sync
description: 创建/更新飞书云文档，并把文档链接发到聊天；支持 chat 或 orchestrator 将阶段摘要同步到一份「任务云文档」。
family_id: feishu-doc
family_label: 飞书文档族
family_summary: 处理飞书云文档的读取、同步与双向落盘；命中后再区分读取还是写回。
family_trigger_examples: 飞书文档, 云文档写回, 文档同步
risk_level: medium
variant_rank: 20
metadata:
  category: feishu
---

# Feishu Doc Sync

将内容同步到飞书云文档（创建或更新），并可选择把文档链接通过 IM 发给用户。用于「发云文档链接给用户」和「同步阶段任务摘要」。

## 适用场景

- 用户要求「发 feishu 云文档」「给我一个云文档链接」：创建/更新一份云文档，在聊天中发送该文档链接。
- chat 或 orchestrator 需要同步阶段摘要：把当前摘要写入配置好的云文档，云文档只作为展示出口。

## 前置条件

- 飞书应用已开通云文档相关权限（如「查看、评论、编辑和管理文档」/ 云空间权限）；使用 `tenant_access_token`。
- 配置中提供 `app_id`、`app_secret`（与现有 butler 飞书配置一致即可）；若做「任务云文档」同步，建议在 chat 或 orchestrator 入口配置 `task_doc_token` 或 `task_doc_folder_token`。

## 实现状态与调用方式

- **当前**：这里保留的是 skill 规格与接线说明，不再把已删除的旧 body service 当成真源。
- **对话侧**：用户要「发云文档链接」时，应由 chat 第四层入口封装 create/update doc 与发链路动作。
- **编排侧**：若要做周期性任务摘要同步，应由 orchestrator 或 chat 的当前入口显式调用，不再依赖旧后台自动化专用钩子。

## 参考

- 方案说明应沉淀到 chat 冷数据或治理目录，不再依赖旧 `agents/local_memory` 目录。
- 飞书开放平台：创建文档、编辑文档、权限说明（以官网最新为准）。
