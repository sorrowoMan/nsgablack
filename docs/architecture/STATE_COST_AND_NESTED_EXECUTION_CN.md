# 状态减负与内层 Case 批量执行

本轮实现日期：2026-10-30。本文区分已实现的接口、已执行的验收和仍需验证的部署条件。
生产供排模型没有在本轮改变，之前暂停的长计算也没有恢复。

## 1. 状态减负保留哪些语义

SolutionPool 继续保存不可原位修改的候选版本；Unit 继续归实际 Adapter 所有。
失败步骤恢复搜索状态，已经发生的求值和预算消耗保留。提交后才能公开新池成员。

基础改动完成两个局部优化：

1. BlackBase SnapshotStore 在**一次 write 内**复用安全 roundtrip 的准备值。
   普通容器与数组可以复用已证明稳定的 safe-wire 来生成原版本摘要，File extras 也可复用编码。
   协议对象、自定义 Mapping 等会在恢复时规范化的值保留原检查路径。
   不增加跨调用缓存，不改变摘要 codec/schema，读取仍核验摘要与身份。
2. `RuntimeTransaction` 捕获 Pool 后，步骤拒绝直接由同一所有者消费已捕获基线。
   不再额外生成第二份完整 Pool baseline。
   零接纳仍可保留本轮创建的输入标识并重置游标，异常仍能撤回整个尝试。

共享接口为 `transaction.reconcile(owner, owner.method)`。仅已捕获的 owner 的绑定方法可以读取基线；
方法必须像 restore 一样只读该基线，调用后事务仍可回滚，结束后不允许调用。
此接口不给外部返回可变快照，也不复制任意活对象图。

一个含 12 条记录及一个 ndarray 的单次写入诊断中，safe-wire 递归次数从 186 降至 89，
lossless 校验从 182 降至 89，摘要完全相同。这是函数调用计数，不是完整排程提速比例。

后续减负又合并候选和 provenance 的调用内读取，并对普通 ndarray 草稿直接复制，
移除两次经 Python list 的 codec roundtrip；语义状态仍走原 codec。
Pool 发布已验证的纯数据索引从 prepare 移交到 commit，正常路径的 Record 解码由 2N 次降为 N 次。
恢复 prepared 快照会重新核验持久 manifest，不把缓存当作恢复证据。
细节与验收见 [候选和索引减负](../development/POOL_MATERIALIZATION_REFINEMENT_CN.md)。

相邻事件可以归为一个有界、完整的证据 archive bundle，共同根按完整 SnapshotIdentity 去重。
三个相邻提交的验收由 3 份 Artifact／8 份根副本降为 1 份 Artifact／6 份根副本；
中断绑定、收据核验和恢复仍逐事件对账。它不宣称把 Pool 或运行检查点的传递闭包一并便携化。
实现约定见 BlackBase 的 `EVIDENCE_ARCHIVE_BUNDLES_CN.md`。

候选各阶段的持久登记、全量池索引生成和步骤快照展开仍保留。
这些优化没有关闭证据，也没有给出完整生产 100 代的耗时收益。

## 2. 用户在哪两处装配

Case 声明希望同时派发多少个候选，以及每个完整内层 Case 的资源/预算需求：

```python
from nsgablack.core import CaseInnerRuntimeEvaluator

problem.inner_runtime_evaluator = CaseInnerRuntimeEvaluator(
    case_name="inner",
    projector=project_result,
    max_workers=2,
    resource_request={"workers": 1, "threads": 1},
    budget_request={"evaluations": 2},
    timeout_seconds=30,
)
```

`artifact_bindings` 将子 Case 输入名映射到父 Case 的正式输入名。
父 Project 先以 `input_artifacts` 注入带发布收据的数据；Evaluator 从当前
`runtime.request.input_artifact_bindings` 转交原 binding，缺失即拒绝派发。
不需要输入时省略该参数。Solver 的 `set_input_artifacts()` 只接收引用，
不下载数据、不构造 Unit，也不把裸 DataRef 提升为发布权威。

`project_result` 由问题作者定义，解释内层产物如何构成外层目标。下面是二倍函数验收 Case 的完整投影，
其中内层发布 JSON Artifact `answer={"value": ...}`；它不代表生产排程模型的业务目标：

