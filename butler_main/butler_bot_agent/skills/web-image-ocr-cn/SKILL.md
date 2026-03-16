---
name: web-image-ocr-cn
description: 下载并识别中文网页抓取里的图片内容（OCR），优先配合 web-note-capture-cn 使用。
category: research
trigger_examples: 图片 OCR, 小红书图片识别, 知乎插图识别, 网页截图文字提取
allowed_roles: feishu-workstation-agent, butler-continuation-agent, heartbeat-executor-agent
risk_level: medium
heartbeat_safe: true
requires_skill_read: true
---

# Web Image OCR CN

用于对「网页抓取结果中的图片」做第二阶段 OCR，特别是配合 `web-note-capture-cn` 使用：

- 当抓取到的小红书 / 知乎 / 其它网页里有图片 URL 列表时，
- 由本 skill 负责下载图片并调用本地 PaddleOCR（默认）或 OpenAI Vision 做 OCR，
- 输出结构化 JSON 与可读 Markdown，方便后续进入 BrainStorm 或 self_mind。

## 本 skill 的边界

- 只做**图片下载 + OCR 识别 + 文本落盘**，不负责网页抓取（由 `web-note-capture-cn` 完成）。
- 默认使用本地 **PaddleOCR** 能力进行识别，避免对外网 API 的强依赖。
- 也支持通过 **OpenAI Vision** 作为可选后端：
  - 依赖环境变量 `OPENAI_API_KEY`（或兼容的同类实现），不在脚本中硬编码密钥。
  - 不额外安装未知三方依赖，只使用 `requests` 与标准库。
- 不尝试绕过图床防盗链；若图片下载失败，会在输出的 `errors` 中记录。
- 不做复杂版面还原，只做「读出文字」和简单分段。

## 入口脚本

- 脚本路径：`./butler_main/butler_bot_agent/skills/web-image-ocr-cn/scripts/image_ocr.py`

### 典型调用 1：直接给一组图片 URL

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-image-ocr-cn/scripts/image_ocr.py' `
  --image-url 'https://example.com/image1.png' `
  --image-url 'https://example.com/image2.jpg' `
  --output-dir 'BrainStorm/Raw/ocr'
  # 默认使用 PaddleOCR，如需改用 OpenAI：
  # --backend openai
```

### 典型调用 2：对 `web-note-capture-cn` 的 JSON 结果做二阶段 OCR

假设你已经用 `web-note-capture-cn` 抓取了一篇内容，得到：

- JSON：`工作区/网页抓取验证/xiaohongshu_xxxxxx.json`
- Markdown：`工作区/网页抓取验证/xiaohongshu_xxxxxx.md`

可以这样触发 OCR：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-image-ocr-cn/scripts/image_ocr.py' `
  --from-capture-json '工作区/网页抓取验证/xiaohongshu_xxxxxx.json' `
  --output-dir 'BrainStorm/Raw'
  # 默认 backend=paddle，如需临时切回 OpenAI：
  # --backend openai
```

脚本会：

- 读取 JSON 里的 `images` 字段（URL 列表）；
- 逐张下载并用默认 PaddleOCR（或 `--backend openai`）做 OCR；
- 在同一目录下生成：
  - `xiaohongshu_xxxxxx_ocr.json`
  - `xiaohongshu_xxxxxx_ocr.md`

## 输出格式

JSON 结构大致为：

- `source`：来源说明（如 `web-note-capture-cn` + 原始 JSON 路径）
- `created_at`：ISO8601 时间戳
- `images`：每张图片的 OCR 结果列表，单项包含：
  - `url`：图片 URL
  - `saved_path`：本地保存路径（若有）
  - `ocr_text`：识别出的文字
  - `error`：若该图片识别失败，则为错误说明

Markdown 会采用便于人看的格式：

```markdown
## Image 1

源地址: ...

识别结果:

...
```

## 环境与前置条件

- **默认 backend=paddle**：使用本地 PaddleOCR，无需 API Key；仅需安装 PaddleOCR 相关依赖（见本 skill 目录说明）。
- **可选 backend=openai**：若显式传入 `--backend openai`，则需 `OPENAI_API_KEY`；可选 `OPENAI_BASE_URL` / `OPENAI_MODEL`。
- 仅依赖：Python 标准库、`requests`；Paddle 时另需本 skill 约定的 PaddleOCR 环境。

## 与 feishu-workstation-agent 的约定

- 当用户在飞书里分享的链接通过 `web-note-capture-cn` 抓取后，若 JSON 结果中存在 `images` 字段：
  - **默认行为（无需用户每轮再说）**：feishu-workstation-agent **必须**在同轮内再触发本 skill，
    以 `--from-capture-json` 方式完成图片 OCR，并在回复中合并关键文字要点。
  - **BrainStorm 场景**：将 OCR Markdown 一并写入对应 `BrainStorm/Raw/..._ocr.md`，
    在 Notes 中注明「由 web-image-ocr-cn 自动识别」。归档前自检：有图未 OCR 则先跑本 skill 再落盘。

若当前环境未配置 OpenAI Key 或调用失败，本 skill 会：

- 在终端打印清晰的错误提示；
- 在输出 JSON 中为每张图片标记 `error` 字段；
- 不硬失败整轮流程，以免阻塞其它抓取任务。

