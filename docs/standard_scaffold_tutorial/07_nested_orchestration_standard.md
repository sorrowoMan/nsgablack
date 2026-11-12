# 07. 标准嵌套 Case 编排

嵌套编排不是在外层 `evaluate()` 中直接 import 一个 Trainer 或 Solver。它表示：

- 外层和内层都是可独立运行的标准 Case；
- 两者使用同一个 `build_solver.py::build_solver()` 装配入口；
- 父 Case 通过 blackbase 公共协议调用子 Case；
- 子运行拥有明确 lineage、deadline/cancellation、子资源 grant、预算 handle 和结果信封。

## 1. 公共对象

所有编排协议都归 `blackbase`：

- `CaseRunRequest`：子 Case 的声明请求；
- `CaseRunResult`：版本化、可序列化的统一结果信封；
- `CaseRunIdentity`：Project run、root run、parent Case、invocation、attempt、depth；
- `ExecutionControl`：当前 cancellation ref、祖先取消链与有效绝对 deadline；
- `ChildResourceGrant`：父 grant 内原子划分的子授权；
- `BudgetHandle`：父预算预留后形成的有界子预算；
- `ArtifactBinding`：把 `DataRef` 与 Case-finalization-sealed publication receipt
  绑定在一起的跨 Case 输入能力；
- `CaseExecutor` / `CaseInvoker`：标准装配与递归调用的唯一执行边界。

`nsgablack` 与 `mlblack` 不各自实现一套 nested runner。

## 2. 父 Case 调用子 Case

标准执行器会给 Case 注入 `case_runtime`。父 Case 只声明请求，不读取子 Case 的
builder，也不自行伪造 `ResourceContext`：

```python
from blackbase.project import CaseRunRequest


class OuterCase:
    def run(self):
        child = self.case_runtime.invoke(
            CaseRunRequest(
                project_name="hybrid_system",
                stage_name="inner_training",
                case_name="train_surrogate",
                case_kind="trainer",
                resource_request={
                    "workers": 1,
                    "threads": 2,
                    "gpus": 0,
                },
                budget_request={"evaluations": 100},
                input_artifact_bindings={"dataset": self.dataset_binding},
                inputs={"model_width": 128},
                component_overrides={"trainer.max_steps": 500},
            )
        )
        if not child.ok:
            raise RuntimeError(child.error)
        return {
            "inner_metrics": child.output["metrics"],
            "artifact_refs": {
                "model": child.artifact_refs["model"].as_dict(),
            },
        }
```

若 Case 对象需要读取非 Artifact 的轻量输入，实现：

```python
def set_case_inputs(self, inputs):
    self.case_inputs = dict(inputs)
```

若需要自定义 runtime 注入，实现：

```python
def set_case_runtime(self, runtime):
    self.case_runtime = runtime
```

普通可设置属性的对象不必实现该 setter。

`DataRef` 只描述数据位置，不证明它来自一个成功 Case。正式 `input_artifacts` 由
`input_artifact_bindings` 自动派生；调用方不得手工把裸 `DataRef` 提升为跨 Case
权威产物。Project Stage 的 `input_artifacts` 声明会由 Registry 自动解析为绑定。

### Project 静态 DAG 与动态子 Case

运行前已经知道的 Case 关系应放在 BlackBase Project DAG：

```python
{
    "name": "workflow",
    "policy": "dag",
    "cases": ["prepare", "baseline", "outer_search"],
    "depends_on": {"outer_search": ["prepare"]},
    "input_artifacts": {
        "outer_search": {"baseline": "baseline.summary"},
    },
}
```

`baseline.summary` 会自动形成 `baseline → outer_search` 依赖边；调度器只在所有上游
成功并发布权威 Artifact 后启动下游。环、未知节点和自依赖在运行前拒绝，实际并行度仍
由 L0 grant 决定。

候选数量只有运行时才知道的调用不展开成静态 DAG。例如外层 Solver 每次评估调用一个
Trainer，Trainer 再调用一个 Solver，仍使用 `case_runtime.invoke()`。因此完整视图是：

```text
Project 静态 DAG
└─ Case 动态调用树
   └─ Solver/Trainer 内部迭代状态机
```

## 3. Lineage 与控制继承

父调用生成子 identity：

```text
project_run_id  保持不变
root_run_id     保持不变
parent_case_run_id = 父 case_run_id
case_run_id     每次调用唯一
invocation_id   每次调用唯一
depth           父 depth + 1
```

子 `ExecutionControl` 保留父 cancellation ref 作为祖先。有效 deadline 是当前和
所有祖先 deadline 的最小值，因此子 Case 不能延长父 Case 的截止时间。Case 可以在
长循环、Provider 等待或批处理边界调用：

```python
self.case_runtime.checkpoint()
```

这里的 checkpoint 是取消与截止时间检查，不是保存求解检查点；
Solver/Trainer 的可恢复状态仍由各自的正式 checkpoint 组件保存。

Project 超时、父 Case 取消或并行 `fail_fast` 都会写入可跨进程重建的 cancellation
authority。它是协作式取消；不可中断的第三方调用仍需由对应 Provider 提供取消能力。

## 4. 资源与预算不能复制

默认本机调用时，父 Case 的 L0 grant 是硬上界。`CaseInvoker` 在父 grant 内维护共享子资源池：

- 子请求超过父线程、GPU 或 device token 授权时立即失败；
- 多个并行子调用对父资源做原子竞争，不能各自复制完整父额度；
- 子 namespace、grant ID、父 lease 与 fencing token 会进入结果审计；
- 等待资源时仍持续检查 deadline/cancellation。

