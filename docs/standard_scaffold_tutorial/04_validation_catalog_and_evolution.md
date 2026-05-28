# 04. 验证、Catalog 与长期演进

标准脚手架不是“能跑就行”。它必须能回答这些问题：

- 这次运行装了哪些组件？
- 参数来自哪个 Spec/Registry？
- 哪些组件读写了 context？
- 大对象写到了哪个 snapshot？
- 两次运行结构差异是什么？
- 新增机制应该归到哪一层？

## 1. 最小检查命令

在项目目录内：

```powershell
python run_solver.py --check
python -m nsgablack project doctor --path . --build --strict --format problem
```

框架主干 catalog：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog list --profile framework-core --kind plugin
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20
```

项目 catalog：

```powershell
python -m nsgablack project catalog list --path .
python -m nsgablack project catalog search pipeline --path .
python -m nsgablack project catalog search vns --path . --global
```

Run Inspector：

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

建议把检查拆成日常三档：

| 档位 | 什么时候跑 | 命令 |
| --- | --- | --- |
| quick | 每改一层组件后 | `python run_solver.py --check` |
| strict | 合并前或机制变更后 | `python -m nsgablack project doctor --path . --build --strict --format problem` |
| audit | 文档、catalog、case 准备发布前 | `run_inspector` + `project catalog` + `framework-core catalog` |

如果某次改动涉及评估链、snapshot、catalog 或 L0 资源，不能只跑 quick。

## 2. doctor 输出怎么读

`project doctor` 的核心不是格式检查，而是契约检查。常见类型：

| 类型 | 含义 | 处理优先级 |
| --- | --- | --- |
| import/build error | 装配入口无法导入或无法 build | 最高 |
| scaffold structure | 标准目录或文件缺失 | 高 |
| context contract | context key/读写声明不清晰 | 高 |
| snapshot policy | 大对象直接写 context | 高 |
| catalog registration | 组件可发现性不足 | 中 |
| example/case placement | 示例落点不符合规范 | 中 |
| warning | 暂不破坏运行，但影响可维护性 | 视情况 |

处理原则：

1. 先修 import/build error。
2. 再修 problem/pipeline/adapter/plugin 的层级边界。
3. 再修 context/snapshot。
4. 最后补 catalog 和文档。

不要因为优化结果正常就忽略 doctor。doctor 报的是长期维护风险。

## 3. 新增组件检查清单

新增 `Problem`：

- `dimension` 与 bounds 数量一致。
- `evaluate(x)` 返回 objective 维度稳定。
- `evaluate_constraints(x)` 返回 violation 维度稳定。
- 异常输入有明确 fallback 或异常。
- 目标和约束含义写在 config 或 docs 中。

新增 `RepresentationPipeline`：

- initializer 输出 shape 稳定。
- mutator 尊重 bounds/context。
- repair 只做可行性兜底，不做业务搜索。
- encode/decode 可序列化。
- typed genome 的字段可以写进 report。

新增 `Adapter`：

- `propose(solver, context)` 只产生候选。
- `update(...)` 只消费反馈。
- 提供 `get_state/set_state` 以支持 checkpoint。
- 不把 population/history 长期塞 context。
- 多策略组合时不依赖全局变量。

新增 `Plugin`：

- lifecycle hook 幂等。
- 写 context 使用 canonical key 或清晰前缀。
- 大对象写 snapshot。
- 短路评估返回 shape 合法。
- 外部资源失败支持 soft/strict 模式。

新增 `Bias`：

- 明确是软引导。
- 记录启用状态和风险。
- 不替代 objective/constraint。

新增 `L0 Resource` 或跨框架资源能力：

- `ResourceRequest`、`ResourceOffer`、`ResourceLease` 字段可序列化。
- GPU 资源落到具体 `device_tokens`，不是只写 `gpus: 1`。
- 多进程时使用共享 lease store，例如 `SQLiteLeaseStore`。
- 如果启用 TTL，heartbeat 由 runner/worker 管理，不进入业务 trainer。
- `ResourceContext` 写入 summary/runtime_state，便于审计。

## 4. 单点、批量、短路评估必须同时验证

涉及评估链改动时，至少验证三条路径：

```python
# 单点
obj = solver.evaluate_individual(x)

