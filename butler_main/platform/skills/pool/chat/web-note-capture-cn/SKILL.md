---
name: web-note-capture-cn
description: 抓取知乎专栏、小红书分享页等中文网页内容，并在落盘时把图片下载到本地，供 agent 直接按图片路径读图整理。用于用户给出 zhihu/xiaohongshu/xhslink 链接并要求提取标题、正文、作者、图片、互动数据、导出 Markdown/JSON 的场景。
category: research
family_id: web-capture
family_label: 中文网页抓取族
family_summary: 面向中文网页、分享页与图文内容的抓取落盘；命中后再区分平台和脚本细节。
family_trigger_examples: 网页抓取, 小红书链接, 知乎专栏
variant_rank: 10
trigger_examples: 知乎链接抓取, 小红书链接抓取, xhslink解析, 网页内容提取, 专栏正文导出
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: true
requires_skill_read: true
---

# Web Note Capture CN

用于抓取中文内容平台里的“单篇网页/笔记/专栏”，并把配图一起下载到本地，方便后续直接读图。

当前脚本重点支持：

- 知乎专栏 `zhuanlan.zhihu.com`
- 小红书分享页 `xiaohongshu.com`
- 小红书短链 `xhslink.com`

## 本 skill 的边界

- 默认只使用本地 Python 脚本和 `requests`，不联网安装未知依赖。
- 不直接执行外部 skill 或来源仓库里的可执行脚本；外部来源只作为人工审阅线索。
- 不在 Butler 主代码里硬塞平台逆向逻辑；平台抓取入口都留在本 skill 下。
- 不承诺绕过平台风控。知乎若出现 403，会提示补充登录 cookie 后重试。
- 默认在 `--output-dir` 下下载图片，并把绝对路径写入结果；后续由 agent 直接读图整理，不再默认串接 OCR skill。

## 入口脚本

- 脚本路径：`./butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py`
- 推荐运行方式：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
  'https://www.xiaohongshu.com/explore?...' `
  --output-dir 'MyWorkSpace/Research/topics/web_capture_validation'
```

## 常用命令

小红书分享页：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
  'https://www.xiaohongshu.com/explore?...' `
  --platform xiaohongshu `
  --output-dir 'MyWorkSpace/Research/topics/web_capture_validation'
```

小红书分享文案里夹着 `xhslink` 短链：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
  '科研龙虾上线 72 小时，我做了什么｜开发日记 🦞我的... http://xhslink.com/o/xxxxx 复制后打开【小红书】查看笔记！' `
  --output-dir 'MyWorkSpace/Research/topics/web_capture_validation'
```

知乎专栏，未登录先试一次：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
  'https://zhuanlan.zhihu.com/p/2013979334365434808?share_code=o8iY49m1fwAX&utm_psn=2016686371469817350' `
  --platform zhihu `
  --output-dir 'MyWorkSpace/Research/topics/web_capture_validation'
```

知乎若被 403，补 cookie 重跑：

```powershell
$env:ZHIHU_COOKIE = 'd_c0=...; z_c0=...'
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
  'https://zhuanlan.zhihu.com/p/2013979334365434808?share_code=o8iY49m1fwAX&utm_psn=2016686371469817350' `
  --platform zhihu `
  --cookie-env ZHIHU_COOKIE `
  --output-dir 'MyWorkSpace/Research/topics/web_capture_validation'
