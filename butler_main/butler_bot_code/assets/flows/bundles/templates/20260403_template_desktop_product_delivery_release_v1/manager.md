# Manager Notes · template_desktop_product_delivery_release_v1

## Asset Identity
- asset_kind: template
- asset_id: 20260403_template_desktop_product_delivery_release_v1
- goal: 交付正式桌面产品：功能完整、交互简洁优雅、运行稳定、缺陷控制在可发布水平，并提供官方 Linux、macOS、Windows 安装/分发包与对应发布说明。
- guard_condition: 仅在同时满足时可结案：核心功能已闭环且关键路径可演示；UX 打磨一致、可用性达标；阻断级/高优先级缺陷已清零，或已书面降级并获认可；三平台 release 产物齐备且可复现构建；发布说明、验证与发布检查清单已完成并对照通过。

## Reuse Guidance
- Default to discussing and refining this asset before creating any concrete flow from it.
- Prefer template-first: if this asset is being used to shape a new task, settle the reusable template contract before instantiating a pending flow.

## Manager Checklist
- Clarify what should stay reusable at the template layer and what is specific to the current run.
- Align `goal`, `guard_condition`, and `phase_plan` before creating or updating a flow instance.
- Check whether `supervisor.md` also needs to be updated so the runtime instruction matches the newly agreed flow intent.
- Ask for explicit confirmation before mutating the template or creating a new flow.