```python
import json
import numpy as np
from blackbase.resources import ArtifactBinding
from blackbase.types import Feedback

def project_result(solver, candidate, result):
    binding = ArtifactBinding(
        ref=result.artifact_refs["answer"],
        publication=result.artifact_publications["answer"],
    )
    data = json.loads(solver.case_runtime.artifact_publisher.read_verified(binding))
    return Feedback(
        objectives=np.array([data["value"]]),
        info={"child_run_id": result.identity.case_run_id,
              "receipt": binding.publication.receipt_digest},
    )
```

Project 再决定这些调用放在本机还是外部 Worker。没有 `L0.nested_execution` 时保持原本机调用。
声明远端执行的配置仍属于 `project_config.py`，Case 不自行创建全局租约或伪造远端 grant。

## 3. 本地两 Worker 的完整 Project 授权配置

下面使用同一文件系统的两个独立 Worker 进程验证实际队列、资源授权、预算与发布收据。
SQLite 路径必须处在所有进程都真实可访问的位置；这段配置不能直接当成无共享文件系统的三机部署。

```python
from pathlib import Path

PROJECT_NAME = "batch"
PROJECT_ROOT = str(Path(__file__).resolve().parent)
L0 = {
    "namespace": "batch.parent",
    "lease_backend": "sqlite",
    "lease_path": ".blackbase/parent.sqlite",
    "offer": {"threads": 1},
    "policy": {"mode": "strict", "max_workers": 1, "max_threads": 1},
    "default_request": {"workers": 1, "threads": 1},
    "budgets": {"evaluations": 6},
    "nested_execution": {
        "case_names": ["inner"],
        "shared_filesystem": True,
        "max_inflight": 2,
        "queue_timeout_seconds": 30,
        "transport": {"backend": "sqlite", "path": ".blackbase/tasks.sqlite"},
        "targets": {
            name: {
                "project_root": PROJECT_ROOT,
                "l0": {
                    "namespace": "batch.node." + name,
                    "lease_backend": "sqlite",
                    "lease_path": ".blackbase/node_" + name + ".sqlite",
                    "offer": {"threads": 1},
                    "policy": {"mode": "strict", "max_workers": 1, "max_threads": 1},
                },
            } for name in ("first", "second")
        },
    },
}
STAGES = [{"name": "run", "cases": ["outer"]}]
GROUPS = {"default": {"stages": ["run"]}}
```

两个独立终端分别运行既有 Worker 入口，`--worker-id` 对应 target 名称：

```powershell
python -m blackbase.project.external_worker --project-root . --backend sqlite --transport .blackbase/tasks.sqlite --worker-id first --threads 1
python -m blackbase.project.external_worker --project-root . --backend sqlite --transport .blackbase/tasks.sqlite --worker-id second --threads 1
```

再从第三个终端运行 Project 的 `python run_project.py`。
目标 Worker 会自动公布 `node:<worker-id>` 能力，队列据此把已授权的目标任务交给正确 Worker。

`max_workers` 是 Case 的请求上限；`max_inflight` 是每个父 Case 的 Project 授权上限。
多父 Case 的物理总用量由各 target 的共享持久 L0 ledger 原子约束。
父 Case 本地只有一个 CPU，也能等待两个已由 Project 另行授权的 Worker；父本机租约不冒充远端授权。

## 4. 跨机器需要替换的条件

跨主机使用 Redis transport、Redis 资源租约/取消控制，以及 Worker 可访问的共享预算和 Artifact authority。
各机器的代码、数据与依赖版本要一致；`project_root` 和额外 import 路径是目标机器路径。
配置只传服务描述与环境变量名，凭据保留在各机器自己的服务配置里。

跨 Windows/Linux 可用 `L0.artifacts.authority` 明确声明服务持有的同一 ArtifactAuthority；
不能将 Linux 服务 root 按 Windows 本地路径重新 resolve。
协调端及各 target 的声明必须匹配各自可信 `BLACKBASE_ARTIFACT_HTTP_PROFILE`，
不匹配立即失败，不退回本地目录。非回环端点只接受验证 CA 与主机名的 HTTPS。
具体配置见 BlackBase 的 `PROJECT_ARTIFACT_AUTHORITY_CN.md` 与 `ARTIFACT_HTTP_CN.md`。