# 批量
objs = solver.evaluate_population(population)

# 插件短路
plugin.evaluate_population(solver, population, context)
```

验收标准：

| 路径 | 必须满足 |
| --- | --- |
| 单点 | objective/violation shape 稳定 |
| 批量 | 返回数量与 population 数量一致 |
| 短路 | 和普通评估同 shape、同方向、同失败语义 |

如果短路评估返回的是缓存结果，也要在 report 中说明缓存命中率和 miss fallback。

## 5. Context/Snapshot 审计规则

不要：

```python
context["population"] = population
context["objectives"] = objectives
context["history"] = huge_history
context["trace"] = huge_trace
```

应该：

```python
snapshot_key = solver.write_population_snapshot(population, objectives, violations)
context["population_ref"] = snapshot_key
```

读取优先级：

```text
snapshot -> adapter state -> solver lightweight mirror
```

写回优先级：

```text
adapter.set_population* -> solver.write_population_snapshot -> context *_ref
```

最小审计字段建议：

| 字段 | 说明 |
| --- | --- |
| `snapshot_key` | 大对象位置 |
| `kind` | population/objectives/trace/artifact |
| `generation` | 产生时刻 |
| `producer` | 哪个组件写入 |
| `schema_version` | 未来兼容 |

## 6. Catalog profile 口径

| profile | 用途 |
| --- | --- |
| `framework-core` | 主干盘点，排除 example/doc |
| `default` | 完整口径，包含 example/doc |

任何“这个组件是不是主干能力”的结论，都必须显式使用：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search <keyword> --profile framework-core --limit 20
```

教学、示例和模板查找才使用 `default`：

```powershell
python -m nsgablack catalog list --profile default --kind example
```

## 7. 项目本地 catalog entry 怎么写

项目侧可在 `catalog/entries.toml` 或 `project_registry.py` 注册本地组件。示例：

```toml
[[entries]]
key = "project.pipeline.offloading"
kind = "pipeline"
summary = "Offloading policy genome pipeline with bounded continuous variables."
status = "project"
owner = "project"

[entries.metadata]
mount_plane = "representation"
mount_point = "solver.set_representation_pipeline"
use_when = "候选解是卸载比例、安全等级等连续变量。"
contract_consumes = []
contract_provides = []
contract_mutates = []
```

最小要求：

- key 全局可读，不要叫 `test1`。
- kind 明确。
- summary 说明做什么。
- mount point 说明怎么挂载。
- contract 字段说明 context 读写。

## 8. Run Inspector 看什么

Run Inspector 的目标是解释 wiring：

| 面板/信息 | 看什么 |
| --- | --- |
| solver | solver 类型、生命周期入口 |
| adapter | 当前策略、是否多策略/串行/事件驱动 |
| representation | pipeline 是否挂载、context contract |
| plugins | 生命周期插件和评估短路插件 |
| context | 轻量状态 key |
| snapshot | 大对象引用 |
| diff | 两次装配差异 |

如果 Run Inspector 无法快速加载，通常说明 `build_solver()` 做了重计算。修法是把重计算移动到：

- `solver.run()` 阶段。
- `problem.evaluate()` 阶段。
- evaluation provider。
- plugin runtime hook。

建议在报告中至少记录这些 wiring 字段：

| 字段 | 来源 | 目的 |
| --- | --- | --- |
| `run_id` | CLI / build_solver | 区分运行 |
| `problem_key` | build config | 解释目标和约束 |
| `pipeline_key` | build config | 解释候选表示 |
| `adapter_profile` | adapter config | 解释搜索策略 |
| `bias_key` | bias config | 解释软先验 |
| `plugin_keys` | plugin config | 解释运行能力 |
| `resource_context` | L0 | 解释 CPU/GPU 授权 |
| `snapshot_refs` | SnapshotStore | 定位大对象 |

