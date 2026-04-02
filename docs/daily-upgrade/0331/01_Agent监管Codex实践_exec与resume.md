# Agent 监管 Codex 实践：`exec`、非交互 `resume` 与重试

日期：2026-03-31  
关联：[00_当日总纲.md](./00_当日总纲.md)  
适用范围：宿主 Agent（IDE 内代理、脚本、CI 任务）在本机调用 **Codex CLI**（例如 `codex-cli` 0.117.x），需在 **无 TTY** 环境下 **恢复会话** 并 **循环监管** 至结束。

---

## 1. 原则：不要对宿主 Agent 使用交互式 `codex resume`

- `codex resume` 启动 **TUI**，依赖真实终端：`stdin/stderr` 为 TTY，且 `TERM` 不能是 `dumb`。在 IDE/自动化 shell 中常见报错：拒绝启动交互界面。
- **监管 Agent 应使用**：`codex exec`（非交互）及子命令 `codex exec resume`。

---

## 2. 命令拼写（易错点）

### 2.1 `profile` 位置

以 **2026-03-31** 本机 `codex exec --help` 为准，`-p / --profile` 当前可挂在：

- `codex` 顶层
- `codex exec` 层

但 `codex exec resume --help` 不再重复这项，因此宿主集成的安全规则仍是：

- 把 `--profile` 放在 `resume` 之前
- 不要写成 `codex exec resume -p ...`

```bash
# 当前安全写法 1：挂在顶层
codex -p relay exec resume <SESSION_ID> "<PROMPT>"

# 当前安全写法 2：挂在 exec 层
codex exec -p relay resume <SESSION_ID> "<PROMPT>"

# 仍然错误：resume 子命令自身不接 -p
codex exec resume -p relay <SESSION_ID> "<PROMPT>"
```

### 2.2 非 Git 工作区

若当前目录不在 Codex 信任的 git 仓库内，需加（与 `exec resume` 同列的选项以 `--help` 为准）：

```bash
codex exec -p relay resume <SESSION_ID> "<PROMPT>" --skip-git-repo-check
```

---

## 3. 非交互续会话：`exec resume`

语义与交互 `resume` 对齐，但不进 TUI：

```bash
codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]
```

- `SESSION_ID`：会话 UUID（或与 CLI 帮助一致的线程标识）。
- `PROMPT`：恢复后 **第一条用户消息**；可用 `-` 从 stdin 读。
- `codex exec resume --last`：续最近一条会话（无 picker 时需满足 CLI 对「最近」的过滤条件）。

**示例（带 profile 与非 git）**：

```bash
codex exec -p relay resume 019d3e78-dbc9-7d20-bc86-2f6f11ebd752 "请从中断处继续" \
  --skip-git-repo-check
```

---

## 4. 宿主 Agent 的「监管」模型：一轮进程 = 一轮用户输入

非交互模式下 **没有**「往 TUI 里再打一个字」的通道；所谓「超时或失败就输入继续」，应实现为：

1. 外层循环：`timeout` 包裹单次 `codex exec resume …`。
2. 第 1 轮：传入明确任务续写说明（或空，若业务允许）。
3. 第 2 轮及以后：将 `PROMPT` 设为 **`继续`** 或更具体的纠偏指令（等同新开一轮用户消息）。
4. 以进程 **退出码** 判定本轮成败：`0` 成功；Linux `timeout` 常为 `124`；其他非 0 视为失败，sleep 后进入下一轮。

### 4.1 便于机器解析的输出

- `--json`：向 stdout 输出 **JSONL** 事件流，便于宿主解析 `error` / `turn.*` 等。
- `-o /path/to/last.txt`：将 **最后一条 agent 消息** 写入文件，便于验收或摘要。

### 4.2 自动化执行策略（按需）

- `--full-auto`：较低摩擦的默认组合（参见 `codex exec --help`）。
- `--dangerously-bypass-approvals-and-sandbox`：跳过确认与沙箱；**仅在外部已隔离环境**考虑。

---

## 5. `relay` 与 MCP：重试无法替代 OAuth

若 profile（如 `relay`）挂载了需 **Bearer / OAuth** 的远程 MCP（日志里可能出现 `AuthRequired`、Stripe/Supabase/Vercel 等资源元数据 URL）：

- 单次 `exec` 内可能出现 **Transport channel closed**、**Reconnecting n/5** 等；进程可能长时间挂起或在超时后退出。
- **单纯把 `PROMPT` 改成「继续」不能修复鉴权**；需在 `~/.codex/` 与 profile 配置中为对应 MCP 配置合法 token，或换用 **不依赖这些 MCP** 的 profile，或让人类在支持浏览器登录的环境里先完成授权。

备选架构：宿主若支持 **MCP 客户端**，可起 `codex mcp-server`（stdio），用协议级集成代替反复 spawn `exec`（职责不同，见 `codex mcp-server --help`）。

---

## 6. 验收建议

- **不要**仅依赖 `exit 0`：结合 `--json` 与最终产物（如 `-o` 文件、工作区 diff）判断是否真正完成任务。
- 对长任务：**单轮 `timeout`** 与 **最大轮数** 上限并存，避免无限「继续」冲刷 API。

---

## 7. 与 Butler 仓库的关系

本文记录 **外部 Codex CLI** 与宿主 Agent 的集成方式；Butler 主代码路径仍以仓库内 `docs/project-map/` 与 runtime 合约为准。若将来由 Butler 统一封装「子进程 Codex」，应把 **参数顺序、非 git 标志、MCP 鉴权前置条件** 写入对应 adapter 的运维说明。
