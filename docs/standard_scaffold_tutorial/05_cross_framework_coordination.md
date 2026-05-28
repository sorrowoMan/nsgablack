# 05. nsgablack 与 mlblack 如何协同

当任务同时包含“结构搜索”和“模型训练”时，不应该让一个框架吞掉另一个框架的职责。推荐分工是：

```text
nsgablack:
  outer structure / policy / multi-objective search
  adapter orchestration
  representation genome
  outer resource allocation
  objective / constraint aggregation

mlblack:
  inner data / numericizer / pipeline
  trainer family / preset / head
  fixed-structure fitting
  artifact / metrics / report
  inner ResourceContext consumption
```

## 0. 术语与组件引用

本章会同时使用 `nsgablack` 和 `mlblack` 的标准脚手架术语。两边有一些同名词，但语义并不相同；如果不先对齐，后面的 `pipeline`、`component_overrides`、`ResourceContext`、`portfolio` 很容易被读成同一个东西。

| 术语 | nsgablack 中的含义 | mlblack 中的含义 | 协同规则 / 详解 |
| --- | --- | --- | --- |
| pipeline | 候选解表示管线，负责 `init/mutate/repair/encode/decode` 和 typed genome | 数据/特征表示管线，负责 numeric features、orthogonal basis、learnable operator 等 | 外层 decode 结构，内层变换数据；不要把两种 pipeline 混写 |
| adapter / trainer | `Adapter` 是搜索策略，负责 `propose/update` | `Trainer` 是固定结构下的拟合器，负责 fit/predict/artifact | 不要让 nsgablack adapter import mlblack trainer，也不要让 trainer 变成搜索器 |
| plugin / capability | `Plugin` 是 solver 生命周期能力，例如 event、checkpoint、trace、report | `Capability` 是 flow 生命周期能力，例如 metric_guard、experiment_tracker、component_override | 两边都可以写审计与信号，但挂载点不同 |
| problem / evaluation | outer objective/constraint evaluator，负责把候选投影为 objectives / violations | 数据任务、评估代理或 inner metrics/report 的一部分 | 跨框架只交换稳定 payload，不交换私有对象 |
| ResourceContext | parent allocator 发出的资源授权，包含 device token、thread、namespace、budget | inner flow/trainer 消费的资源上下文 | 只传 JSON-compatible context，不让 mlblack import nsgablack |
| component_overrides | outer genome 解码后的内层组件参数 | 应用到 `trainer`、`trainer.<key>`、`pipeline`、`pipeline.<key>`、`numericizer`、`bias`、`capability` 等稳定路径 | 所有 override 必须可审计、可报告、可复现 |
| portfolio | 多 solver、adapter group 或 search profile 的外层编排 | 多 trainer/pipeline/resource 候选的模型组合比较 | outer 搜 portfolio 结构，inner 执行给定 portfolio |
| artifact / snapshot | snapshot 保存 population/objectives/frontier/trace 等大对象引用 | artifact 保存模型、metrics、trainer_state、flow_report 等交付物 | 大对象走各自 snapshot/artifact surface，context 只留引用 |

组件索引参考：`nsgablack` 侧见 [组件导读索引](../guides/README.md)，`mlblack` 侧见 `C:\Users\hp\Desktop\mlblack\docs\guides\README.md`。资源与并行边界见 [06. L0 并行与资源模式](06_l0_parallel_resource_patterns.md)；mlblack family/head/mechanism 的细节见 `C:\Users\hp\Desktop\mlblack\docs\standard_scaffold_tutorial\08_family_head_mechanism_stage_cookbook.md`。

## 1. 为什么要分层

如果把结构搜索塞进 mlblack trainer，trainer 会膨胀成第二个优化框架；如果把训练细节塞进 nsgablack problem，outer problem 会变成私有训练脚本。两种都会破坏可审计性。

正确边界：

| 问题 | 应归属 |
| --- | --- |
| 搜索 kernel shape / basis subset / gate / regime policy | nsgablack |
| 拟合固定结构下的系数或模型参数 | mlblack |
| 多目标折中 accuracy / complexity / runtime / stability | nsgablack |
| 训练 RMSE、artifact、flow_report | mlblack |
| 外层多候选并发、GPU lease | nsgablack L0 |
| 内层 trainer 使用哪个 device/thread | mlblack 消费 ResourceContext |

## 2. 标准数据流