这些字段不是为了好看，而是为了之后能回答“为什么这次结果和上次不同”。

## 9. 标准 case 落点

正式 example、benchmark、cross-framework case 放：

```text
examples/cases/<case>/
```

推荐结构：

```text
examples/cases/<case>/
  README.md
  build_solver.py
  run_solver.py
  config/
    schema.py
  problem/
    outer_problem.py
    inner_bridge.py
  pipeline/
    genome.py
  bias/
  plugins/
  reporting/
  tests/
```

不要把完整 case 长期放到：

```text
my_project/<case>
```

`my_project/` 只作为 starter template、参考骨架、兼容层或个人孵化位。

迁移检查清单：

- `my_project/<case>` 中的完整装配逻辑迁到 `examples/cases/<case>`。
- 旧入口只保留 thin wrapper 或 compatibility note。
- `build_solver.py` 不堆 problem/pipeline/plugin 细节。
- case 内部按 `problem/pipeline/config/reporting` 分层。
- 跨框架 case 通过正式 surface 传 ResourceContext。

## 10. 新机制落点决策树

当你想新增一个机制，先问：

| 问题 | 如果答案是 yes | 落点 |
| --- | --- | --- |
| 它改变候选生成策略吗？ | yes | Adapter |
| 它改变候选表示、decode 或 repair 吗？ | yes | RepresentationPipeline |
| 它只是软偏好或初始引导吗？ | yes | Bias |
| 它只是运行能力、记录、恢复、后端或副作用吗？ | yes | Plugin |
| 它改变目标或约束吗？ | yes | Problem/Evaluation |
| 它只是并行、设备、backend 或资源池吗？ | yes | L0 runtime/plugin |
| 它调度多个 solver 实例吗？ | yes | solver orchestration |
| 它控制内层组件参数吗？ | yes | representation decode + component_overrides + bridge |

如果一个文件同时做三件以上事情，通常说明边界错了。

## 11. 版本演进建议

推荐演进顺序：

1. 先跑单策略 baseline。
2. 再加真实 problem constraints。
3. 再加 representation typed genome。
4. 再加 bias seeds。
5. 再加多策略 adapter。
6. 再加 plugin trace/report/checkpoint。
7. 再加 nested inner runtime。
8. 最后做多 solver orchestration 和资源调度。

每一步都要保持可回退、可审计、可解释。不要一开始就把多 solver、嵌套训练、GPU、Redis、复杂 report 全部混在一起，否则失败时无法定位是哪一层的问题。

推荐把长期演进拆成版本号：

| 版本 | 内容 | 风险控制 |
| --- | --- | --- |
| v0 | 单 problem + 单 pipeline + 单 adapter | 只看 shape 和 smoke |
| v1 | 加真实约束和基础 report | 检查 objective/violation 方向 |
| v2 | 加 typed representation 或 component_overrides | report 记录 decode 结果 |
| v3 | 加 adapter group / serial group | trace 记录候选来源和 phase |
| v4 | 加 checkpoint/snapshot | 验证恢复后 adapter state |
| v5 | 加 nested inner runtime | inner report 和 outer objective 对齐 |
| v6 | 加 L0 lease / GPU / 多进程 | active lease、ResourceContext 可审计 |
| v7 | 加多 solver orchestration | 每个 solver profile 独立 summary |

每升一个版本，只新增一个主机制。效果变差时先回退最近版本，而不是同时调 problem、pipeline、adapter 和 plugin。

## 12. 提交前最小清单

- 是否保持 Solver / Adapter / Representation / Plugin 边界？
- 是否避免大对象直写 context？
- 若改评估链，是否验证单点/批量/插件短路？
- 若改 catalog，是否验证 `default` 与 `framework-core`？
- 若新增 example/case，是否放在 `examples/cases/<case>/`？
- 是否运行 `project doctor --strict --format problem` 并确认无新增 error？
