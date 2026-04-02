# Butler

Butler 当前主工程收口在 `butler_main/`，正式文档统一收口在 `docs/`。  
从 `2026-03-26` 起，agent 改动前的当前导航入口统一收口在 `docs/project-map/`。  
本轮先建立一版目录整理方案与治理规则，作为后续实际搬迁、归档和清理的执行基线。

`2026-03-31` 已完成第一轮根目录收口实施：

- `runtime_os/` 保持为根目录现役兼容命名空间，不下沉、不归档
- `tools/` 保持为根目录现役 CLI / 运维 / 审计入口，并补工具说明
- 根目录历史快照 `1/`、`C:/` 已迁入 `过时/20260331_root_snapshots/`
- 根目录临时单文件 `dir_names_utf8.txt` 已迁入 `过时/20260331_root_misc/`
- `MyWorkSpace/` 当前标记为待收敛旧并行工作台，不再作为新增落位目标

## 当前结论

目前目录状态已经形成四个明显层次：

1. **根目录**：同时混有主工程、正式文档、本地环境、临时排障文件和历史残留目录。
2. **`工作区/`**：已经有一版较成熟的编号目录体系，但仍与大量未编号历史目录并存。
3. **`过时/`**：已经承担归档职责，但归档粒度、命名和说明文件还不统一。
4. **兼容入口层**：`runtime_os/` 与 `tools/` 虽然位于根目录，但承担现役兼容与启动职责，不能按“视觉整理”直接挪走。

因此后续治理目标不是“全部删掉重来”，而是：

- 根目录只保留入口、正式主链路和仓库级设施
- `工作区/` 承担所有活跃中的中间产出与专题工作
- `过时/` 只承接退出主链路的历史资产，且可追溯

## V1 整理目标

### 1. 根目录目标

根目录只保留以下几类内容：

1. 主工程目录：`butler_main/`
2. 正式文档目录：`docs/`
3. 活跃工作目录：`工作区/`
4. 历史归档目录：`过时/`
5. 根级兼容命名空间：`runtime_os/`
6. 工具目录：`tools/`
7. 仓库级入口文件：`README.md`、`.gitignore`、`pytest.ini`
8. 本地开发设施：`.git/`、`.venv/`、`.vscode/`、`.cursor/`、隐藏缓存目录

当前实施裁决：

- `runtime_os/` 是 repo-root compatibility surface，对应真实实现位于 `butler_main/runtime_os/`
- `tools/` 是现役脚本入口；具体分类见 `tools/README.md`
- `MyWorkSpace/` 不再视为现役主工作台，后续新增内容统一落 `工作区/`

以下内容不应继续长期停留在根目录：

- `_tmp*`、`__shell_output_test.txt`、临时脚本、一次性排障输出
- 主题性文档、阶段报告、实验记录
- 业务试验目录、历史副本目录、压缩包
- 已退出主链路的旧目录

### 2. `工作区/` 目标

`工作区/` 是 Butler 的**活跃工作台**，不是根目录的“第二个杂物箱”。  
但从 2026-03-19 起，`工作区/` 的治理思路已进入 V2 过渡阶段：  
后续目标是逐步迁移为 `WorkSpace/`，并从“编号能力目录”转向“任务 / 项目导向目录”。

当前目标一级结构为：

- `WorkSpace/Butler/`
- `WorkSpace/Research/`
- `WorkSpace/TargetProjects/`
- `WorkSpace/MyProjects/`
- `WorkSpace/Shared/`
- `WorkSpace/Inbox/`
- `WorkSpace/Archives/`

详细规则以 `工作区/README.md` 为准；旧的 `00~09` 结构继续视为过渡期兼容层，而不是长期终态。

### 3. `过时/` 目标

`过时/` 是**退出主链路后的仓库级归档区**，不是继续开发目录。  
它只保存以下内容：

- 已被替代的历史架构
- 已完成且不再扩写的老专题
- 根目录或 `工作区/` 清退下来的旧资料
- 出于审计、回溯、对照而保留的目录快照

## 根目录治理规则

### 保留规则

根目录新增内容必须满足以下任一条件，否则一律不应直接落根：

