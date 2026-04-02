# research_manager agents_os adapters

这里放 `research_manager` 自己的 adapter。

建议后续承接：

- `task_store.py`
- `runtime_policy.py`
- `task_source.py`
- `scheduler.py`
- `truth.py`

原则：

- adapter 跟 manager 走
- 不进 `agents_os/`
- 不直接复用 Butler 旧后台自动化私有语义
