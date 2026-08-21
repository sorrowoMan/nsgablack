# NSGABlack

`nsgablack` 是统一框架栈中的优化与搜索语义层。它面向的不是“调用一个算法”，而是把候选表示、目标与约束、搜索策略、运行能力和结果证据装配成可组合、可恢复、可审计的求解系统。

当前版本：`0.3.11`，依赖 `blackbase>=0.3.9,<0.4.0`。

## 三仓边界

- `blackbase`：Project / Stage / Case / Scaffold、L0 资源授权、Context / Snapshot / Artifact 引用、跨 Case 调用与公共协议。
- `nsgablack`：Solver 生命周期、CandidateBatch、Representation、Adapter、Bias、Plugin、目标/约束、Pareto 与求解结果。
- `mlblack`：DataView、Spec、Codec、Head、LearningProblem、Evaluation Provider、模型 Artifact 与 ML 报告。

编排和资源授权只属于共享底座。优化 Adapter 不申请 GPU，也不硬编码 Torch、CUDA 或模型训练逻辑；Problem / Evaluation Provider 根据 L0 发放的 `ResourceContext` 执行求值。

## 核心闭环

```text
Representation 产生语义候选与数值视图
    -> Adapter.propose()
    -> Problem / Evaluation Provider 求值
    -> OptimizationFeedbackBatch
    -> Adapter.update()
    -> Solver 提交 incumbent、frontier、snapshot 和审计
```

四个主要扩展面：

- `Solver`：唯一控制平面，管理生命周期、评估入口、状态和插件钩子。
- `Adapter`：搜索策略，只负责 `propose/update`。
- `RepresentationPipeline`：候选的 init / mutate / repair / encode / decode。
- `Plugin`：checkpoint、trace、报告、评估短路和运行治理等能力。

`CandidateBatch` 同时保存 `semantic_states`、`numeric_matrix` 与 candidate token/provenance。数值算法消费矩阵；Representation、Problem、结果绑定和恢复消费语义状态。框架不再通过“数值相等”反推候选身份。

复合 Adapter 不再把多个子群体强行拼成一个虚假的 population。透明包装器委托当前子 Adapter；多策略、角色路由和事件组合器通过稳定 partition ID 发布 `PopulationPartition`。checkpoint 保存 partition、反馈和 token，Solver 只在外层确实完成融合选择时接受单一权威 population。

恢复生命周期固定为 `prepare -> setup -> Plugin.prepare_restore -> apply restore envelope -> ordinary init hooks -> initialize if fresh -> run`。外部预加载、插件自动恢复和 `set_state()` 都进入同一恢复通道，普通初始化钩子只能观察恢复后的状态。每次执行尝试返回 `StepOutcome`，只有 `committed` 才增加逻辑 step 并触发完成类钩子；累计耗时和逻辑 deadline 由可恢复的 `RunProgressState` 统一记录。

Population Snapshot 使用 `nsgablack.population_snapshot/v2`。`single/step_batch` 可以暴露一个 `(X, F, V)`；`partitioned` 只保存稳定分区和独立的 `last_evaluated_batch` 事件证据，旧单 population 读取入口会 fail-closed，不能把最后一次评估批次冒充复合 Adapter 的权威 population。

## 标准项目

```text
project/
  project_config.py
  run_project.py
  README.md
  cases/
    case_a/
      .case
      README.md
      build_solver.py
      run_solver.py
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/
      solver/
```

- Project 负责跨 Case 的串行、并行、嵌套和资源授权。
- Case 是独立运行和被父 Case 调用的统一组合单元。
- `build_solver.py` 是唯一规范装配入口。
- `build_trainer.py` 如存在，只能是 `build_solver` 的薄别名。
- 每个 Project 和 Case 只维护一个 `README.md`，不再复制 `START_HERE`、注册指南或契约模板。

## 快速开始

```powershell
python -m pip install -e .[dev]
python -m nsgablack project new demo_project
Set-Location demo_project
python -m nsgablack project add-case demo_case --type solver
python -m nsgablack project doctor --path . --build --strict
python run_project.py
```

查看组件：

```powershell
python -m nsgablack catalog search nsga2 --profile framework-core
python -m nsgablack catalog list --kind adapter --profile framework-core
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

`default` Catalog 包含示例和文档；架构审计必须显式使用 `framework-core`。

## 状态与大对象

- ContextStore 只保存轻量状态、版本和引用。
- population、objectives、history、trace 和大型 incumbent 进入 SnapshotStore。
- 可跨 Case、跨进程或长期保存的模型与数据先由 Artifact provider 发布，再传递 `DataRef`。
- `UnknownState` 是可传输语义状态；`StateRef` 是 Provider 持有的进程内活状态，不能伪装成持久 Artifact。

## 文档

- [文档入口](docs/README.md)
- [标准脚手架教程](docs/standard_scaffold_tutorial/README.md)
- [架构边界](docs/architecture/README.md)
- [用户指南](docs/user_guide/README.md)
- [组件导读](docs/guides/README.md)
- [示例项目](examples/cases/README.md)
- [当前白皮书草稿](docs/whitepaper/README.md)

历史设计和已删除接口以 Git 历史为准，不作为现行使用说明。
