# COPT / 数值求解器融合边界

这页说明如何把 COPT、LP/MIP/QP 求解器或其他数值求解器接入当前统一框架栈。核心原则是：

> 数值求解器是 domain backend。它可以作为 inner Case、L4 evaluation provider 或 Plugin 能力接入；不要把完整数值求解流程私下塞进 Adapter。

## 1. 推荐落点

| 形态 | 适合场景 | 边界 |
| --- | --- | --- |
| inner standard Case | 一个候选需要触发完整 LP/MIP/QP/仿真求解 | 通过 `build_solver(resource_context=...)` 调用，返回结构化 result |
| L4 evaluation provider | 数值求解器只是评估链的一部分 | 负责短路/增强 `evaluate_*`，保证 objectives/violations shape 合法 |
| Plugin | 回调、日志、IIS、解池、checkpoint、backend audit | 不改写搜索策略语义 |
| Adapter | 搜索策略本身，如 trust-region / local search | 只做 `propose/update`，不拥有外部 backend 生命周期 |

## 2. 与 Project / Case / L0 的关系

- Project L0 声明可用资源和服务后端。
- Case 声明数值求解器需求，例如线程数、license token、服务 endpoint、worker queue。
- Project L0 发放 `ResourceContext`。
- COPT/数值求解器适配层只能消费 grant，不能私下抢全局资源或写死机器本地设备。

```text
Project L0
  -> outer Case ResourceContext
  -> outer Problem.evaluate()
  -> child ResourceContext
  -> inner numeric Case / provider / plugin
  -> structured result + audit
```

## 3. 多策略与多层嵌套

多策略编排分两类：

- **Adapter 内部多策略**：同一个 Case 内多个 search policy 的 propose/update 组合。
- **多 Case 编排**：多个 solver/trainer/numeric Case 的串行、并行、嵌套，属于 Project / Case / L0 substrate。

如果是“启发式外层 + COPT 内层”，推荐表达为：

```text
project_root/
  project_config.py
  run_project.py
  cases/
    outer_search/
      build_solver.py
      problem/
      pipeline/
      adapter/
      runtime/
    inner_copt/
      build_solver.py
      problem/
      pipeline/
      plugins/
      runtime/
```

外层只看 inner result，不解析 inner solver 私有对象。

## 4. 框架级抽象

下面能力应抽象为通用 provider/plugin surface，而非 COPT 私有捷径：

- callback / event hook
- warm start / MIP start
- solution pool
- IIS / infeasibility diagnosis
- parameter tuning
- license / service / worker audit

## 5. 推荐阅读

- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`
- `docs/architecture/SOLVER_ORCHESTRATION.md`
- `docs/architecture/L0_RESOURCE_ORCHESTRATION.md`
- `docs/user_guide/NUMERICAL_SOLVER_PLUGINS.md`
