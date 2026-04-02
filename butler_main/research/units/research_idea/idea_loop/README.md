# idea_loop

科研方法改进任务的最小 harness 实现目录。

## 默认入口

- 文件树设计：`butler_main/research/units/research_idea/docs/20260320_idea_loop_文件树与层级设计.md`
- 总体方案：`butler_main/research/units/research_idea/docs/20260320_idea_loop_设计方案.md`

## 目录分层

- `specs/`：稳定协议与 schema
- `prompts/`：planner / verifier 等角色提示词
- `scripts/`：执行入口与辅助脚本
- `adapters/`：面向具体仓库/任务的适配层
- `templates/`：run 模板、报告模板
- `examples/`：最小示例与参考 run
- `tests/`：对 harness 自身的测试
- `runtime/`：运行时状态、队列、锁、检查点
- `runs/`：按阶段沉淀的实验产物
