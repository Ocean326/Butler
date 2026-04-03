---
name: skill-github-import
description: 从 GitHub 公共仓库按目录导入 skill 到 Butler 的 `sources/skills/pool/`，用于把外部 skill 样例或可复用 skill 真正落到本地 skill 池，而不是只停留在搜索结果。
category: operations
family_id: skill-intake
family_label: Skill 引入族
family_summary: 面向外部 skill 的引入、审阅与本地落库；命中后再区分直接导入还是先做 intake review。
family_trigger_examples: 导入 skill, 上游审阅, 拉到本地
variant_rank: 10
trigger_examples: 从 GitHub 导入 skill, 下一个 skill, 把这个 skill 拉到本地, import skill from github
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
---

# Skill GitHub Import

当 Butler 已经确认某个 GitHub 仓库目录里存在可复用 skill，需要把它正式导入到本地 skill 池时，使用本 skill。

## 本 skill 的边界

- 只负责从 **GitHub 公共仓库** 下载指定目录到本地。
- 默认导入到 `./butler_main/platform/skills/pool/imported/`。
- 不自动把导入结果加入默认 collection；是否暴露给 chat/codex/orchestrator，需要另行审阅并登记到 `collections/registry.json`。
- 不替代安全审阅。导入后仍需人工检查 `SKILL.md`、脚本、副作用与许可证。

## 入口脚本

- `./butler_main/platform/skills/pool/ops/skill-github-import/scripts/import_github_skill.py`

## 标准用法

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/ops/skill-github-import/scripts/import_github_skill.py' `
  --repo 'Narwhal-Lab/MagicSkills' `
  --path 'skill_template/c_2_ast' `
  --ref 'main'
```

## 执行步骤

1. 先确认目标目录确实是一个 skill 目录，至少应包含 `SKILL.md`。
2. 运行导入脚本，把目录下载到 `./butler_main/platform/skills/pool/imported/<skill-name>/`。
3. 检查导入目录中的：
   - `SKILL.md`
   - `scripts/`
   - `references/` / `assets/` / 其他依赖文件
4. 查看脚本自动生成的：
   - `UPSTREAM_IMPORT.json`
   - `IMPORT_REPORT.md`
5. 如果要给运行时暴露，再去更新 `./butler_main/platform/skills/collections/registry.json`。

## 参数

- `--repo`：`owner/repo`
- `--path`：仓库内 skill 目录路径
- `--ref`：分支/tag/commit，默认 `main`
- `--dest-root`：目标根目录，默认 `./butler_main/platform/skills/pool/imported`
- `--name`：可选，指定导入后的目录名
- `--replace`：若目标目录已存在则覆盖

## 输出

- 导入后的 skill 目录
- `UPSTREAM_IMPORT.json`
- `IMPORT_REPORT.md`

## 注意事项

- 如果目标目录里没有 `SKILL.md`，本 skill 应直接失败，不要假装导入成功。
- 导入只是“拿到本地真源候选”，不是“已经可对外暴露”。
- 对脚本型 skill，后续至少还要补一次验证或沙箱试跑。