供排标准 Project 的 `portable` group 增加 `production_sources` 阶段，先发布原始 BOM／到料字节。
`--portable-inputs` 使用 production_task/v2 传递原发布 binding、源 SHA256、格式和生产代码 manifest。
Worker 根据部署方的 `NSGABLACK_PRODUCTION_CASE_DIR` 读取预部署代码，并验证 manifest；
不接受协调机文件路径或任务自行指定的代码目录。今天库存及逐笔到料的原模型不变。

本机 Snapshot key 不能直接作为跨机可读地址。需要交付的排程、证据与 checkpoint 使用正式 Artifact 引用和收据。
不能只把 `shared_filesystem=True` 写进配置来代替真正共享存储，也不能依赖本机端口转发自动在远端成立。
完整服务配置和已拒绝的组合见 BlackBase 的内层外部执行说明。

`case_names` 明确选择需要外部分发的 Case。未命中的下一层调用继续使用原本机子授权，
不会因为父级选择了远端就把整个递归调用树再次搬走。
当前不支持向同一父物理容量账本再次申请远端递归，也不自动重试不确定的执行。

## 5. 批次与算法语义

`max_workers` 默认 1，保留逐点路径。大于 1 时，标准 Solver 的普通 Problem fallback 将调用
`CaseInnerRuntimeEvaluator.evaluate_batch(...)`，通过一个并行 `CaseStage` 派发完整子 Case。
`EvolutionSolver(enable_parallel=True)` 遇到完整 Case 也使用这条正式路径，不误入旧的 `nested_candidate_eval` 协议。

工厂、投影器、约束合并、Bias 和外层 Plugin hooks 都在调用线程执行；并发的只有完整子 Case。
整批结果先完成屏障，再按原输入顺序解释。相同数值的不同 token 保持独立。
任何子失败都不返回伪造的零分或部分成功批次，不重跑 Problem 兜底。
同一次整批 dispatch 计入外层 N 次求值，内层预算另由原 BudgetHandle 委托、结算。
根账应包含外层 N 次与内层真实评分 M 次；子分区的 M 已包含在根账中，不能拿根账总数再加一次子分区。

有 L4 Provider 注册或自定义 EvaluationMediator 时保留原逐点仲裁，避免批次优化绕开其决定权。
默认不把外层 GA 改成结果先到先更新的异步算法。

## 6. 失败与验收边界

排队取消与已执行任务的取消不同。已租用任务须等待其可信终结；单凭“发出了取消”不能归还机器容量。
提交后通信失败、Worker 丢失或结果身份/授权不符属于执行不确定：保留隔离和控制债务，
预算按预留上限保守结算，未用额度不能猜测退还。隔离容量不因普通 TTL 到期自动重新授予；
解除需要确认原 Worker 已停止，首版不提供自动解除。

本轮测试入口：

- `tests/test_case_inner_runtime_batch.py`：乱序、身份、Provider 仲裁、Bias/raw、计数与失败屏障。
- `tests/test_case_inner_external_dispatch.py`：真实两个 Worker 进程、队列、并发区间、预算和 Artifact 收据。
- BlackBase `tests/test_nested_external_cases.py`：目标授权、共享容量、取消、身份与不确定结算。
- `tests/test_pool_transaction_baseline.py`：单次捕获与两种恢复语义。
- BlackBase `tests/test_snapshot_write_preparation.py`：摘要等价、安全边界与遍历次数。

本地多进程检查之后，又完成了本机与两台香港节点的正式三机短验收：三份标准生产内层 Case 各评分一次并审计一次，根账六次评分／三次审计，十一份已封存产物完成本机核验保存。
实测也发现并修复 Project 结果登记误用本地 Ledger 的跨机缺口，以及部署漏包和连接数限制。
完整证据、两次前置失败、并行区间与资源偏差见
[三机验收记录](../../results/test_runs/cloud-case-20261030-bd0b7601/RESULT_CN.md)。
本轮临时部署已回收，长算仍暂停；完整池索引与快照展开仍保留，尚未证明生产全预算吞吐。
