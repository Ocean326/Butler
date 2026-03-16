---
name: web-note-capture-cn
description: 抓取知乎专栏、小红书分享页等中文网页内容。用于用户给出 zhihu/xiaohongshu/xhslink 链接并要求提取标题、正文、作者、图片、互动数据、导出 Markdown/JSON 的场景。优先使用本 skill 提供的本地脚本，默认只做 HTTP 抓取与可选 cookie 读取，不安装未知外部依赖。
category: research
trigger_examples: 知乎链接抓取, 小红书链接抓取, xhslink解析, 网页内容提取, 专栏正文导出
allowed_roles: feishu-workstation-agent, butler-continuation-agent, heartbeat-executor-agent
risk_level: medium
heartbeat_safe: true
requires_skill_read: true
---

# Web Note Capture CN

用于抓取中文内容平台里的“单篇网页/笔记/专栏”。

当前脚本重点支持：

- 知乎专栏 `zhuanlan.zhihu.com`
- 小红书分享页 `xiaohongshu.com`
- 小红书短链 `xhslink.com`

## 本 skill 的边界

- 默认只使用本地 Python 脚本和 `requests`，不联网安装未知依赖。
- 不直接执行外部 skill 或来源仓库里的可执行脚本；外部来源只作为人工审阅线索。
- 不在 Butler 主代码里硬塞平台逆向逻辑；平台抓取入口都留在本 skill 下。
- 不承诺绕过平台风控。知乎若出现 403，会提示补充登录 cookie 后重试。

## 入口脚本

- 脚本路径：`./butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py`
- 推荐运行方式：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py' `
  'https://www.xiaohongshu.com/explore?...' `
  --output-dir '工作区/网页抓取验证'
```

## 常用命令

小红书分享页：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py' `
  'https://www.xiaohongshu.com/explore?...' `
  --platform xiaohongshu `
  --output-dir '工作区/网页抓取验证'
```

小红书分享文案里夹着 `xhslink` 短链：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py' `
  '科研龙虾上线 72 小时，我做了什么｜开发日记 🦞我的... http://xhslink.com/o/xxxxx 复制后打开【小红书】查看笔记！' `
  --output-dir '工作区/网页抓取验证'
```

知乎专栏，未登录先试一次：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py' `
  'https://zhuanlan.zhihu.com/p/2013979334365434808?share_code=o8iY49m1fwAX&utm_psn=2016686371469817350' `
  --platform zhihu `
  --output-dir '工作区/网页抓取验证'
```

知乎若被 403，补 cookie 重跑：

```powershell
$env:ZHIHU_COOKIE = 'd_c0=...; z_c0=...'
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py' `
  'https://zhuanlan.zhihu.com/p/2013979334365434808?share_code=o8iY49m1fwAX&utm_psn=2016686371469817350' `
  --platform zhihu `
  --cookie-env ZHIHU_COOKIE `
  --output-dir '工作区/网页抓取验证'
```

## 输出

脚本会输出：

- 标准化 JSON
- 对应 Markdown

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
- `tags`
- `engagement`
- `status`

## 与图片 OCR 的衔接

当抓取结果中包含 `images` 字段时，推荐配合 `web-image-ocr-cn` skill 做第二阶段 OCR：

- Step1：使用本 skill 抓取网页，生成 `...json` 与 `...md`；
- Step2：调用 `web-image-ocr-cn`：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/butler_bot_agent/skills/web-image-ocr-cn/scripts/image_ocr.py' `
  --from-capture-json '工作区/网页抓取验证/xiaohongshu_xxxxxx.json' `
  --output-dir 'BrainStorm/Raw'
```

feishu-workstation-agent 在对话场景下，应视为**默认行为**：当用户让你「抓这篇小红书 / 知乎」且返回结果含图片时，**自动**再走一轮 OCR，将识别出的关键文字一并总结给用户，并在需要时把 OCR Markdown 落入 `BrainStorm/Raw`。无需用户每轮重复「有图就 OCR」。

**归档自检（调用方契约）**：凡将抓取结果归档到 BrainStorm 前，必须自检——若结果含 `images` 且尚未跑过 OCR，则先调用 `web-image-ocr-cn` 再落盘；落盘后若首图/图片区内容为空且原始抓取确有图，视为未完成，应补跑 OCR 并更新归档。用户索要「刚刚那条」首图内容时，若 Raw 无 OCR 结果，先补跑抓取+OCR 再回复，不仅回复「当前无数据」。

## 平台说明

### 小红书

- 默认走分享页 HTML 首屏数据解析，当前对标题、正文、作者、图片、互动数提取较稳。
- 评论默认不抓，因为页面首屏通常不带完整评论列表。

### 知乎

- 未登录抓取经常命中 403 挑战页。
- 本脚本会先做公开请求；若被挡，会明确报错并提示补 cookie。
- 补 cookie 的最省事方法见 [reference.md](./reference.md)。
- 现在cookie为：q_c1=313b2c73ea1743db9011878abd718071|1740624355000|1740624355000; __snaker__id=OwlQ1BgByciN06LI; _xsrf=T4HFp8YX2na7u3jBfx8iKENbBT8FlJuV; _zap=1dbaa790-c7dc-4e88-bfe3-e8f90b279b52; d_c0=foGUOMjR6xuPTj7UosZmSZWPGt823PJ3rds=|1772462044; __zse_ck=005_RlNAU3HnWUSwIOsClBBIE4hURkCSzPq9JTJcvgzREe6QSBFQv5QqEZhyu3qzrQE=6a6QWPwcTFHMUkfU4WkRzuhPzfMHwEIUtTFXE2C3IIkeAOHS3DWpdS=vEw4hFcC0-KrF5mfU/Nn7SNwruCoZeanZGypmYueDGYgIrZLxOp2B3mkUP+ICyobFKnnVtTciU4CNhe5gu2x76b471+rrZFU9qY6qumqf/OQCBtpduIGglNqrcYUwcVIliQUuHELJiuwxzww/FnTwMDJBTH9NA7Q==; BEC=9de1a923fbc880d97a5571e917aeb532; z_c0=2|1:0|10:1773601938|4:z_c0|92:Mi4xZ1ZJTUxnQUFBQUItZ1pRNHlOSHJHeVlBQUFCZ0FsVk4zTzJTYWdEb2RnM1hZWUd1M1psVXBnRUtiSDVRTEhIZ2Vn|bb82a5c2a9ba351da6b4b3632c63f1d0dcdc34e8fe45ce8b3f8e95080aed2021; Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49=1773224690,1773569242,1773597748,1773601939; Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49=1773601939; HMACCOUNT=796B3AA5F6ADE7D3; SESSIONID=IHChY6CyyBaFQ8aN5aPileWUT48gH1Bf4R7zaEbolFw; JOID=Ul0RB09K009w-0vcdk8yVaVEl3NqBpoMGKZ4ng83lC82qne4OdzW-B36T912Zkqd6Jq_Gej-f1BtUzaQVevvFmA=; osd=W14UCkxD0Ep9-ELfc0IxXKZBmnBjBZ8BG697mwI0nSwzp3SxOtnb-xT5StB1b0mY5Zm2Gu3zfFluVjuTXOjqG2M=

## 来源与审阅结论

- 当前实现只保留本地可审阅、可直接运行的抓取脚本。
- 外部 skill 市场和类似 `clawhub` 来源，只作为“有无现成思路”的线索，不直接安装、不直接执行、不直接信任。
