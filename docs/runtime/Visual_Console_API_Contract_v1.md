# Visual Console API Contract v1

日期：2026-03-30  
版本：v1  
范围：可视化后台控制台、operator harness 与前门 Draft Board 的 API/数据合同

## 1. 目标

本合同定义 Butler 可视化控制台的最小 API 与数据结构，确保：

1. 前端不直接读取内部 store 文件。
2. 图面、控制、草案都走统一可审计的 control plane。
3. `WorkflowIR` 与 campaign/session 仍是唯一运行时真源。

## 1.1 0331 对齐补充

自 `2026-03-31` 起，campaign 新主线已切到 `campaign ledger -> workflow_session -> agent turn receipt -> harness`。  
因此 visual console 的 campaign 主视图也同步改成：

1. 自然语言 `task_summary` 优先
2. `latest_turn_receipt` 与 `latest_delivery_refs` 作为一线 operator 事实
3. graph / board 默认展示 `ledger -> turn -> delivery -> harness`
4. operator 主动作收口为 `pause / resume / abort / annotate_governance / force_recover_from_snapshot / append_feedback`
5. `force_transition / skip_to_step` 只保留 legacy/best-effort 兼容，不再是主 UX 合同

## 2. 对外 API（建议路径）

当前现役集合如下，前半部分是 0326 的 V1 基线，后半部分是 0330 已实施的 operator harness / authoring 扩展：

- `GET /console/api/runtime`
- `GET /console/api/access`
- `GET /console/api/global/board`
- `GET /console/api/campaigns`
- `GET /console/api/campaigns/{campaign_id}`
- `GET /console/api/campaigns/{campaign_id}/graph`
- `GET /console/api/campaigns/{campaign_id}/board`
- `GET /console/api/campaigns/{campaign_id}/control-plane`
- `GET /console/api/campaigns/{campaign_id}/transition-options`
- `GET /console/api/campaigns/{campaign_id}/recovery-candidates`
- `GET /console/api/campaigns/{campaign_id}/audit-actions`
- `GET /console/api/campaigns/{campaign_id}/audit-actions/{action_id}`
- `GET|PATCH /console/api/campaigns/{campaign_id}/prompt-surface`
- `GET|PATCH /console/api/campaigns/{campaign_id}/agents/{node_id}/prompt-surface`
- `GET|PATCH /console/api/campaigns/{campaign_id}/workflow-authoring`
- `GET /console/api/campaigns/{campaign_id}/agents/{node_id}/detail`
- `GET /console/api/campaigns/{campaign_id}/artifacts/{artifact_id}/preview`
- `GET /console/api/campaigns/{campaign_id}/events`
- `GET /console/api/campaigns/{campaign_id}/events/stream`
- `POST /console/api/campaigns/{campaign_id}/actions`
- `GET /console/api/drafts`
- `GET /console/api/drafts/{draft_id}`
- `PATCH /console/api/drafts/{draft_id}`
- `GET|PATCH /console/api/drafts/{draft_id}/workflow-authoring`
- `GET|POST /console/api/drafts/{draft_id}/compile-preview`
- `POST /console/api/drafts/{draft_id}/launch`
- `GET /console/api/skills/collections`
- `GET /console/api/skills/collections/{collection_id}`
- `GET /console/api/skills/families/{family_id}`
- `GET /console/api/skills/search`
- `GET /console/api/skills/diagnostics`
- `GET /console/api/channels/{session_id}`

## 3. 核心类型

### 3.1 GraphSnapshot

```json
{
  "graph_level": "campaign",
  "revision_id": "rev_20260326_01",
  "campaign_id": "campaign_xxx",
  "workflow_session_id": "session_xxx",
  "phase_path": ["ledger", "turn", "delivery", "harness"],
  "active_path": ["ledger", "turn"],
  "nodes": [],
  "edges": [],
  "inspector_defaults": {
    "selected_node_id": "turn"
  },
  "available_actions": ["pause", "append_feedback", "annotate_governance", "force_recover_from_snapshot", "abort"]
}
```

### 3.2 GraphNodeView