```

## 输出

脚本会输出：

- 标准化 JSON
- 对应 Markdown
- 若结果包含图片且传入了 `--output-dir`，还会在输出目录下生成 `images/` 子目录并下载图片
- 额外生成一份 `*_handoff.md`，供 agent 在同一轮里直接接着整理，不必再次重抓

字段尽量统一为：

- `platform`
- `source_url`
- `resolved_url`
- `id`
- `title`
- `author`
- `published_at`
- `updated_at`
- `content_text`
- `images`
- `image_assets`
- `image_local_paths`
- `agent_handoff`
- `tags`
- `engagement`
- `status`

## 与图片读图整理的衔接

当抓取结果中包含 `images` 字段时，本 skill 默认会在 `--output-dir` 下把图片下载到本地，并在 JSON / Markdown 中补充：

- `image_assets`：每张图的 `url / local_path / download_status / error`
- `image_local_paths`：成功下载图片的绝对路径列表
- `agent_handoff`：给下一步 agent 的交接信息，例如 `content_mode`、`should_read_images_first`、`recommended_next_step`

后续流程改为：

1. 使用本 skill 抓取网页，生成 `...json` 与 `...md`；
2. 优先打开同目录下自动生成的 `*_handoff.md`；
3. 若 `agent_handoff.content_mode = image_primary`，直接读取 `image_local_paths`；
4. agent 逐张按本地路径直接读图、识字、整理图中信息；
5. 将整理结果合并进 BrainStorm 工作稿或 Raw 汇总稿。

feishu-workstation-agent / butler-continuation-agent 在对话场景下，应视为**默认行为**：当用户让你「抓这篇小红书 / 知乎」且返回结果含图片时，**自动**读取下载后的本地图片并把关键信息一并整理给用户。无需用户每轮重复强调「图片也要看」。

**同轮收口约定**：如果这次抓取已经生成了 `*_handoff.md`，且其中提示 `should_read_images_first = true`，则本轮应直接继续读图整理并产出 `BrainStorm/Working`，不要再让用户发起第二轮“按这几张图继续整理”。

**归档自检（调用方契约）**：凡将抓取结果归档到 `MyWorkSpace/Research/brainstorm` 前，必须自检。若结果含 `images` 且 `image_local_paths` 为空或明显不全，视为图片 ingest 未完成，应先补跑抓取或检查下载失败原因。用户索要「刚刚那条」首图内容时，若本地图片未落盘，先补跑抓取并下载图片，再基于本地路径读图回复，不仅回复「当前无数据」。

## 平台说明

### 小红书

- 默认走分享页 HTML 首屏数据解析，当前对标题、正文、作者、图片、互动数提取较稳。
- 评论默认不抓，因为页面首屏通常不带完整评论列表。
- 若传入 `--output-dir`，会把图片同步下载到本地，适合后续直接按路径读图。

### 知乎

- 未登录抓取经常命中 403 挑战页。
- 本脚本会先做公开请求；若被挡，会明确报错并提示补 cookie。
- **环境变量约定**：默认约定使用 `ZHIHU_COOKIE` 作为知乎登录态 Cookie 的环境变量名。
  - feishu-workstation-agent 等调用方，如需在当前机器上携带知乎登录态，应优先尝试从 `ZHIHU_COOKIE` 读取。
  - 设置示例（请只在本机/CI 环境变量里设置，勿写入仓库文件）：
    - PowerShell：
      ```powershell
      $env:ZHIHU_COOKIE = 'q_c1=...; d_c0=...; z_c0=...; SESSIONID=...; ...'
      ```
    - 调用脚本时可通过 `--cookie-env ZHIHU_COOKIE` 显式指定。
- **本地私有 Cookie 文件约定**：为方便日常使用，推荐在项目根目录下建立 `butler_private/zhihu_cookie.txt`（已在 `.gitignore` 中忽略，不会进入仓库），将从浏览器复制的知乎 Cookie 粘贴到该文件中（整行 `q_c1=...; d_c0=...; z_c0=...; SESSIONID=...; ...`）。
  - 示例调用（使用本地私有 Cookie 文件）：
    ```powershell
    & '.venv\Scripts\python.exe' `
      'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
      'https://zhuanlan.zhihu.com/p/2015575496742679437' `
      --platform zhihu `
      --cookie-file 'butler_private/zhihu_cookie.txt' `
      --output-dir 'MyWorkSpace/Research/topics/web_capture_validation'
    ```
- 补 cookie 的最省事方法见 [reference.md](./reference.md)，仅记录「如何从浏览器开发者工具复制 Cookie」和如何维护 `ZHIHU_COOKIE` / `butler_private/zhihu_cookie.txt`，不在任何文档中保存真实 Cookie 值。

## 来源与审阅结论

- 当前实现只保留本地可审阅、可直接运行的抓取脚本。
- 外部 skill 市场和类似 `clawhub` 来源，只作为“有无现成思路”的线索，不直接安装、不直接执行、不直接信任。

