---
name: feishu-doc-sync
description: 创建/更新飞书云文档，并把文档链接发到聊天；支持心跳将任务摘要同步到一份「任务云文档」。
metadata:
  category: feishu
---

# Feishu Doc Sync

将内容同步到飞书云文档（创建或更新），并可选择把文档链接通过 IM 发给用户。用于「发云文档链接给用户」和「心跳维护任务云文档」。

## 适用场景

- 用户要求「发 feishu 云文档」「给我一个云文档链接」：创建/更新一份云文档，在聊天中发送该文档链接。
- 心跳 planner 维护任务云文档：每轮 plan 后，body 调用本 skill，把当前任务摘要写入配置好的云文档（真源仍为 `heartbeat_tasks/*.md`，云文档为展示出口）。

## 前置条件

- 飞书应用已开通云文档相关权限（如「查看、评论、编辑和管理文档」/ 云空间权限）；使用 `tenant_access_token`。
- 配置中提供 `app_id`、`app_secret`（与现有 butler 飞书配置一致即可）；若做「任务云文档」同步，需在 `heartbeat` 下配置 `task_doc_token` 或 `task_doc_folder_token`（见方案文档）。

## 实现状态与调用方式

- **当前**：能力已落在 body 侧，由 `butler_bot_code/butler_bot/services/feishu_doc_sync_service.py` 实现，供心跳与对话复用。
- **对话侧**：用户要「发云文档链接」时，可调用该 service 的 `create_doc` + `send_doc_link_to_im`（或由 body 在回复中附带【decide】发文件；云文档链接需走本能力）。
- **心跳侧**：每轮 plan 且 snapshot 后，若配置了 `heartbeat.task_doc_token` 或 `heartbeat.task_doc_folder_token`，body 会自动调用 `sync_heartbeat_task_doc` 将任务摘要同步到该云文档（真源仍为 `heartbeat_tasks/*.md`）。推荐配置 `task_doc_token`（在飞书先建好文档，把文档 token 填进 config）。

## 参考

- 方案真源：`./butler_main/butler_bot_agent/agents/local_memory/飞书云文档发送与心跳任务云文档_方案.md`
- 飞书开放平台：创建文档、编辑文档、权限说明（以官网最新为准）。