```text
outer adapter proposes x
  -> outer representation decodes typed genome
  -> component_overrides
  -> acquire ResourceLease
  -> ResourceContext
  -> mlblack build_flow(...)
  -> flow.fit(data)
  -> inner metrics/artifact/report
  -> outer objectives/violations
  -> adapter.update(...)
  -> report / snapshot / trace
```

这一条链路里，只有两个对象跨框架传递：

- `component_overrides`
- `resource_context`

不要跨框架传递 trainer 实例、pipeline 内部对象、全局变量或私有 module 状态。

## 3. outer genome 怎么设计

outer genome 负责结构，不负责所有连续参数。典型设计：

| genome 字段 | 含义 | 输出 |
| --- | --- | --- |
| `structure_type` | kernel / symbolic / gate / lane | component key |
| `basis_mask` | 使用哪些 basis | `component_overrides.pipeline.*` |
| `complexity_budget` | 最大项数、rank、层数 | constraint 或 override |
| `refinement_budget` | 内层拟合步数 | `component_overrides.trainer` 或 `component_overrides.trainer.<trainer_key>` |
| `safety_mode` | 是否启用保守策略 | capability/evaluation override |

示例：

```python
def decode_outer_candidate(x):
    structure = decode_structure_type(x[0])
    basis = decode_basis_mask(x[1:8])
    rank = decode_rank(x[8])
    refine_steps = decode_refine_steps(x[9])

    return {
        "pipeline.symbolic_kernel": {
            "structure": structure,
            "basis": basis,
            "rank": rank,
        },
        "trainer.symbolic": {
            "refinement_steps": refine_steps,
            "refinement_method": "trust_region_dfo",
        },
    }
```

注意：`mlblack` 的通用 `component_overrides` 匹配器支持 `trainer` / `trainer.<trainer_key>`、`pipeline` / `pipeline.<pipeline_key>`、`numericizer`、`bias`、`capability` 等稳定路径。`trainer.refinement` 这类二级路径不是默认通用语义，只有 case 自己实现 resolver 时才成立。

如果你发现 outer genome 里有大量连续系数，例如 200 个 kernel coefficients，通常说明边界错了。结构交给 outer，系数细化交给 inner。

## 4. mlblack build_flow 标准入口

mlblack 侧只暴露正式 scaffold surface：

```python
def build_flow(
    cfg,
    *,
    resource_context=None,
    component_overrides=None,
):
    flow = MLFlow(run_name=cfg.run_name)
    flow.set_numericizer(cfg.numericizer_key, params=cfg.numericizer_params)
    flow.set_pipeline(cfg.pipeline_key, params=cfg.pipeline_params)
    flow.set_trainer(cfg.trainer_key, params=cfg.trainer_params)
    flow.set_component_overrides(component_overrides or {})
    flow.set_resource_context(resource_context or {})
    flow.set_execution(cfg.execution)
    flow.set_orchestration({
        **cfg.orchestration,
        "nested": True,
        "outer_framework": "nsgablack",
    })
    for capability in cfg.capabilities:
        flow.add_capability(capability.key, params=capability.params)
    flow.set_output_dir(cfg.output_dir)
    return flow
```

禁止：

```python
# 错误：nsgablack case 直接 import mlblack trainer 并私下传 cuda:0
trainer = TorchTrainer(device="cuda:0", hidden_dims=[128, 64])
trainer.fit(X, y)
```

正确：

```python
flow = build_flow(
    cfg,
    resource_context=lease.resource_context(compute_backend="torch", device="auto"),
    component_overrides=decode_outer_candidate(x),
)
result = flow.fit(data)
```

## 5. ResourceContext 协调

nsgablack 负责发 lease：

```python
lease = allocator.acquire(
    ResourceRequest(threads=2, gpus=1, backend="local"),
    owner_id="trial_0007",
    scope="outer_eval",
)

resource_context = lease.resource_context(
    compute_backend="torch",
    device="auto",
    execution_backend="thread",
    namespace="nsgablack.trial_0007",
)
```

mlblack 只消费：

```python
flow.set_resource_context(resource_context)
```

优先级：

```text
nsgablack ResourceLease
  > injected ResourceContext
  > mlblack execution defaults
  > legacy trainer device fields
```

如果 outer 给的是 `cuda:0`，inner 不能私下改成 `cuda:1`。如果 inner 不支持 GPU，应在 report 中写明 fallback，而不是静默忽略。

## 6. objective / violation 契约

inner result 应返回稳定 payload：