1. 是仓库级入口文件
2. 是主工程或正式文档主目录
3. 是本地开发环境或 IDE 目录
4. 是明确的公共工具目录

### 落位规则

新增内容按下面规则落位：

- 代码改动：进入 `butler_main/`
- 正式说明文档：进入 `docs/`
- 活跃研究/任务/实验产物：进入 `工作区/`
- 已退出主链路的历史材料：进入 `过时/`
- 短期临时文件：进入 `工作区/09_temp/`

### 清理规则

根目录出现以下内容时，优先执行迁移而不是继续堆放：

- `*_log.*`、`*_debug.*`、`*_output.*`
- 单次执行产生的 `.json`、`.jsonl`、`.txt`、`.md`
- `_tmp*` 前缀目录或脚本
- 专题试验目录，如歌词抓取、网页抓取、临时 brainstorm 目录

### 当前建议迁移对象

基于当前现状，后续整理时优先关注以下对象：

- 根目录 `_tmp*`、`tmp_read_doc.py`、`_tmp_read_doc.py`、`__shell_output_test.txt`
- 根目录歌词抓取相关 `netease_lyric_*`
- 根目录 `BrainStorm/` 与 `BrainStorm.zip`
- 根目录 `butle_bot_space/`
- 根目录 `Microsoft/` 与异常命名目录 `������`

建议原则：

- 仍在使用的迁到 `工作区/` 对应编号目录
- 已停止维护的迁到 `过时/`
- 无保留价值的进入临时区后再删

### 本轮已完成迁移对象

- 根目录 `1/` -> `过时/20260331_root_snapshots/1_run_snapshot/`
- 根目录 `C:/` -> `过时/20260331_root_snapshots/C_drive_workspace_snapshot/`
- 根目录 `dir_names_utf8.txt` -> `过时/20260331_root_misc/dir_names_utf8.txt`

## `工作区/` 治理规则

### 一级目录规则

`工作区/` 当前处于过渡期。  
在真正改名为 `WorkSpace/` 前，正式入口建议收敛为两类：

1. 未来任务 / 项目导向结构的兼容目录
2. 少量跨目录索引文件

`工作区/` 根目录长期允许保留的文件，建议收敛为：

- `README.md`
- `index.md`
- `task_ledger.md`
- 少量跨模块总索引或审批入口文件

除上述少量入口文件外，新的主题文档不再直接写入 `工作区/` 根目录。

### 新增目录规则

新增目录必须优先服从“主任务 / 主项目”逻辑，不再继续强化旧编号目录。  
今后优先判断：

- 这是 `Butler/` 内容
- 这是 `Research/` 内容
- 这是 `TargetProjects/<project>/` 内容
- 这是 `MyProjects/<project>/` 内容

同一主任务下，再细分：

- `runtime/`
- `governance/`
- `handoffs/`
- `deliveries/`
- `user/`
- `meetings/`
- `plans/`

禁止继续新增这类未编号同义目录：

- `background_notes/`、`background_recent/`
- `governance/`、`workspace_governance/`、`manager/`
- `temp/`、`tools/`、`architecture/` 这类语义宽泛目录

### 历史遗留目录规则

`工作区/` 下未编号旧目录统一视为**历史遗留目录**：

- 可以迁移
- 可以归档
- 可以删除
- 不再继续扩写

后续搬迁时，优先采用以下收口方向：

- Butler 本体相关：`self_mind/`、`governance/`、`06_governance_ops/`、`manager/`、`proactive_talk/` 等历史目录 → 未来 `WorkSpace/Butler/`
- Research 相关：`BrainStorm/`、`Simon_agent_xhs_*`、`网页抓取验证/`、`网易云歌词/`、`netease_lyric/`、`netease_lyric_fetch/`、`architecture/`、`skill-explore/`、`学习项目/` → 未来 `WorkSpace/Research/`
- 临时缓冲：`temp/`、`09_temp/` → 未来 `WorkSpace/Inbox/`
- 工作区归档：`08_archives/` → 未来 `WorkSpace/Archives/`
- 旧 memory / cognition 相关内容按实际用途拆分进入 `WorkSpace/Butler/governance/`、`WorkSpace/Butler/runtime/` 或具体项目目录，而不再单独扩成一级桶

### 文件命名规则

