# Supervisor Notes · template_desktop_product_delivery_release_v1

- Preserve the flow goal: 交付正式桌面产品：功能完整、交互简洁优雅、运行稳定、缺陷控制在可发布水平，并提供官方 Linux、macOS、Windows 安装/分发包与对应发布说明。
- Respect the guard condition: 仅在同时满足时可结案：核心功能已闭环且关键路径可演示；UX 打磨一致、可用性达标；阻断级/高优先级缺陷已清零，或已书面降级并获认可；三平台 release 产物齐备且可复现构建；发布说明、验证与发布检查清单已完成并对照通过。
- Apply shared-asset management constraints before mutating local runtime state.
