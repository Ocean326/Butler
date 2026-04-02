# 0327 Skill Exposure Plane 与 Codex 消费边界

日期：2026-03-27  
时间标签：0327_0002  
状态：已收口 / 作为本轮 skill 注入分层与接口口径真源

关联文档：

- [00_当日总纲.md](./00_当日总纲.md)
- [0323 全局 skil 与注入](../0323/01D_全局skil与注入.md)
- [0325 Codex 原生能力边界与 Butler 吸收参考](../0325/10_Codex原生能力边界与Butler吸收参考.md)
- [0325 Codex 时代 1_2_3 层收口与并行推进计划](../0325/11_Codex时代1_2_3层收口与并行推进计划.md)

## 一句话裁决

从 `2026-03-27` 起，Butler 的 skill 注入正式收口为：

`skill 真源 / collection 暴露 / provider 注入方式`

三者分离；`Codex CLI` 只负责消费 `skill exposure contract`，不再作为 skill 真源或选择层。

## 当前定位

### 1. 真源在哪

当前唯一 skill 真源继续是：

- `butler_main/sources/skills/`
- `collections/registry.json`
- `collections/prompt_policy.json`

`~/.codex/skills` 或项目外 provider-local skills 只视为某个 CLI 的本地能力包，不直接作为 Butler 全局真源。

### 2. 该放在哪一层

当前正式分层口径固定为：

1. `Domain & Control Plane（领域与控制平面）`
   - skill 真源
   - collection registry
   - prompt policy
   - `SkillExposureContract`
2. `Product Surface（产品表面层） + Domain & Control Plane（领域与控制平面）`
   - 为 chat / campaign / research 选择本次可见的 skill 子集
   - 决定 `collection_id / family_hints / direct_bind`
3. `L1 Agent Execution Runtime（Agent 执行运行时）`
   - 只把上层合同 materialize 成 provider 可消费的形态
   - 对 `Codex CLI` 只做 prompt 拼装、runtime request 透传、provider override 吃入
4. `L2 Durability Substrate（持久化基座）`
   - 只记录跨轮事实、artifact、receipt、状态写回
   - 不拥有 skill 选择和注入策略

## 本轮实现

### 1. 统一 contract

本轮新增统一 `SkillExposureContract`，最小字段为：

- `collection_id`
- `family_hints`
- `direct_skill_names`
- `direct_skill_paths`
- `injection_mode`
- `requires_skill_read`
- `provider_skill_source`
- `provider_overrides`

当前支持的 `injection_mode` 固定为：

- `passive_index`
- `shortlist`
- `direct_bind`
- `tool_api`

### 2. chat 路线

`chat/runtime.py` 现在不再只传裸 `skills_prompt + skill_collection_id`。

当前流程改为：

1. 先根据 `recent_mode + runtime_cli + invocation.metadata.skill_exposure` 归一化出 `SkillExposureContract`
2. 再统一渲染为 skill exposure prompt block
3. 再把结构化 contract 摘要写入 turn metadata

因此 chat 前门、content_share、Codex chat prompt 现在都能共用同一份 exposure 结构，而不是各自拼一套 skills 文本。

### 3. campaign / Codex runtime 路线

`domains/campaign/codex_runtime.py` 现在会：

1. 从 `metadata.skill_exposure` 或 `codex_runtime_request` 里恢复 exposure contract
2. 在 discover / implement / iterate prompt 前统一注入 exposure block
3. 把归一化后的 `skill_exposure` 写入 Codex runtime request
4. 在 runtime artifact metadata 里回写：
   - `skill_exposure`
   - `skill_collection_id`
   - `skill_injection_mode`

### 3.5 控制面 V1 优化补丁

本轮补充把 skill exposure 从“prompt 注入薄层”继续推进到“可治理 exposure plane”：

1. collection registry 现在允许稳定承载：
   - `owner`
   - `status`
   - `allowed_runtimes`
   - `default_injection_mode`
   - `phase_tags`
   - `ui_visibility`
   - `risk_budget`
