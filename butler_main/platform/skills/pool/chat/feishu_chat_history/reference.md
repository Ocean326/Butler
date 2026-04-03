# 飞书「获取会话历史消息」API 参考

本 skill 基于飞书开放平台 **获取会话历史消息** 接口实现，便于在主代码外独立维护与调用。

## 接口说明

- **文档**：[获取会话历史消息 - 飞书开放平台](https://open.feishu.cn/document/server-docs/im-v1/message/list)
- **方法**：`GET`
- **路径**：`/open-apis/im/v1/messages`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| container_id_type | string | 是 | 容器类型，当前仅支持 `"chat"`（含单聊 p2p 与群聊 group） |
| container_id | string | 是 | 会话（chat）ID，如 `oc_234jsi43d3ssi993d43545f` |
| start_time | string | 否 | 历史消息起始时间（**秒级**时间戳） |
| end_time | string | 否 | 历史消息结束时间（**秒级**时间戳） |
| page_token | string | 否 | 分页标记，首次请求不填；响应中返回下一页的 token |
| page_size | int | 否 | 分页大小，默认 20，**最大 50** |

## 请求头

- `Authorization: Bearer {tenant_access_token}`
- `Content-Type: application/json`

## 响应体（data）

| 字段 | 类型 | 说明 |
|------|------|------|
| has_more | bool | 是否还有更多数据 |
| page_token | string | 下一页的分页标记 |
| items | array | 消息列表，每项包含 message_id、msg_type、create_time、sender、body、mentions 等 |

单条消息常见字段：`message_id`、`msg_type`（text/post/interactive 等）、`create_time`（秒级时间戳）、`sender`（发送者信息）、`body`（消息内容 JSON 字符串）。

## 权限

- **单聊（p2p）**：应用默认具备「获取用户发给机器人的单聊消息」等能力即可。
- **群聊（group）**：需在 [飞书开放平台](https://open.feishu.cn/app) 为该应用开通 **「获取群组中所有消息」** 权限，且机器人已加入对应群组。

## 与本 skill 的对应

| 本 skill 函数 | 说明 |
|--------------|------|
| `get_tenant_token` | 获取调用上述接口所需的 `tenant_access_token`（与主项目 memory_manager 鉴权方式一致） |
| `list_messages` | 对应单次 GET 请求，返回 `data`（含 items、has_more、page_token） |
| `list_all_messages` | 循环分页直至 `has_more == false`，返回合并的 items 与摘要 |
| `download_messages_to_file` | 调用 `list_all_messages` 并将结果写入 JSON 文件 |

## 错误与排查

- `code != 0`：以飞书返回的 `code`、`msg` 为准，本 skill 会抛出 `RuntimeError`。
- 群聊无数据：检查是否已申请「获取群组中所有消息」且机器人在群内。
- 鉴权失败：确认 `app_id`、`app_secret` 与当前应用一致，且未过期。
