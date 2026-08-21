# Inner Case Runtime（标准 Case 契约版）

本页说明当前内层求解/训练/仿真接入模式：内层必须是标准 Case surface。外层可以在 `Problem.evaluate()`、stage runner 或 project runner 中调用内层，但不应直接读取内层 solver/trainer 私有对象。

## 1. 目标
- 外层 Case 仍按自己的语义工作。
- 内层 Case 作为评估、训练、仿真或数值求解 backend 执行。
- Project L0 发放 `ResourceContext`；外层可以派生 child grant，内层不能扩大资源范围。
- 运行治理与追溯由插件、runtime audit 和 run surface contract 完成。

## 2. 关键对象
- `cases/<inner>/build_solver.py`：内层 canonical assembly entry。
- `build_trainer.py`：如存在，只能是 alias。
- `ResourceContext`：Project L0 发放、由公共 child grant ledger 分账的有效资源授权。
- `component_overrides`：外层候选解码出的内层组件参数。
- result payload / Artifact ref / Snapshot ref：层间唯一稳定通信形态。

## 3. 推荐接线
1. 外层 Project 在 `project_config.py` 声明资源池和 case requirements。
2. 外层 Case 在 `Problem.evaluate()` 中构造 `CaseRunRequest`，或使用 `CaseInnerRuntimeEvaluator` 的等价公共入口。
3. BlackBase `CaseInvoker` 统一派生 lineage、deadline、cancellation、budget 与 child resource grant，再调用内层 canonical builder。
4. 内层运行后返回稳定 result payload，并把大对象写成 Artifact/Snapshot ref。
5. 外层只做 objective/constraint projection。

## 4. 禁止的旧入口

不得通过修改 `sys.path`、直接导入另一仓库内部 workflow、私自派生资源上下文或调用私有 `build_inner_solver(...)` 完成嵌套。这些路径不具备完整 lineage、预算结算、取消传播与标准结果信封。

## 5. 示例

正式入口优先看：

- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`
- `examples/cases/supply_adjustment_nested/`

不要把旧单文件脚本作为新增机制的入口。若需要保留旧脚本，只保留 thin wrapper 或 compatibility note。
