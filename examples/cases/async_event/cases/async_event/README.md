# async_event

**async_event** 是 **async_event** Project 中的标准 **solver** Case。

## 标准入口

- **build_solver.py**：唯一 canonical assembly entry。
- **run_solver.py**：Case 本地检查与运行入口。
- **build_trainer.py / run_trainer.py**：仅作为统一 Case 词汇的薄别名。
- **problem/**：目标、约束和领域评价语义。
- **pipeline/**：候选初始化、编码、修复、解码或数据处理链。
- **adapter/**：算法策略装配。
- **plugins/、evaluation/、runtime/**：能力、评估和运行审计扩展点。

## 检查

~~~powershell
cd examples/cases/async_event/cases/async_event
python run_solver.py --check
~~~

完整运行优先从 Project 入口发起，以便注入权威 **ResourceContext**、lineage、预算、取消控制和 Artifact authority：

~~~powershell
python examples/cases/async_event/run_project.py
~~~