```python
{
    "status": "ok",
    "metrics": {
        "valid.rmse": 0.51,
        "test.rmse": 0.55,
        "test.mae": 0.41
    },
    "cost": {
        "runtime_seconds": 12.4,
        "fit_seconds": 10.8
    },
    "complexity": {
        "term_count": 8,
        "rank": 2
    },
    "reports": {
        "flow_report_path": "runs/inner_trial_0007/flow_report.json"
    },
    "effective": {
        "trainer_key": "ridge",
        "pipeline_key": "symbolic_kernel",
        "resource_context": {},
        "component_overrides": {}
    }
}
```

outer objective 示例：

```python
objectives = np.asarray([
    result["metrics"]["valid.rmse"],
    result["complexity"]["term_count"],
    result["cost"]["runtime_seconds"],
], dtype=float)
```

outer violation 示例：

```python
violations = np.asarray([
    max(0.0, result["metrics"]["valid.rmse"] - task.max_rmse),
    max(0.0, result["complexity"]["term_count"] - task.max_terms),
    max(0.0, result["cost"]["runtime_seconds"] - task.max_runtime),
], dtype=float)
```

不要让 outer problem 解析 mlblack 私有 artifact 对象。outer 只消费稳定 metrics/cost/complexity/effective/report 字段。

## 7. 常见协同模式

| 模式 | nsgablack 负责 | mlblack 负责 |
| --- | --- | --- |
| symbolic residual search | basis、term、complexity search | residual fit、metrics、formula report |
| learnable kernel structure | kernel type、shape、symmetry、rank | coefficient refinement、trainer fit |
| regime-aware policy | regime split、policy genome | 每个 regime 的 predictor/evaluator |
| model family selection | family/pipeline candidate as genome | 每个 family 的 fit/report |
| hyperparameter Pareto | multi-objective search | fixed config training/eval |
| resource-aware search | trial priority、lease、budget | obey ResourceContext and report usage |

### 7.1 outer 搜什么，inner 配什么

跨框架 case 不一定只搜 symbolic kernel。外层也可以搜索 family、head、pipeline、runtime mechanism 和 staged search 方案，但输出仍应落成 `mlblack` 能审计的 scaffold 语言。

| 搜索对象 | outer genome 示例 | inner mlblack 落点 | outer objective 示例 |
| --- | --- | --- | --- |
| family 选择 | `family_id in {ridge,xgboost,mlp_torch,symbolic}` | `portfolio_model.trainer_key` 或 scaffold model candidate | accuracy、runtime、artifact size |
| head 选择 | `head_id in {point,interval}` | `family_spec.task_head` / `orchestration.selection_policy` | RMSE 或 coverage/width，不直接混算 |
| pipeline 选择 | `pipeline_id in {identity,zscore,orthogonal}` | `pipeline_key` / `pipeline_params` | accuracy、stability、transform cost |
| basis mask | binary mask over candidate terms | `component_overrides.pipeline.<pipeline_key>` | RMSE、term count、stability |
| runtime mechanism | mechanism bitset + params | `trainer_params.mechanisms` 或 `component_overrides.trainer.<trainer_key>` | RMSE、fit time、sample usage |
| residual stage | stage sequence / accept gate | `orchestration.stage_spec` + staged runner | final RMSE、stage complexity、test gap |
| resource policy | threads / gpu / priority | `ResourceContext` | throughput、OOM risk、idle GPU time |

示例：外层把一个候选解码成完整 inner assembly 片段，而不是直接 new 一个 trainer。

```python
def decode_candidate_to_inner_payload(x):
    family_id = decode_family(x[0])
    head_id = decode_head(x[1])
    basis = decode_basis_mask(x[2:10])
    use_loss_weighting = bool(round(x[10]))

    trainer_key = {
        "linear": "ridge",
        "boosting": "xgboost",
        "neural": "mlp_torch",
        "symbolic": "symbolic",
    }[family_id]

    trainer_params = {}
    if trainer_key == "symbolic":
        trainer_params["family_spec"] = {
            "trainer_key": "symbolic",
            "structure_engine": {
                "structure_mode": "orthogonal_basis_search",
                "search_driver": "nsgablack",
            },
            "parameter_backend": {"backend": "ridge"},
            "task_head": {"task": head_id, "outputs": ["mean"] if head_id == "point" else ["lower", "upper"]},
        }

    if use_loss_weighting:
        trainer_params["mechanisms"] = [
            {"key": "state_signal_view.prediction_residual", "params": {}},
            {"key": "sample_weighting.loss_adaptive", "params": {"alpha": 0.5}},
            {"key": "aggregation.ensemble_summary", "params": {}},
        ]

    component_overrides = {
        "pipeline.symbolic_kernel": {
            "basis": basis,
            "max_terms": int(decode_max_terms(x[11])),
        },
        f"trainer.{trainer_key}": {
            "refinement_steps": int(decode_steps(x[12])),
        },
    }

    return {
        "trainer_key": trainer_key,
        "trainer_params": trainer_params,
        "pipeline_key": "symbolic_kernel" if trainer_key == "symbolic" else "identity",
        "component_overrides": component_overrides,
        "orchestration": {
            "outer_search_axes": ["family", "head", "basis", "mechanism", "refinement_budget"],
            "head_aware_selection": True,
        },
    }
```

