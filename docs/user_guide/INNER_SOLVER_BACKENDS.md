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
- `ResourceContext`：Project L0 或 parent case 派生的有效资源授权。
- `component_overrides`：外层候选解码出的内层组件参数。
- result payload / Artifact ref / Snapshot ref：层间唯一稳定通信形态。

## 3. 推荐接线
1. 外层 Project 在 `project_config.py` 声明资源池和 case requirements。
2. 外层 Case 在 `Problem.evaluate()` 中构造 inner task payload。
3. 外层调用内层 `build_solver(..., resource_context=child_context, component_overrides=...)`。
4. 内层运行后返回稳定 result payload，并把大对象写成 Artifact/Snapshot ref。
5. 外层只做 objective/constraint projection。

## 4. 兼容对象

历史上的 `problem.inner_runtime_evaluator`、`build_inner_solver(...)`、inner backend helper 可以作为过渡层保留，但推荐把它们收敛到标准 inner Case surface。新机制不要继续扩展旧私有入口。

## 5. 示例

正式入口优先看：

- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`
- `examples/cases/supply_adjustment_nested/`
- `examples/cases/mlblack_nested_scaffold/`

不要把旧单文件脚本作为新增机制的入口。若需要保留旧脚本，只保留 thin wrapper 或 compatibility note。
