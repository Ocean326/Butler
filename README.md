# Butler

Butler 当前主工程收口在 `butler_main/`，正式文档统一收口在 `docs/`。

## 根目录约定

根目录只保留以下几类内容：

1. 主工程目录：`butler_main/`
2. 正式文档目录：`docs/`
3. 历史归档目录：`过时/`
4. 仓库级入口文件：`README.md`、`.gitignore`、`pytest.ini`
5. 本地开发目录：`.venv/`、`.vscode/`、`.cursor/`、`工作区/`、各类隐藏缓存目录

以下内容不应再直接落在根目录：

- 按日期命名的阶段性文档
- 临时测试输出、缓存目录、一次性排障文件
- 已退出主链路的历史说明或 checklist

## 文档规范

1. 长期有效的架构、约定、排障说明放 `docs/concepts/`
2. 阶段性变更、现状、计划、排查记录统一放 `docs/daily-upgrade/<MMDD>/`
3. 以后新增日更文档时，先建日期目录，再落文件，不再直接写到 `docs/` 根目录
4. Skills相关，请放入`butler_main\butler_bot_agent\skills`

## 当前运行约定

1. Butler 当前后台结构以 `talk 主进程 + heartbeat sidecar + self_mind` 为准。
2. 运行控制优先通过 `butler_main/butler_bot_code/manager.ps1` 完成。
3. `guardian` 已退出现役链路，只保留在 `过时/` 作为历史归档。

## 维护边界

1. 当前真实代码入口在 `butler_main/butler_bot_code/`
2. 当前真实文档入口在 `docs/README.md`
3. 根目录若产生新的缓存、临时目录或误放文档，应优先迁移到对应子目录或加入忽略规则
