# 本地 Cursor CLI Agent 接入飞书指南

> 参考：[飞书下载与官网](https://www.feishu.cn/download)、[手把手打造飞书 Webhook Bot](https://www.feishu.cn/content/7271149634339422210)、[飞书自定义机器人文档](https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN)

## 一、接入方式概览

| 方案 | 方向 | 复杂度 | 适用场景 |
|------|------|--------|----------|
| **自定义机器人 Webhook** | 单向推送 | ⭐ 低 | 本地执行 agent，推送结果到飞书群 |
| **企业自建应用 + 长连接** | 双向交互 | ⭐⭐⭐ 高 | 飞书内 @机器人 触发 agent，回复到飞书 |

本指南优先实现**方案一**，本地无需公网 IP，开箱即用。

---

## 二、创建飞书自定义机器人（获取 Webhook）

1. 打开飞书，创建或进入目标群组  
2. 点击群设置 → **群机器人** → **添加机器人**  
3. 选择 **自定义机器人**  
4. 填写名称（如 `Cursor Agent`）、描述  
5. 复制生成的 **Webhook 地址**（形如 `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx`）  
6. （推荐）配置安全设置：
   - **自定义关键词**：如 `Cursor`、`agent`，仅包含关键词的消息才会推送
   - **IP 白名单**：填入本机公网 IP
   - **签名校验**：需在发送时携带 `timestamp` 与 `sign` 参数（见下文）

---

## 三、推送消息格式

### 1. 普通文本

```json
{
  "msg_type": "text",
  "content": {
    "text": "你的消息内容"
  }
}
```

### 2. 富文本（支持 Markdown 风格）

```json
{
  "msg_type": "post",
  "content": {
    "post": {
      "zh-CN": {
        "title": "标题",
        "content": [
          [{ "tag": "text", "text": "正文内容" }]
        ]
      }
    }
  }
}
```

### 3. 启用签名时的请求参数

若开启签名校验，需在请求体中增加：

```json
{
  "timestamp": "1730784000",
  "sign": "Base64(HMAC-SHA256(timestamp + \"\\n\" + secret))",
  "msg_type": "text",
  "content": { "text": "消息" }
}
```

- `timestamp`：当前 Unix 时间戳（秒），1 小时内有效  
- `sign`：签名算法见 [飞书官方文档](https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN)

---

## 四、与 Cursor CLI Agent 的集成方式

### 方式 A：脚本执行 agent 后推送到飞书

1. 本地运行 Cursor CLI：`agent -p "你的提示" --output-format text`  
2. 捕获输出内容  
3. 对飞书 Webhook 发起 POST 请求，将输出作为消息内容发送

详见 `butler_bot_agent/skills/feishu-webhook-tools/SendToFeishu.ps1` 及 `butler_bot_agent/skills/feishu-webhook-tools/agent-to-feishu.ps1`。

### 方式 B：在每日自动化脚本中增加飞书推送

在 `daily/DailyResearchOps.ps1` 执行完三项任务后，将日志或摘要推送到飞书群，便于在手机上查看执行结果。

---

## 五、双向交互（进阶）

若需在飞书内 @机器人 触发 agent 并回复：

1. 在 [飞书开放平台](https://open.feishu.cn/app) 创建企业自建应用  
2. 开启 **机器人** 能力，订阅 `im.message.receive_v1`  
3. 使用 **长连接** 接收消息（本地无需公网）  
4. 收到消息后调用 `agent -p "用户问题"`，将回复通过 [发送消息 API](https://open.feishu.cn/document/server-docs/im-v1/message/create) 回传到飞书

实现需额外开发（如 Node.js + 飞书 SDK），可参考 [飞书长连接文档](https://open.feishu.cn/document/ukTMukTMukTM/uYDO1YjL2gTN24iN4YjN)。

---

## 六、快速验证

```powershell
cd "c:\Users\Lenovo\Desktop\研究生\Butler\butler_main"

# 1. 纯消息推送测试
.\butler_bot_agent\skills\feishu-webhook-tools\SendToFeishu.ps1 -WebhookUrl "https://open.feishu.cn/open-apis/bot/v2/hook/xxx" -Message "Cursor Agent 接入飞书测试"

# 2. 执行 agent 并推送输出到飞书
.\butler_bot_agent\skills\feishu-webhook-tools\agent-to-feishu.ps1 -WebhookUrl "你的Webhook地址" -Prompt "用一句话介绍今日 AI 领域重要进展"

# 3. 每日脚本完成后推送摘要（传入 FeishuWebhookUrl 参数）
.\butler_bot_agent\skills\daily-inspection\DailyResearchOps.ps1 -FeishuWebhookUrl "你的Webhook地址"
```

成功则飞书群内会收到对应消息。