`工作区/` 文件命名建议统一为：

- `YYYYMMDD_主题.md`
- `主题_YYYYMMDD.md`
- `主题_status_YYYYMMDD.json`

避免再出现含义不清的文件名，例如：

- `test.txt`
- `new.md`
- `临时结果.md`

### 生命周期规则

`工作区/` 中的材料按四种状态治理：

1. **active**：持续编辑，留在编号目录
2. **stable**：已基本稳定，保留在编号目录并补 README/索引
3. **archive-ready**：不再扩写，迁到 `工作区/08_archives/`
4. **obsolete**：退出主链路，迁到仓库根 `过时/`

## `过时/` 治理规则

### 归档准入规则

满足以下任一条件时，可进入 `过时/`：

1. 已被新主链路替代
2. 保留仅为追溯，不再继续开发
3. 目录结构过旧，不适合继续留在活跃区
4. 根目录清理时需要保留历史快照

### 命名规则

后续新归档建议统一使用：

- `YYYYMMDD_主题_原因/`
- `YYYYMMDD_主题_snapshot/`
- `YYYYMMDD_root_misc/`

例如：

- `20260319_guardian_retired/`
- `20260319_runtime_protocol_snapshot/`

现有命名如 `guardian_root_legacy_20260315_2204/` 可暂时保留，但后续新增尽量统一新格式。

### 说明文件规则

每个新归档目录建议至少包含一个简短说明文件，例如 `README.md`，写清：

- 来源目录
- 归档日期
- 归档原因
- 是否仍允许只读引用
- 替代入口在哪里

### 使用边界

`过时/` 下内容默认只读，不作为活跃开发路径，不作为新文档默认引用入口。

## 建议执行顺序

本轮建议按“三步法”推进，而不是一次性大搬家：

1. **先立规**：以本 README 和 `工作区/README.md` 作为治理基线
2. **再收口**：先收根目录，再收 `工作区/` 未编号旧目录
3. **后归档**：最后统一补 `过时/` 命名和归档说明文件

建议操作批次如下：

### 批次 A：根目录减负

- 清出所有 `_tmp*`、单次执行输出、零散实验文件
- 把仍活跃的专题迁入 `工作区/`
- 把明确停用的目录迁入 `过时/`

### 批次 B：`工作区/` 归一

- 冻结未编号旧目录
- 将活跃内容并入正式编号目录
- 把 `工作区/` 根目录零散文件下沉到对应专题目录

### 批次 C：`过时/` 规范化

- 新归档目录统一命名
- 逐步给重要归档补 `README.md`
- 让 `过时/` 只承担“退出主链路后的只读资产”职责

## 文档规范

1. 长期有效的架构、约定、排障说明放 `docs/concepts/`
2. 阶段性变更、现状、计划、排查记录统一放 `docs/daily-upgrade/<MMDD>/`
3. 自 `0322` 起，日更目录默认维护 `1+N` 文档：`00_当日总纲.md` + `01_...md` / `02_...md`
4. 同一二级主题的计划、落实、再计划持续更新在同一份 `01_...md` / `02_...md` 文档里，文档前几行先写主线，后面再追加细节
5. 新增日更文档时，先建日期目录，再落文件，不再直接写到 `docs/` 根目录
6. Skills 相关放 `butler_main/sources/skills/`

## 当前运行约定

1. Butler 当前后台结构以 `chat core 主进程 + orchestrator + recent memory` 为准
2. 系统级前台 CLI 入口固定为 `butler-flow`；可通过 `./tools/install-butler-flow` 安装到 `~/.local/bin/butler-flow`
3. Linux / macOS 下后台运行控制继续通过 `python -m butler_main.butler_bot_code.manager ...` 或 `./tools/butler ...` 完成
4. Windows 的旧 `manager.ps1` 已退役，文档里若仍提到它，应视为待更新历史信息
5. `guardian` 已退出现役链路，只保留在 `过时/` 作为历史归档

## 维护边界

1. 当前真实代码入口在 `butler_main/butler_bot_code/`
2. 当前真实文档入口在 `docs/README.md`
3. 根目录若产生新的缓存、临时目录或误放文档，应优先迁移到对应子目录或加入忽略规则