2. skill registry 增加 diagnostics 视角：
   - 缺失路径
   - 重复 entry
   - inactive/private skill 被 collection 引用
   - 不可读 skill document
3. query / console 现在可以消费结构化 `skill_exposure_observation`，而不是只看 prompt 文本摘要。
4. console 新增 skill 只读管理 API：
   - `GET /console/api/skills/collections`
   - `GET /console/api/skills/collections/{collection_id}`
   - `GET /console/api/skills/families/{family_id}`
   - `GET /console/api/skills/search`
   - `GET /console/api/skills/diagnostics`
5. Draft Board / console draft patch 现在允许写入任务级 `skill_selection`，并在 launch 时收口成 `metadata.skill_exposure`，为未来前端选择面保留稳定合同。

### 4. control plane 默认值

`orchestrator/interfaces/campaign_service.py` 现在对 `campaign_runtime.mode=codex` 的任务，默认补：

- `skill_exposure.collection_id = codex_default`
- `skill_exposure.injection_mode = shortlist`
- `skill_exposure.provider_skill_source = butler`

因此 negotiation 创建的后台 `delivery / research` 任务现在默认有一份可审计的 skill exposure contract，而不是只靠 Codex 自己猜。

### 5. provider override 边界

`agents_os/execution/cli_runner.py` 现在会在解析 runtime request 时读取：

- `skill_exposure.provider_overrides.<provider>.profile`
- `skill_exposure.provider_overrides.<provider>.config_overrides`
- `skill_exposure.provider_overrides.<provider>.extra_args`

但这些字段只影响当前 provider 的 materialization，不回头污染 Butler 的 vendor-neutral 主合同。

## 当前规则

1. 不再把 “Codex 会用到某个本地 skill” 误判成 “Butler 已拥有这个 skill 真源”。
2. 不再让 `L1 Agent Execution Runtime（Agent 执行运行时）` 决定“该暴露哪些 skill”；这一层只吃合同。
3. 不再让 `L2 Durability Substrate（持久化基座）` 承接 skill 注入语义；这一层只记跨轮事实。
4. 任何需要全局复用、长期维护、可审计的 skill，都必须先进入 `sources/skills` 体系。
5. 只有 provider-local、只服务单一 CLI 的 skill，才允许停留在 provider 自己的本地目录里。

## 验收

本轮直接通过的定向回归包括：

- `test_skill_exposure.py`
- `test_talk_runtime_service.py`
- `test_campaign_domain_runtime.py`
- `test_orchestrator_campaign_service.py`
- `test_chat_engine_model_controls.py`
- `test_chat_prompt_support_provider.py`
- `test_agent_soul_prompt.py`
- `test_agents_os_skill_tool.py`

其中已确认通过：

- `62 passed`
- `26 passed`

对应命令：

```bash
.venv/bin/python -m pytest \
  butler_main/butler_bot_code/tests/test_skill_exposure.py \
  butler_main/butler_bot_code/tests/test_talk_runtime_service.py \
  butler_main/butler_bot_code/tests/test_campaign_domain_runtime.py \
  butler_main/butler_bot_code/tests/test_orchestrator_campaign_service.py \
  butler_main/butler_bot_code/tests/test_chat_engine_model_controls.py -q

.venv/bin/python -m pytest \
  butler_main/butler_bot_code/tests/test_chat_prompt_support_provider.py \
  butler_main/butler_bot_code/tests/test_agent_soul_prompt.py \
  butler_main/butler_bot_code/tests/test_agents_os_skill_tool.py -q
```

## 最终结论

当前 Butler 对 skill 注入的正确理解应固定为：

1. `sources/skills` 是真源
2. `SkillExposureContract` 是跨层接口
3. `orchestrator / chat` 负责选择
4. `Codex CLI` 只负责消费

只要这四件事没有同时成立，就说明系统仍在把 skill 注入当成散落 prompt 文案，而不是长期可维护接口。
