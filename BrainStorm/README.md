# BrainStorm 头脑风暴系统

现在把 `BrainStorm` 看成一套更清楚的 **前台四区 + 后台一层**：

| 区域 | 作用 | 主要维护者 |
|---|---|---|
| `Ideas/` | 你的新想法、疑问、猜想、方向感，先丢进来再说 | 你为主 |
| `Raw/` | 碎资料、链接摘录、抓取结果、OCR、图片资产 | agent 为主 |
| `Insights/standalone_archive/` | 单主题 insight，已经有一轮提炼 | agent 为主 |
| `Insights/mainline/` | 长主线知识线，沉淀成树干级文档 | agent 为主 |
| `Working/` | 后台加工层，供 agent 从 Raw/Ideas 过渡到 Insight | agent 内部使用 |

默认阅读入口仍然是 `Insights/README.md`，但默认写入新脑暴点的入口改成 `Ideas/README.md`。
根目录本身现在只保留入口与状态，说明文档不再散落在这里。

---

## 先用哪一块

| 你的场景 | 第一落点 |
|---|---|
| 我突然有个想法，还没证据 | `Ideas/inbox/` |
| 这个想法值得追踪一阵 | `Ideas/threads/` |
| 我手上有链接、截图、原文、OCR | `Raw/` |
| 我想把一批资料提炼成结论 | `Insights/standalone_archive/` |
| 我想看已经成体系的长期知识 | `Insights/mainline/` 或 `Insights/README.md` |

---

## 三句暗号

| 你说 | 效果 |
|---|---|
| `帮我记个想法` | 落到 `Ideas/inbox/`，先保留原始脑暴 |
| `把这些资料收进去` | 进入 `Raw/`，作为后续提炼材料 |
| `提炼成 insight / 并回主线` | 进入 `Insights/standalone_archive/` 或 `Insights/mainline/` |

---

## 推荐入口

- 想开始扔新点子：`Ideas/README.md`
- 想看总使用说明：`Guides/阅读指南.md`
- 想看成熟知识树：`Insights/README.md`
- 想看目录和命名规则：`Guides/命名与目录约定.md`
- 想看当前状态与行动项：`STATE.md`
- 想看长期记忆：`MEMORY.md`

---

## 目录结构

```text
BrainStorm/
├── README.md
├── MEMORY.md
├── STATE.md
├── Guides/                     ← 使用说明与放置规则
├── Ideas/                      ← 你的脑暴入口
│   ├── inbox/                  ← 随手扔想法
│   ├── threads/                ← 值得持续跟踪的想法线
│   └── templates/              ← 脑暴模板
├── Playbooks/                  ← 具体流程与任务手册
├── Raw/                        ← 碎资料与抓取资产（含 `daily/YYYYMMDD/`）
├── Templates/                  ← 可复用结构模板
├── Working/                    ← agent 后台加工层
├── Insights/
│   ├── README.md               ← 默认知识入口（自动生成）
│   ├── mainline/               ← 长主线知识线
│   └── standalone_archive/     ← 已提炼的单主题 insight
└── Archive/                    ← 月度归档
```

---

## 信息流

存在两条常见入口：

1. `Ideas/` 起步：你的新点子 -> agent 补资料到 `Raw/` -> 中间加工到 `Working/` -> 形成 `Insight` -> 成熟后并入 `mainline/`
2. `Raw/` 起步：外部资料/抓取/OCR -> agent 提炼 -> `Insight` -> `mainline/`

`Working/` 不是你默认要找的地方，它更像 agent 的厨房，不是餐桌。

---

## 刷新知识树

- 命令：`python BrainStorm/tools/refresh_brainstorm.py`
- 会更新：
  - `Insights/README.md`
  - `Insights/index.md`
  - `Insights/knowledge_tree.json`

使用时机：

- 新增或修改 `Insights/` 文档后
- 有 insight 并回主线后
- 调整知识树分支关键词后

---

## 详细流程文档

首页不再承载长流程细节，避免入口继续变乱。具体流程去这里看：

- `Playbooks/Web_内容抓取到头脑风暴_MVP流程.md`
- `Playbooks/Web_内容到头脑风暴_合并模板.md`
- `Playbooks/AI技术博客地图_每日巡检任务书.md`

---

## 维护分工

- 你主要负责：往 `Ideas/` 里持续抛点子，决定什么值得继续想。
- agent 主要负责：维护 `Raw/`、`Working/`、`Insights/`，并把零散内容往更稳定层推进。
- 当一个主题长期反复出现时，优先不是再开平行文件，而是并回现有 `mainline/`。