```json
{
  "id": "turn",
  "kind": "campaign_surface_node",
  "title": "Supervisor Turn",
  "status": "active",
  "phase": "turn",
  "role_id": "campaign_supervisor",
  "artifact_refs": ["bundle/delivery.md"],
  "badges": ["Running", "1 outputs"],
  "action_state": {
    "can_retry": true,
    "can_reroute": false
  }
}
```

### 3.3 GraphEdgeView

```json
{
  "id": "turn__next__delivery",
  "source": "turn",
  "target": "delivery",
  "kind": "next",
  "condition": "next",
  "active": true
}
```

### 3.4 FrontdoorDraftView

```json
{
  "draft_id": "draft_20260326_xxx",
  "session_id": "session_xxx",
  "mode_id": "research",
  "goal": "Build a visual console for Butler",
  "materials": ["..."],
  "hard_constraints": ["..."],
  "acceptance_criteria": ["..."],
  "recommended_template_id": "campaign.research_then_implement",
  "selected_template_id": "campaign.research_then_implement",
  "composition_mode": "template",
  "pending_confirmation": false,
  "linked_campaign_id": "campaign_xxx",
  "frontdoor_ref": {
    "channel": "feishu",
    "thread_id": "xxx"
  },
  "governance_defaults": {
    "risk_level": "medium",
    "autonomy_profile": "reviewed_delivery"
  }
}
```

### 3.5 ControlActionRequest / ControlActionResult

```json
{
  "action": "annotate_governance",
  "target_kind": "campaign",
  "target_scope": "campaign",
  "target_node_id": "",
  "target_id": "campaign_xxx",
  "transition_to": "",
  "resume_from": "",
  "check_ids": [],
  "feedback": "",
  "prompt_patch": {},
  "workflow_patch": {},
  "reason": "tighten governance before the next turn",
  "operator_reason": "tighten governance before the next turn",
  "policy_source": "console.action",
  "payload": {
    "risk_level": "high",
    "autonomy_profile": "guarded"
  },
  "operator_id": "console_user"
}
```

```json
{
  "ok": true,
  "campaign_id": "campaign_xxx",
  "mission_id": "mission_xxx",
  "applied_at": "2026-03-26T20:00:00Z",
  "result_summary": "paused",
  "audit_event_id": "evt_xxx",
  "trace_id": "trace_xxx",
  "receipt_id": "operator_receipt_xxx",
  "recovery_decision_id": "recovery_decision_xxx"
}
```

### 3.6 ControlPlaneEnvelope

```json
{
  "campaign_id": "campaign_xxx",
  "canonical_session_id": "workflow_session_xxx",
  "macro_state": "running",
  "execution_state": "running",
  "closure_state": "open",
  "narrative_summary": "agent completed one supervisor turn and committed the latest summary",
  "progress_reason": "agent completed one supervisor turn and committed the latest summary",
  "closure_reason": "",
  "operator_next_action": "review the latest delivery and decide whether to resume another turn",
  "approval_state": "requested",
  "risk_level": "medium",
  "autonomy_profile": "reviewed_delivery",
  "latest_turn_receipt": {
    "turn_id": "turn_xxx",
    "summary": "implemented the first bounded pass",
    "yield_reason": "awaiting operator review"
  },
  "latest_delivery_refs": ["bundle/report.md"],
  "harness_summary": {
    "turn_count": 1,
    "artifact_count": 2,
    "session_event_count": 5
  },
  "available_actions": ["pause", "append_feedback", "annotate_governance", "force_recover_from_snapshot", "abort"],
  "transition_options": [
    {
      "action": "resume",
      "label": "Resume Turn"
    }
  ],
  "recovery_candidates": [
    {
      "action": "force_recover_from_snapshot",
      "label": "Recover canonical session"
    }
  ],
  "audit_summary": {
    "action_count": 2
  }
}
```

### 3.7 PromptSurfaceEnvelope

```json
{
  "campaign_id": "campaign_xxx",
  "node_id": "implement",
  "phase_id": "implement",
  "structured_contract": {
    "skill_exposure": {},
    "governance_contract": {},
    "planning_contract": {},
    "template_contract": {},
    "prompt_surface": {},
    "node_overlay": {}
  },
  "preview": {
    "preview_kind": "estimated_materialization",
    "final_prompt": "...",
    "prompt_length": 1024
  },
  "policy_sources": {},
  "audit_summary": {}
}
```