outer 仍然只拿稳定 payload 做 objective：

```python
result = inner_runner.evaluate(payload, resource_context=resource_context)

if result["status"] != "ok":
    return failed_objectives(), failed_violations()

objectives = np.asarray([
    result["metrics"].get("valid.rmse", 1e9),
    result["complexity"].get("term_count", 1e9),
    result["cost"].get("runtime_seconds", 1e9),
], dtype=float)

violations = np.asarray([
    max(0.0, result["metrics"].get("test_gap", 0.0) - max_test_gap),
    max(0.0, result["resource"].get("gpu_memory_peak_ratio", 0.0) - 0.9),
], dtype=float)
```

这里的关键不是“nsgablack 会写 mlblack 的配置”，而是 outer 只负责搜索结构和预算，inner 只负责把某个确定配置训练、评估、产出 report。两边通过 JSON-compatible payload 对齐，不互相 import 私有对象。

## 8. 失败模式

inner run 可能失败，outer 不能崩成不可解释状态。建议统一失败 payload：

```python
{
    "status": "failed",
    "error_type": "ResourceBudgetError",
    "message": "device cuda:0 unavailable",
    "metrics": {},
    "cost": {"runtime_seconds": 0.0},
    "violations": {"inner_failure": 1.0},
    "reports": {}
}
```

outer 处理：

```python
if result["status"] != "ok":
    objectives = np.asarray([1e9, 1e9, 1e9], dtype=float)
    violations = np.asarray([1.0], dtype=float)
```

失败必须进入 report，不能只打印到控制台。

## 9. 报告字段建议

outer report 至少记录：

| 字段 | 说明 |
| --- | --- |
| `outer_trial_id` | 外层候选 id |
| `genome` | 原始候选或 snapshot ref |
| `decoded_overrides` | decode 后的 component_overrides |
| `resource_context` | 实际资源授权 |
| `inner_run_name` | mlblack run |
| `inner_metrics` | inner metrics |
| `inner_report_path` | flow_report |
| `objectives` | outer objective |
| `violations` | outer constraints |
| `status` | ok/failed/skipped |

inner report 至少记录：

| 字段 | 说明 |
| --- | --- |
| `assembly` | trainer/pipeline/numericizer/capability |
| `component_overrides` | 外层注入参数 |
| `resource_context` | 生效资源 |
| `orchestration.outer_trial_id` | 外层来源 |
| `metrics` | train/valid/test |
| `artifact` | 模型产物 |
| `capability_reports` | guard/tracker/operator 等 |

## 10. 反模式

| 反模式 | 问题 | 改法 |
| --- | --- | --- |
| nsgablack 直接 import mlblack trainer | 绕过 mlblack scaffold/report | 调 `build_flow()` |
| mlblack trainer 私下搜索结构 | 变成第二个 outer optimizer | 结构交给 nsgablack |
| outer genome 直接包含大量连续系数 | 搜索维度爆炸 | outer 搜结构，inner 拟合系数 |
| example 文件写死 `cuda:0` | 资源不可审计 | 通过 ResourceContext |
| inner 失败只 print | outer 不知道失败原因 | 返回 failed payload |
| component override 用全局变量 | 不可复现 | 稳定 key + report |
| report 只写最终指标 | 无法解释机制 | 写 effective assembly 和 overrides |

## 11. 最小验收清单

- nsgablack outer problem 不 import mlblack 私有 trainer。
- mlblack inner 通过 `build_flow(resource_context, component_overrides)` 运行。
- `component_overrides` key 稳定，并写入 inner report。
- `ResourceContext` 在 outer 和 inner report 中一致。
- inner result payload 字段稳定。
- outer objectives/violations 只依赖稳定 payload。
- 失败路径有明确 penalty 和 report。
- cross-framework case 放在 `examples/cases/<case>/`，不是长期堆在 `my_project/`。
