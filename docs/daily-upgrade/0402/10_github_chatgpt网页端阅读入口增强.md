# 0402 GitHub / ChatGPT 网页端阅读入口增强

日期：2026-04-02  
状态：已实施

关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [Project Map 入口](../../project-map/README.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)

## 1. 本轮目标

解决 GitHub 网页端与 ChatGPT 网页端阅读仓库时的入口误判问题：

1. 根 `README.md` 不再只面对本地 agent / 仓库治理视角
2. 明确把网页端读者导向 `docs/` 与 `docs/project-map/`
3. 降低“按目录名猜系统结构”导致的误解

## 2. 当前裁决

1. 根 `README.md` 现在同时承担 **网页端阅读壳** 的职责。
2. GitHub / ChatGPT 网页端读者的默认入口固定为：
   - `docs/README.md`
   - `docs/project-map/README.md`
   - `docs/project-map/00_current_baseline.md`
   - `docs/project-map/01_layer_map.md`
   - 当天 `00_当日总纲.md`
3. 根 `README.md` 必须显式声明：
   - 当前目录结构更偏向 agent 开发与迁移期治理
   - 正式系统说明统一以 `docs/` 为准
   - 不要直接按目录名猜系统分层
4. 根 `README.md` 必须直接给出当前系统理解口径：
   - `3 -> 2 -> 1`
5. 根 `README.md` 必须补一个简短目录职责速览，至少覆盖：
   - `butler_main/`
   - `docs/`
   - `runtime_os/`
   - `tools/`
   - `工作区/`
   - `过时/`

## 3. 回写范围

- `README.md`
  - 新增 GitHub / ChatGPT 网页端阅读入口区块
- `docs/README.md`
  - 增加本专题入口
- `docs/project-map/02_feature_map.md`
  - 在 `docs only` 条目中补本专题
- `docs/project-map/03_truth_matrix.md`
  - 增加“GitHub / ChatGPT 网页阅读入口”真源条目
- `docs/project-map/04_change_packets.md`
  - 在 `docs-only` 检查项中补 README 网页端入口校验
- `docs/daily-upgrade/0402/00_当日总纲.md`
  - 记录本轮 docs-only 回写

## 4. 当前口径

- `AGENTS.md` 仍然服务于本地 agent 协议与收尾动作
- GitHub / ChatGPT 网页端优先看根 `README.md`
- 根 `README.md` 只做**导航壳**，不替代 `docs/` 真源
- 长文说明、术语裁决、分层映射、改前读包仍以 `docs/project-map/` 为准