### 3.8 WorkflowAuthoringEnvelope / CompilePreviewEnvelope

```json
{
  "scope": "campaign",
  "scope_id": "campaign_xxx",
  "template_id": "campaign.single_repo_delivery",
  "template_label": "Single Repo Delivery",
  "composition_mode": "template",
  "skeleton_changed": false,
  "phase_plan": ["discover", "implement", "evaluate", "iterate"],
  "role_plan": ["campaign_supervisor", "campaign_reviewer"],
  "transition_rules": [],
  "recovery_entries": []
}
```

```json
{
  "scope": "draft",
  "scope_id": "draft_xxx",
  "template_id": "campaign.single_repo_delivery",
  "compile_result": "ready",
  "validation_errors": [],
  "warnings": [],
  "risk_hints": ["phase_count=4", "role_count=2"],
  "compiled_contract": {}
}
```

### 3.9 AuditActionRecord

```json
{
  "action_id": "operator_action_xxx",
  "action_type": "workflow_authoring_patch",
  "target_scope": "campaign",
  "target_node_id": "",
  "trace_id": "trace_xxx",
  "result_summary": "workflow authoring updated",
  "patch_receipt": {},
  "recovery_decision": {}
}
```

### 3.6 ConsoleEventEnvelope (SSE)

```json
{
  "scope": "campaign",
  "scope_id": "campaign_xxx",
  "event_id": "evt_xxx",
  "event_type": "campaign_event",
  "created_at": "2026-03-26T20:00:00Z",
  "severity": "info",
  "payload": {
    "event_type": "phase_transition",
    "phase": "review",
    "iteration": 2
  }
}
```

### 3.7 ChannelThreadSummary

```json
{
  "channel": "feishu",
  "session_id": "session_xxx",
  "thread_id": "om_...",
  "latest_user_message": "进度怎么样",
  "latest_system_message": "campaign progress...",
  "jump_link": "https://..."
}
```

### 3.8 BoardSnapshot

```json
{
  "scope": "campaign",
  "scope_id": "campaign_xxx",
  "snapshot_id": "campaign_xxx_rev01",
  "title": "Campaign title",
  "status": "active",
  "summary": "active · current Implement · next Evaluate",
  "idle_reason": "",
  "current_agent": {},
  "next_agent": {},
  "running_agents": [],
  "next_agents": [],
  "queued_agents": [],
  "nodes": [],
  "edges": [],
  "artifacts": [],
  "records": [],
  "preview_defaults": {
    "selected_node_id": "implement",
    "preview_artifact_id": "artifact_xxx",
    "mode": "graph"
  }
}
```

`timeline_items` 的事件节点在 0327 收尾后补充以下布局/详情字段：

```json
{
  "id": "evt_xxx",
  "kind": "event",
  "timestamp": "2026-03-27T09:00:00+00:00",
  "anchor_timestamp": "2026-03-27T09:00:00+00:00",
  "display_title": "Review Done",
  "display_brief": "evaluate",
  "detail_available": true,
  "detail_campaign_id": "campaign_xxx",
  "detail_node_id": "evaluate",
  "anchor_x": 184.0,
  "layout_x": 232.0
}
```

其中：

1. `anchor_*` 表示真实时间锚点。
2. `layout_x` 表示单排避让后的卡片位置。
3. 前端必须允许 `layout_x` 相对 `anchor_x` 右移，但不能把时间轴排成多行。

### 3.10 AgentDetailEnvelope

```json
{
  "campaign_id": "campaign_xxx",
  "node_id": "implement",
  "title": "Execution Pass",
  "status": "running",
  "execution_state": "running",
  "role_id": "campaign_supervisor",
  "role_label": "Supervisor",
  "agent_spec_id": "codex",
  "subtitle": "campaign_supervisor · codex",
  "updated_at": "2026-03-27T09:00:00+00:00",
  "overview": {},
  "planned_input": {},
  "live_records": [],
  "artifacts": [],
  "raw_records": []
}
```

### 3.11 AccessDiagnostics