预算也不传普通 `remaining_budget` 数字。父调用先在共享 Budget Authority 中预留，
再给子 Case 一个 `BudgetHandle`。子 Case仍在真实 charging point 使用
`BudgetAccount.from_resource_context(...)`；完成后实际消耗计入父预算，未使用部分返还。

Project 显式配置 `L0.nested_execution.case_names` 后，被选中的完整内层 Case 可复用外部 Worker 执行。
此时目标物理容量来自 Project 对该 target 的共享持久 L0 授权，不把父本机的线程数复制成远端授权；
逻辑 lineage、取消、deadline、父级预算委托和 Artifact 收据继续贯穿。
`CaseInnerRuntimeEvaluator(max_workers=...)` 请求批次并发，Project 控制生效上限和放置。

内层需要父级已注入的数据时，增加 `artifact_bindings={"dataset": "dataset"}`：
左边是内层输入名，右边是父 Case 的 `input_artifacts` 名。
框架转交原发布收据；内层从自己的 `runtime.request.input_artifact_bindings` 取 binding，
再用 `runtime.artifact_publisher.read_verified(binding)` 读取。
只传源文件路径不能代替这份声明；引用注入本身不执行下载或初始化 Unit。
未命中的下层调用继续 local。完整装配和当前限制见
[状态减负与内层 Case 批量执行](../architecture/STATE_COST_AND_NESTED_EXECUTION_CN.md)。

## 5. 统一结果信封

串行 Project、进程池、外部 worker 和父子调用都返回同一种 `CaseRunResult`：

```text
schema_version
request + identity + control
status
output
artifact_refs
artifact_publications
resource_usage
budget_usage
started_at / finished_at / elapsed_seconds
exit_code
structured failure
metadata / runtime audit
```

协议读取严格检查 `schema_version`，不猜测旧字典的含义。标准状态包括
`succeeded`、`built`、`checked`、`resumed`、`failed`、`cancelled`、`timed_out`
和 `skipped`。

## 6. Canonical 入口

Solver 与 Trainer 的目录形状一致：

| 语义 kind | 唯一装配入口 | 唯一 CLI 入口 |
| --- | --- | --- |
| `solver` | `build_solver.py::build_solver()` | `run_solver.py` |
| `trainer` | `build_solver.py::build_solver()` | `run_solver.py` |

`build_trainer.py` 与 `run_trainer.py` 只能是薄别名。kind 只改变运行时优先选择
`run()` 还是 `fit()`，不能制造第二套装配。

## 7. 最小检查清单

- 父子均为完整标准 Case，且可以独立 build/run；
- 父 Case 只调用 `case_runtime.invoke()`；
- 子输入是轻量 `inputs` 或经验证的 `ArtifactBinding`，不是父对象内部状态；
- 子资源来自 `ChildResourceGrant`，预算来自 `BudgetHandle`；
- 长运行逻辑设置 checkpoint；
- 调用方检查 `CaseRunResult.ok` 并保留失败信封；
- Artifact 通过命名引用返回；
- Project Manifest 保存完整版本化结果信封。

## 8. Pool 与三级 Case 的边界

每个 Solver/Trainer 运行维护自己的 SolutionPool、候选身份、逻辑时钟和 Unit。
Project 的父子调用关系不自动把两个池接成一个可写的母池/子池。
同一 Case 内 Router/Chain 的 working_pool 继承也止于该 Case 的调用作用域，
不会成为新 Case 的默认工作区域。

正式示例 `examples/cases/super_topology_orchestration` 的三级语义是：

```text
外层 Solver：x = (capacity, regularization)，二维配置
    → Trainer：以 x 创建训练问题和模型规格
        → 内层 Solver：target = clip(0.5 × (capacity - regularization))
                         搜索一维 calibration = y
        ← 返回已评估、由内层选中的 y
    ← 用 x 和 y 计算 loss、complexity
外层：把这两个目标作为 x 的原始求值
```

这里的 y 属于另一候选空间。它进入 Trainer 的模型与评分计算，不直接作为二维配置加入外层池。
父池也不自动接收内层全部尝试、继承内层排名或修改原 x 的身份。
子调用资源、预算、deadline 和结果收据继续经 BlackBase 管理。

### 8.1 什么时候才需要把父池候选交给内层

业务明确需要暖启动、参考解集合或历史候选时，才增加这项输入：

1. 父层先选择并冻结候选版本，明确交付用途。
2. 少量可传输值通过 inputs 或 builder 的 component_overrides 交付；大集合和持久对象通过
   ArtifactBinding 交付，不能仅给子 Case 一个父池的 SolutionRef。
3. 接收方显式消费输入。需要暖启动时，已有 `set_warm_start(candidate, source_run_id=..., metadata=...)`
   会排队种子，进入本层正常初始化和求值；inputs 注入本身不等于自动播种。
4. 同空间仍需验证维度与问题含义；异空间必须提供明确映射。本例的 x→target 是问题参数映射，
   不意味着把二维 x 当成一维 y 的初始点。
5. 源引用可以作为来源证据保留，接收方建立本地地址。父反馈、Bias 分数和 Unit 不自动成为子层权威。

当前没有新增自动跨 Case 池导入 API。若未来出现多个相同需求，可以把候选 payload、来源、映射和
接受方用途收敛成可复用交接约定；这不要求共享可写 Pool 或自动回写祖先池。

### 8.2 提交与恢复仍分别归属各层

内层 Case 已成功发布的结果和真实预算消耗，不随外层后续步骤失败而撤销。
再次调用默认创建新的子运行；父 checkpoint 不自动表示动态子任务已经去重或已经续跑。
若业务需要复用已完成子求解，应显式保存逻辑请求与成功结果收据，按相同问题、输入版本、
配置和随机性约定决定是否可以复用，不能只按候选数值相等猜测。
