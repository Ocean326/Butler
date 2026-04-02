# 0316 执行结果：Bootstrap 升级落地

## 1. 本轮已完成

本轮按 `1534_bootstrap升级方案和计划.md` 落地了第一阶段到第二阶段（真源建立 + 三链接入），核心完成项如下。

1. 新建 Bootstrap 真源目录
   - `butler_main/butler_bot_agent/bootstrap/`
2. 新建 8 个真源文件
   - `SOUL.md`
   - `TALK.md`
   - `HEARTBEAT.md`
   - `EXECUTOR.md`
   - `SELF_MIND.md`
   - `USER.md`
   - `TOOLS.md`
   - `MEMORY_POLICY.md`
3. 新增 bootstrap 加载服务
   - `butler_main/butler_bot_code/butler_bot/services/bootstrap_loader_service.py`
4. 接入 talk prompt
   - `butler_main/butler_bot_code/butler_bot/agent.py`
5. 接入 self_mind cycle/chat prompt
   - `butler_main/butler_bot_code/butler_bot/services/self_mind_prompt_service.py`
6. 接入 heartbeat planner/executor prompt
   - `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
7. 路径常量补齐
   - `butler_main/butler_bot_code/butler_bot/butler_paths.py`

---

## 2. 结构变化

### 2.1 Talk

`build_feishu_agent_prompt()` 现在会先加载 `talk` 会话的 bootstrap 组合（`SOUL/TALK/USER/TOOLS/MEMORY_POLICY`）再组 prompt，不再只靠代码里的硬编码行为块。

### 2.2 Self-Mind

`build_cycle_prompt()` / `build_chat_prompt()` 现在会注入 `self_mind` 会话的 bootstrap 组合（`SOUL/SELF_MIND/USER/MEMORY_POLICY`），确保 self_mind 有自己的真源。

### 2.3 Heartbeat

1. planner prompt 会注入 `heartbeat_planner` bootstrap（`HEARTBEAT/TOOLS/MEMORY_POLICY`）。
2. executor branch prompt 会注入 `heartbeat_executor` bootstrap（`EXECUTOR/TOOLS/MEMORY_POLICY`）。

---

## 3. 验证结果

本轮执行了这组回归测试并通过：

1. `test_agent_soul_prompt.py`
2. `test_self_mind_services.py`
3. `test_heartbeat_orchestration.py`
4. `test_memory_manager_recent.py`

结果：`82 passed`

服务已重启，bootstrap 改动已上线。

---

## 4. 当前边界（重要）

这轮是“bootstrap 真源接入”而不是“彻底移除旧拼接逻辑”。

当前仍存在的边界：

1. 部分历史硬编码规则仍在 `agent.py`、`heartbeat_orchestration.py` 内共存。
2. `recent` 仍有一部分以文本方式拼接，尚未完全升级为结构化 context schema。
3. role 文档与 bootstrap 之间尚未完成全量去重，仍有重复行为描述。

---

## 5. 下一步建议

按原方案继续，建议顺序：

1. 收口 talk：把剩余硬编码行为块迁到 `bootstrap/TALK.md`，代码只留最小组装逻辑。
2. 收口 memory：把 `recent` 注入改为结构化块，避免混入用户消息正文。
3. 收口 role：把 `feishu-workstation-agent.md` 中与 bootstrap 重复的行为规则降到最小，只保留入口职责。
