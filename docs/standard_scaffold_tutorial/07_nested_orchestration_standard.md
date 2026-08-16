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
                input_artifacts={"dataset": self.dataset_ref},
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

Project 超时、父 Case 取消或并行 `fail_fast` 都会写入可跨进程重建的 cancellation
authority。它是协作式取消；不可中断的第三方调用仍需由对应 Provider 提供取消能力。

## 4. 资源与预算不能复制

父 Case 的 L0 grant 是硬上界。`CaseInvoker` 在父 grant 内维护共享子资源池：

- 子请求超过父线程、GPU 或 device token 授权时立即失败；
- 多个并行子调用对父资源做原子竞争，不能各自复制完整父额度；
- 子 namespace、grant ID、父 lease 与 fencing token 会进入结果审计；
- 等待资源时仍持续检查 deadline/cancellation。

预算也不传普通 `remaining_budget` 数字。父调用先在共享 Budget Authority 中预留，
再给子 Case 一个 `BudgetHandle`。子 Case仍在真实 charging point 使用
`BudgetAccount.from_resource_context(...)`；完成后实际消耗计入父预算，未使用部分返还。

## 5. 统一结果信封

串行 Project、进程池、外部 worker 和父子调用都返回同一种 `CaseRunResult`：

```text
schema_version
request + identity + control
status
output
artifact_refs
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
- 子输入是轻量 `inputs` 或 `DataRef`，不是父对象内部状态；
- 子资源来自 `ChildResourceGrant`，预算来自 `BudgetHandle`；
- 长运行逻辑设置 checkpoint；
- 调用方检查 `CaseRunResult.ok` 并保留失败信封；
- Artifact 通过命名引用返回；
- Project Manifest 保存完整版本化结果信封。
