---
name: feishu_chat_history
description: "飞书会话历史消息的获取、分页拉取与导出。当需要「获取/下载/访问/查找历史聊天记录」、按时间范围或关键词梳理对话、将会话记录导出到本地时使用。基于飞书开放平台「获取会话历史消息」API（im v1 message list），独立于主代码，避免 butler_bot 臃肿。"
metadata:
    category: feishu
---

# 飞书历史聊天记录 (Feishu Chat History)

基于 [飞书开放平台 - 获取会话历史消息](https://open.feishu.cn/document/server-docs/im-v1/message/list) 实现：**获取、分页拉取、导出** 指定会话（单聊/群聊）的历史消息，供 Agent 或主程序按需调用，不污染主代码。

## 使用场景

- 获取某单聊/群聊的历史消息列表（含分页）
- 按时间范围（start_time / end_time）筛选历史记录
- 分页拉取全部历史并合并为一份列表或导出到本地文件
- 查找、统计、复盘某会话的对话内容

## 快速开始

### 依赖

- Python 3.8+
- `requests`（与 butler_bot 主项目一致）

### 配置来源

**凭证与会话 ID 的真实来源与解析顺序如下：**

- **应用凭证 (`app_id` / `app_secret`)**
  - 若函数入参中显式传入 `app_id` / `app_secret`，优先使用入参。
  - 否则，若传入 `config_provider() -> dict`，且返回字典中包含 `app_id` / `app_secret`，则复用该配置；推荐直接复用主进程的 CONFIG。
  - 否则，尝试从环境变量 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 读取。
  - 若以上都未命中，**兜底**从 Butler 主体配置 `butler_main/butler_bot_code/configs/butler_bot.json` 中读取 `app_id` / `app_secret`，与 `agent.py` / 飞书长连接使用的是同一份配置。
  - 若最终仍无法获得完整的 `app_id` + `app_secret`，才会抛出错误提示。

- **会话 ID (`container_id` / `chat_id`)**
  - 若函数入参中显式传入 `container_id`，则直接使用该值（推荐传入具体 `chat_id`，形如 `oc_xxx`）。
  - 否则，尝试从环境变量 `FEISHU_CHAT_ID` 读取默认会话 ID，用于在本地或心跳/巡检脚本中与主进程对齐同一个会话。
  - 若两者都为空，会抛出显式错误，提示调用方补全 `container_id` 或配置 `FEISHU_CHAT_ID`。

> 小结：在本地与生产环境中，只要主进程已经通过 `butler_bot.json` 正常运行飞书长连接，`feishu_chat_history` 在**不传任何 app_id/app_secret 参数**的情况下，也能自动复用同一套飞书应用凭证，避免出现「本地拿不到凭证」的错误结论。

### 在代码中调用

```python
from butler_bot_agent.skills.feishu_chat_history import (
    get_tenant_token,
    list_messages,
    list_all_messages,
    download_messages_to_file,
)

# 方式一：直接传 app_id / app_secret
token = get_tenant_token(app_id="xxx", app_secret="xxx")
page = list_messages(
    container_id="oc_xxxxxxxxxxxx",  # 会话（chat）ID
    container_id_type="chat",
    app_id="xxx",
    app_secret="xxx",
    page_size=20,
)
# page["items"] 为当前页消息列表，page["has_more"], page["page_token"] 用于翻页

# 方式二：拉取全部并导出到文件（自动分页）
all_items, summary = list_all_messages(
    container_id="oc_xxxxxxxxxxxx",
    app_id="xxx",
    app_secret="xxx",
    start_time=1700000000,  # 可选，秒级时间戳
    end_time=1735689600,    # 可选
)
path = download_messages_to_file(
    container_id="oc_xxxxxxxxxxxx",
    app_id="xxx",
    app_secret="xxx",
    output_path="./工作区/with_user/feishu_chat_history/raw/chat_oc_xxx.json",
    start_time=1700000000,
    end_time=1735689600,
)
```

### 通过配置注入（与 memory_manager 一致）

若主程序已有 `config_provider() -> dict`（含 `app_id`、`app_secret`），可传参复用：

```python
def config_provider():
    return {"app_id": "...", "app_secret": "..."}

all_items, summary = list_all_messages(
    container_id="oc_xxx",
    config_provider=config_provider,
)
```

## 能力一览

| 能力 | 函数 | 说明 |
|------|------|------|
| 获取 tenant token | `get_tenant_token` | 内部鉴权用，也可供其他飞书 API 复用 |
| 单页历史消息 | `list_messages` | 对应飞书「获取会话历史消息」单次请求，支持 start_time / end_time / page_token |
| 拉取全部（自动分页） | `list_all_messages` | 循环翻页直到 has_more=False，返回合并列表与摘要 |
| 导出到文件 | `download_messages_to_file` | 将历史消息写入 JSON 文件，便于归档或后续分析 |
| 获取消息详情 | `get_message_detail` | 通过 message_id 获取单条消息详情，包含 chat_id 等字段 |
| message_id→chat_id | `get_chat_id_by_message_id` | 通过一条已知消息反查所属会话 chat_id，用于初始化 `FEISHU_CHAT_ID` |

## 权限与限制

- **单聊（p2p）**：默认权限即可。
- **群聊（group）**：需在飞书开放平台为该应用申请「获取群组中所有消息」权限，且机器人已加入该群。
- 分页大小：单次最多 50 条（飞书限制）；`page_size` 默认 20。

## 与本工作区

- 导出路径建议：与用户直接相关的产出使用 **`./工作区/with_user/feishu_chat_history/`**（其下 `raw/` 存原始 JSON，`digest/` 存摘要）；其它场景可用 `./工作区/feishu_chat_history/` 或各 Agent 产出目录下的子目录，便于与 daily-inspection、file-manager 等协作。
- 主代码（如 `memory_manager`）仅需 `from butler_bot_agent.skills.feishu_chat_history import list_messages, list_all_messages` 即可使用，无需再实现鉴权与分页逻辑。

## 更多说明

- API 文档与参数详见 [reference.md](reference.md)。
- 飞书官方文档：[获取会话历史消息](https://open.feishu.cn/document/server-docs/im-v1/message/list) 以及 [获取指定消息的内容](https://open.feishu.cn/document/server-docs/im-v1/message/get)。
- `chat_id` 获取推荐路径（一次性）：
  - 在目标会话中任选一条消息，拿到它的 `message_id`（例如通过机器人日志或飞书开放平台调用记录）。
  - 在仓库根目录下执行：`python .\工作区\temp\run_feishu_get_chat_id_from_message_id.py om_xxx`。
  - 该脚本会调用本 skill 的 `get_chat_id_by_message_id`，打印解析到的 `chat_id`，并在 `工作区/temp/feishu_chat_id_resolved.txt` 中落一份记录，便于写入环境变量 `FEISHU_CHAT_ID`。

## 「飞书聊天记录抓取（含心跳会话）」验收回执（范本）

- **唯一必备缺参**：目标会话的 `chat_id`，建议写入环境变量 `FEISHU_CHAT_ID`。
- **最短复跑路径**（示例，PowerShell）：
  - 在仓库根目录：`$env:FEISHU_CHAT_ID="oc_xxx"; python -m butler_main.butler_bot_agent.skills.feishu_chat_history.chat_history` 上层可封装为自用脚本，核心是复用 `download_messages_to_file` 把指定 `chat_id` 全量导出到 `./工作区/with_user/feishu_chat_history/raw/`。
- **产物落盘位置（建议）**：
  - 原始 JSON：`./工作区/with_user/feishu_chat_history/raw/`
  - 摘要/派生结果：`./工作区/with_user/feishu_chat_history/digest/`
- **常见卡点（对本项目场景）**：
  - 混用 `open_id` / `chat_id`：history API 只接受会话 `chat_id` 作为 `container_id`，不能直接传用户 `open_id`。
  - 忘记配置 `FEISHU_CHAT_ID`：会在 raw 目录生成 `*_chat_raw_error.json`，`error_type=missing_credentials_or_chat_id`，按上文脚本补齐后重试即可。
  - 凭证错用：使用了错误环境或已下线应用的 `app_id` / `app_secret`，可对照飞书开放平台应用配置与 `butler_bot.json` 校验。

## 这类问题的「做事范式」（以本轮为例）

以后遇到类似「飞书链路有点糊、但希望一次性收口成可复跑工具」的任务，默认按下面节奏来：

1. **先对齐真实目标**：用户要的不是“能不能调通一个接口”，而是「有一条最短可复跑链路 + 清晰验收回执」。
2. **先查官方文档，再看现有 skill**：用飞书开放平台文档确认边界（能不能直接用 open_id、有没有 message→chat 的接口），再对照当前 skill / 配置实际落地情况。
3. **优先补 skill / 文档，而不是散落脚本**：像这次一样，把新的 helper（`get_chat_id_by_message_id`）、脚本入口、验收回执都集中写回 `feishu_chat_history` skill，而不是只在临时脚本里救火。
4. **给用户一眼能懂的结果形态**：包括——唯一缺参点、最短复跑命令、产物落到哪里、常见会卡住的地方；这些都应该在 SKILL 里有模板。
5. **把这轮合作当作下次的范本**：下次再遇到飞书相关链路问题，优先复用这套节奏：先问“目标验收回执长什么样”，再补 skill / 文档 / helper，而不是只堆实现细节。

## 常见故障与排查清单

- **缺少凭证或会话 ID**
  - **症状**：`./工作区/with_user/feishu_chat_history/raw/` 下生成 `*_chat_raw_error.json`，`error_type` 为 `missing_credentials_or_chat_id`，`missing_keys` 中包含 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_CHAT_ID`。
  - **排查**：
    - 在本机或运行环境中配置 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_CHAT_ID` 环境变量。
    - `FEISHU_CHAT_ID` 为目标会话的 `chat_id`（形如 `oc_xxx`），可从飞书开放平台或现有机器人日志中获取。
    - 若主程序已有配置中心，也可以通过 `config_provider()` 传入 `app_id` / `app_secret`。

- **鉴权失败 / token 获取失败**
  - **症状**：日志或 raw error 中出现 `飞书 tenant_access_token 获取失败`，信息中包含 `code=`, `msg=`, `request_id=`。
  - **排查**：
    - 确认当前使用的 `app_id` / `app_secret` 与飞书开放平台上的应用配置一致，未误用其它环境或旧应用的凭证。
    - 检查应用是否为自建应用，当前 skill 使用的是 `auth/v3/tenant_access_token/internal` 接口。
    - 如需进一步排查，可在飞书开放平台查看对应 `request_id` 的调用详情。

- **接口返回 code != 0 / 无法获取会话历史消息**
  - **症状**：异常信息中包含 `飞书获取历史消息失败: code=... msg=... request_id=...`。
  - **排查**：
    - 对照飞书开放平台文档，查看该 `code` / `msg` 所对应的错误原因。
    - 确认应用已经为目标场景开通：
      - 单聊：默认权限一般即可；
      - 群聊：需要「获取群组中所有消息」权限。
    - 确认机器人账号已经加入目标会话（群聊），否则历史消息接口会返回无权限或空数据。

- **参数配置不一致 / 会话无数据**
  - **症状**：调用成功但 `items` 为空，或只拿到部分时间段的数据。
  - **排查**：
    - 检查 `container_id` 是否填写为正确的 `chat_id`（不要填 open_id、user_id 等其它 ID）。
    - 核实 `start_time` / `end_time` 是否为秒级时间戳，且时间范围覆盖了你期望的消息区间。
    - 如有分页需求，注意 `page_size` 最大为 50，并根据返回的 `has_more` / `page_token` 循环拉取。

- **接口变更或网络异常**
  - **症状**：异常信息中出现「响应非 JSON」或 HTTP status 非 200，附带完整响应文本。
  - **排查**：
    - 检查本机网络是否可以访问 `https://open.feishu.cn`。
    - 对照飞书开放平台最新文档，确认 `im/v1/messages` 接口路径与参数未发生兼容性变更。
    - 若长期稳定失败，可在上层脚本中记录 raw 响应，或配合飞书开放平台的调用日志排查。
