---
type: "note"
---
# 01 Framework Catalog 与 Mapping

日期：2026-03-25
时间标签：0325_0001
状态：已迁入完成态 / framework 吸收背景输入保留

## 目标

1. 建立 Butler 的外部框架登记层。
2. 统一记录 Butler 应吸收什么、不应照搬什么。
3. 让 framework knowledge 最终能下沉到 package / contract / runtime binding。

## 今日要完成的事

1. 设计 `framework catalog` 最小字段。
2. 设计 `framework mapping spec` 最小字段。
3. 第一批登记：
   - `gstack`
   - `Superpowers`
   - `OpenFang`
   - `LangGraph`
   - `OpenAI Agents SDK`
   - `AutoGen`
   - `CrewAI`
   - `MetaGPT`
   - `OpenHands`
   - `Temporal`
4. 为每个 framework 明确它在 Butler 里映射到哪一层。
5. 为每个 framework 补最小吸收结论：
   - 吸收的对象
   - 不照搬的对象
   - 对应 Butler package / contract / policy 位置

## 验收标准

1. Butler 第一次拥有正式的 framework knowledge plane 入口。
2. `OpenFang` 被吸收为 Agent OS / package / governance 参考项，而不是被误读成 Butler 要复制的产品壳层。

## 范围边界

### 这一路必须回答

1. Butler 如何登记一个外部框架。
2. Butler 如何描述“吸收什么、不吸收什么、映射到 Butler 哪一层”。
3. Butler 如何把 framework knowledge 交给 compiler，而不是停在调研文档。

### 这一路不要做

1. 不在这里直接实现 runtime 执行。
2. 不在这里直接写 framework-specific prompt。
3. 不在这里替 `Lane B` 写编译逻辑。

## 建议代码落点

1. `butler_main/orchestrator/framework_catalog.py`
   - framework 条目模型
   - catalog 读写
2. `butler_main/orchestrator/framework_mapping.py`
   - mapping spec 模型
   - absorb / reject / project 到 Butler layer 的规则
3. `butler_main/orchestrator/__init__.py`
   - 暴露 catalog / mapping API
4. 测试优先放在：
   - `butler_main/butler_bot_code/tests/test_orchestrator_package_bootstrap.py`
   - 新增 `test_orchestrator_framework_catalog.py`
   - 新增 `test_orchestrator_framework_mapping.py`

## 这一路对其他 lane 的输出

1. 给 `Lane B`：
   - 冻结后的 `framework_id`
   - `mapping spec`
   - `compiler hints`
   - `package / governance defaults`
2. 给 `Lane D`：
   - 选定的 demo framework profile
   - 每个 demo profile 的 Butler 吸收结论

## 这一路的最小 schema

1. `framework catalog entry`
   - `framework_id`
   - `display_name`
   - `source_kind`
   - `focus_layers`
   - `strengths`
   - `non_goals`
   - `status`
2. `framework mapping spec`
   - `framework_id`
   - `source_terms`
   - `butler_targets`
   - `absorbed_packages`
   - `governance_defaults`
   - `runtime_binding_hints`
   - `compiler_profile_templates`

## 执行拆解

1. 第一阶段：冻结 schema
   - 不求全，只求给后续编译器一个稳定输入。
2. 第二阶段：录入第一批 framework
   - 至少覆盖 `Superpowers / gstack / OpenFang / LangGraph / OpenAI Agents SDK`。
3. 第三阶段：形成两条示范 mapping
   - 一条偏 `task flow`
   - 一条偏 `autonomous package / governance`
4. 第四阶段：补测试与导出接口

## 首日动作

1. 先把 `framework catalog entry` 和 `mapping spec` 写成 dataclass 或等价对象。
2. 先录入 3 个最关键 profile：
   - `Superpowers`
   - `gstack`
   - `OpenFang`
3. 先冻结一版字段清单，再允许继续补 framework 数量。

## 风险与缓解

1. 风险：framework 条目越记越散，重新变成调研清单。
   - 缓解：每个条目必须带 `butler_targets` 和 `compiler_profile_templates`。
2. 风险：字段太大，导致 `Lane B` 不敢消费。
   - 缓解：强制区分 `required fields` 与 `optional notes`。
3. 风险：把 `OpenFang` 当产品壳照抄。
   - 缓解：只记录它对 Butler 的 `capability package / governance / autonomy` 启发，不记录 UI 壳层。
