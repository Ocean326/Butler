# Butler Console Webapp

当前 `webapp/` 目录分成两条并存链路：

1. `legacy` 运行链
   - 根目录的 `index.html`、`styles.css`、`app.js`
   - 继续作为 Python console server 的零构建回退页面
2. `SPA` 迭代链
   - `spa/`
   - 使用 `React + TypeScript + Vite + TanStack Query + Zustand + React Flow`
   - 构建产物输出到 `dist/`

## 当前托管规则

- `butler_main.console.server` 会优先托管 `webapp/dist/`
- 若 `dist/` 不存在，则自动回退到当前根目录的 legacy 静态页
- `/console/api/*` 合同不因前端形态变化而改变

## 目录结构

- `index.html`
- `styles.css`
- `app.js`
  - legacy fallback 页面
- `spa/`
  - 新的可维护 SPA 源码
- `dist/`
  - Vite 构建产物，供 Python server 直接托管
- `ATTRIBUTION.md`
  - 外部设计/实现参考来源约束

## 常用命令

在 `butler_main/products/campaign_orchestrator/console/webapp/` 下执行：

```bash
npm install
npm run dev
npm run build
npm run test
npm run typecheck
```

`butler_main/console/` 仅保留 compat shell；前端源码和 package workspace 当前都以这里为准。

## 维护约束

- 不把 graph / board UI 反向做成 runtime 真源
- 不改 `/console/api/*` 的语义，只做前端消费层升级
- legacy fallback 仅作为回退面，不再承接新功能
- 新增前端能力优先进入 `spa/`，不要再往根目录追加新的大块逻辑

Direct code reuse must follow [ATTRIBUTION.md](./ATTRIBUTION.md). `EpicStaff` is not an allowed code source for this console.
