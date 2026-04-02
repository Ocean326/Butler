# Skills Temp

这个目录是 `butler_main/sources/skills/` 自身的过程态工作区。

用途：

1. skill 池盘点、校验、导入、promotion、探索时产生的过程报告
2. skill 资产治理阶段的中间文件
3. 还不应该升格到 `工作区/Butler/...` 的内部工作材料

约束：

1. 这里是 skill 真源邻接工作区，不是最终展示层
2. 对外运行结果仍应进入 `工作区/Butler/runtime/skills/...`
3. 若某份材料需要对用户展示、治理归档或长期引用，再显式升格到 `工作区/Butler/...`
4. 新的 skill 治理脚本默认应优先落到这里，而不是在 `工作区/` 根层开目录