```json
{
  "listen_host": "0.0.0.0",
  "port": 8765,
  "base_path": "/console/",
  "local_urls": ["http://127.0.0.1:8765/console/"],
  "lan_urls": ["http://10.134.142.90:8765/console/"],
  "note": "console is listening on all interfaces; cross-device failures are likely caused by network policy outside Butler",
  "hints": []
}
```

补充约束：

1. `GET /console/` 返回的入口 HTML 必须把静态资源引用到 `/console/assets/...`，不能回退成根路径 `/assets/...`。
2. 若前端构建产物仍输出根路径资源，WSGI server 需要在返回 `index.html` 时做兼容重写，避免出现页面可达但 JS/CSS 404 的假可用状态。

### 3.12 SkillExposureObservation

```json
{
  "collection_id": "codex_default",
  "collection_known": true,
  "collection_family_count": 6,
  "collection_skill_count": 22,
  "selected_family_ids": ["research"],
  "selected_family_labels": ["Research"],
  "selected_skill_names": ["pdf-read"],
  "direct_skill_names": ["pdf-read"],
  "direct_skill_paths": [],
  "injection_mode": "shortlist",
  "requires_skill_read": true,
  "provider_skill_source": "butler",
  "provider_override_keys": ["codex"],
  "materialization_mode": "prompt_block",
  "fallback_reason": ""
}
```

### 3.13 SkillCollectionView

```json
{
  "collection_id": "codex_default",
  "description": "codex chat 路线默认暴露的 skills。",
  "owner": "butler",
  "status": "active",
  "allowed_runtimes": ["chat", "campaign", "console"],
  "default_injection_mode": "shortlist",
  "risk_budget": "",
  "phase_tags": ["discover", "implement", "iterate"],
  "ui_visibility": "visible",
  "entry_count": 22,
  "skill_count": 22,
  "family_count": 6,
  "diagnostic_count": 0
}
```

### 3.14 PreviewEnvelope

```json
{
  "scope": "campaign",
  "scope_id": "campaign_xxx",
  "item_id": "artifact_xxx",
  "title": "Implementation report iteration 1",
  "kind": "implementation_report",
  "preview_kind": "text",
  "language": "json",
  "content": "{ ... }",
  "content_path": "/abs/path/to/file.json",
  "metadata": {}
}
```

## 4. 生成规则（V1）

1. `GraphSnapshot` 的结构与 `WorkflowIR` + campaign/session view 组合生成。
2. `GraphNodeView` 优先从 `WorkflowIR.steps` 与 `workflow_session` 的 active step 合成。
3. `GraphEdgeView` 优先从 `WorkflowIR.edges` 生成。
4. `events` JSON 接口可作为前端轮询回退；`events/stream` 作为 SSE 增量接口。
5. `FrontdoorDraftView` 来自 `CampaignNegotiationDraft` + frontdoor metadata。
6. `ControlActionResult` 必须写审计事件，并返回 `campaign_id / mission_id`。
7. `BoardSnapshot` 用于三栏工作台主画布，支持全局调度视图和单项目节点视图。
8. `AgentDetailEnvelope` 用于全屏 agent detail 层；若目标节点在刷新后消失，前端应保留 stale placeholder，而不是强制关闭。
9. `AccessDiagnostics` 必须能解释“已监听但其他设备打不开”的常见原因，避免把网络策略问题误判成 Butler 未启动。
10. `PromptSurfaceEnvelope` 中的 `preview.final_prompt` 只是估算物化结果，不作为 runtime prompt 真源。
11. `WorkflowAuthoringEnvelope` / `CompilePreviewEnvelope` 服务于 authoring shell，不反向成为 workflow session 真源。
12. `PreviewEnvelope` 这一轮只承诺文本优先预览；二进制文件返回 metadata + open hint。

## 5. 稳定性与边界

1. console API 不直接写 runtime 文件。
2. 任何控制动作必须通过 orchestrator/control plane 统一入口。
3. draft 与 campaign 的 workflow patch 只允许结构化字段更新，不允许直接改 workflow session 真源。
4. operator patch / recovery / audit 必须经过 control plane，且要留下 `trace_id / receipt_id / recovery_decision_id`。
5. V1 不承诺多租户权限隔离，默认内部可信入口。
