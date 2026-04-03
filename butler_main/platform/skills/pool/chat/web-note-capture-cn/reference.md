# Web Note Capture CN Reference

## 知乎 cookie 最省事补法

当知乎返回 403 时，只需要补一次登录态 cookie。

步骤：

1. 用浏览器正常登录知乎并打开目标专栏页。
2. 打开开发者工具，切到 `Network`。
3. 刷新页面，点开当前文章请求。
4. 复制请求头里的 `cookie` 整行值。
5. 任选一种方式传给脚本：

方式 A，环境变量：

```powershell
$env:ZHIHU_COOKIE = 'd_c0=...; z_c0=...'
```

方式 B，文本文件：

```powershell
Set-Content -Path '工作区/网页抓取验证/zhihu_cookie.txt' -Value 'd_c0=...; z_c0=...'
```

对应命令：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
  'https://zhuanlan.zhihu.com/p/2013979334365434808?share_code=o8iY49m1fwAX&utm_psn=2016686371469817350' `
  --platform zhihu `
  --cookie-env ZHIHU_COOKIE `
  --output-dir '工作区/网页抓取验证'
```

或：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/chat/web-note-capture-cn/scripts/social_capture.py' `
  'https://zhuanlan.zhihu.com/p/2013979334365434808?share_code=o8iY49m1fwAX&utm_psn=2016686371469817350' `
  --platform zhihu `
  --cookie-file '工作区/网页抓取验证/zhihu_cookie.txt' `
  --output-dir '工作区/网页抓取验证'
```

## 小红书说明

- 当前分享页 HTML 可直接解析出正文、标题、作者、图片和互动数据。
- `xhslink.com` 短链可以直接交给脚本，脚本会先跟随跳转。
