# Butler

这是 Butler 体系的唯一规范根目录。

## 目录结构

1. `butler_main/`
   主 Butler 工程，包含对话主进程、heartbeat、记忆、agent、工作区映射与运行脚本。
2. `guardian/`
   独立 guardian 工程，负责审阅升级请求、维护修复、重启、回滚与统一运维入口。

## 结构约定

1. `butler_main` 是原始 Butler 主工程的规范名称。
2. `guardian` 是与 `butler_main` 并列的独立维护工程，不再作为临时脚本散落在主工程外。
3. 以后任何目录调整、脚本新增、运行入口说明，都应先在本目录和对应子项目 README 中声明。

## 唯一重启约定

以后 Butler 的重启、恢复、上线、回滚，统一走 guardian 的脚本与流程。

唯一允许的运维入口是：

1. `Butler/guardian/manager.ps1`

### 重启前 Git 快照约定（可回滚）

任何**涉及代码或配置改动**并准备通过 `guardian/manager.ps1` 重启 / 上线 / 回滚时，必须先在 Butler 根目录执行一次完整快照：

```bash
git status           # 确认当前改动
git add .            # 暂存当前工作树（含 .gitignore 允许的文件）
git commit -m "说明本次修改与重启原因"
```

这样可以保证：一旦重启后效果不佳，可以通过 `git log` / `git revert` / `git reset` 等方式快速回滚到重启前的稳定状态。

禁止继续新增以下类型的脚本：

1. 主工程里新的平行 `restart_*.ps1`
2. 主工程里新的临时 `start_*.ps1` / `stop_*.ps1` / `fix_*.ps1`
3. 让其他语言模型临时创建、但未被 guardian 接管和记录的重启脚本

## 责任划分

### butler_main

1. 负责用户对话
2. 负责 heartbeat 规划与执行
3. 负责记忆、任务、工作区协作
4. 轻量修复可以先备案给 guardian 后自行执行

### guardian

1. 负责 keep Butler alive
2. 负责审阅 upgrade / repair request
3. 负责涉及代码改动或重启的修复主导
4. 负责统一测试、重启、上线、回滚
5. 负责写入 guardian ledger，避免未来继续长出错误脚本

## 公开仓库边界

准备初始化 git 并逐步开放给他人体验时，默认边界如下：

1. `butler_main/butler_bot_agent/agents/local_memory/Butler_SOUL.md` 属于项目公共人格，可以进入仓库。
2. `butler_main/butler_bot_agent/agents/local_memory/Current_User_Profile.template.md` 属于公共模板，可以进入仓库。
3. `butler_main/butler_bot_agent/agents/local_memory/Current_User_Profile.private.md` 属于当前用户私有画像，不应进入仓库。
4. `butler_main/butler_bot_agent/agents/recent_memory/`、`agents/state/`、运行日志、运行态 `json/jsonl` 默认视为本地状态，不应进入仓库。
5. 以后若继续拆分个性化偏好，优先放入当前用户画像或其他私有记忆层，不直接写进公共 Soul 与主角色提示词。

## 迁移说明

旧目录 `Bulter/` 不再是规范根，只保留为当前工作区会话的过渡壳。
后续应以 `Butler/` 作为唯一入口重新打开工作区并继续开发。