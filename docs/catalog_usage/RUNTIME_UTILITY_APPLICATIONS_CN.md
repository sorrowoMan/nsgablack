# 工具究竟放在哪里：上下文、外部信号、并行与目录维护

本书的工具不需要假装成算法。下面每节给独立完整脚本或明确的 Case 插入点，说明其输入、实际消费者与输出。本轮没有执行脚本、连接 Redis、启动交互线程或调用模型。

## tool.context_schema · 构造一次调用的最小上下文

**什么时候用：** 为一个并行工作项或叶函数传递“当前行”的约束、代数、种子和少量元信息；需要在边界校验字段。它不包含整个种群、Provider session 或全局调度状态。

**先准备什么：** 当前 blackbase/nsgablack 环境。下面的输入就是三个实际约束残差，正值表示违约，本例约定求正部和；并非要求所有业务约束都必须按同一公式聚合。

**放在哪：** 在独立 Project 根保存 inspect_context.py。它是工具检查脚本，不进入 run_solver，不向共享 ContextStore 写 individual_id。把 leaf_penalty 换成自己的叶消费者时，仍保留其最小输入约定。

**接入步骤：** 完整脚本如下。

```python
import json
from blackbase.context import context_keys
from blackbase.context.key_registry import context_key_scope, current_context_registry
from nsgablack.core.state import MinimalEvaluationContext, validate_minimal_context


def leaf_penalty(context):
    validate_minimal_context(context)
    return float(context[context_keys.KEY_CONSTRAINT_VIOLATION])


def main():
    constraints = [-2., .5, 1.]
    local = MinimalEvaluationContext(generation=3, individual_id=0,
        constraints=constraints, constraint_violation=sum(max(0., c) for c in constraints),
        seed=17, metadata={"source": "manual_worker_input"}).to_dict()
    before = "case.worker_label" in current_context_registry().keys
    with context_key_scope(("case.worker_label",)):
        local["case.worker_label"] = "worker_0"
        registered_inside = "case.worker_label" in current_context_registry().keys
        print(json.dumps(dict(violation=leaf_penalty(local),
            individual_id=local[context_keys.KEY_INDIVIDUAL_ID],
            registered_inside=registered_inside, context=local), ensure_ascii=False))
    assert ("case.worker_label" in current_context_registry().keys) == before


if __name__ == "__main__":
    main()
```

context_keys 是共享词汇模块；优化扩展从 nsgablack.context_keys 取，不自行改变共享常量。scope 演示的是局部注册与退出，不是为一个标准 Case 在导入时永久注册私有键。标准 Case 若确实使用此键，把 `context_keys.json` 放在 Case 根，内容为 `["case.worker_label"]`，由正式运行入口加载；worker 也须获得明确的 scoped registry。

MinimalEvaluationContext 的 frozen dataclass 不代表内部 list/dict 深度只读；to_dict 创建顶层与这些容器的副本，不提供安全序列化或任意对象图恢复。validate_minimal_context 只检查必需字段与可转换类型，不证明约束语义或未知键已注册。不要用一个静态 individual_id 贯穿下一批候选。

**怎样判断接对：** 本例 violation=1.5，individual_id=0，registered_inside=true；scope 退出后私有键状态恢复。generation 是这次调用传入的3，不自动推进 Solver。JSON中的constraints是三条残差，而非成员数组。

**运行入口：** `python inspect_context.py`；没有启动求解或写共享库。

### 变体：另一个工作项

**目的：** 不继承上一行的身份与约束。**改在哪里：** main 中 local 构造完整替换为：

```python
local = MinimalEvaluationContext(generation=None, individual_id=1,
    constraints=[], constraint_violation=0., seed=18,
    metadata={"source": "second_worker_input"}).to_dict()
```

**行为变化：** 叶消费者返回0，当前行变为1。**限制：** 这是调用内位置，不是 SolutionRef/token；不携带全局 Unit。

## tool.parallel_evaluator · 对一批明确输入进行离线求值

**什么时候用：** 在算法外检查一个纯数值 Problem 的批量计算，或开发自己的受控评估桥。它是工程求值器，不是 Solver 的接纳、证据日志和池发布接口。

**先准备什么：** 独立复制完整 bias_gallery Project，保留原 SphereProblem。以下三个已知二维输入用于算术检查，非搜索初始种群。thread 主例只用1个 worker；如用于正式 Case，必须服从 Project 的有效资源 grant，不能自行按CPU总数扩容。

**放在哪：** Project 根 parallel_probe.py。不要在 Adapter.propose 或 Problem.evaluate 中再开启这个批量工具，也不要把返回三数组冒充已正式送评的种群。正式搜索优先使用框架的评估 Plugin/受授权集成面。

**接入步骤：** 完整脚本如下。

```python
import json
import numpy as np
from cases.bias_gallery.problem.example_problem import SphereProblem
from nsgablack.utils.parallel import ParallelEvaluator


def main():
    problem = SphereProblem(dimension=2)
    candidates = np.array([[0., 0.], [1., 2.], [-1., 0.]])
    with ParallelEvaluator(backend="thread", max_workers=1, strict=True,
            retry_errors=False, max_retries=0, extra_context={"generation": 0}) as evaluator:
        result = evaluator.evaluate_population(candidates, problem,
                                               enable_bias=False, return_detailed=True)
    F = np.asarray(result["objectives"])
    V = np.asarray(result["constraint_violations"])
    if result["error_count"] or not np.allclose(F[:, 0], [0., 5., 1.]):
        raise ValueError("unexpected raw Sphere result")
    print(json.dumps(dict(objectives=F.tolist(), violations=V.tolist(),
        errors=result["error_count"], success_rate=result["success_rate"])))


if __name__ == "__main__":
    main()
```

底层按idx放回结果，完成顺序不会变成候选顺序。max_workers、retry_errors 与 strict 是不同设置。源码存在任务失败转inf、后端异常回退串行等工程路径，strict并不构成“绝不回退后端”保证；因此显式检查error_count和结果。这里没有Bias，也没有把它调整后的矩阵当原始反馈。

**怎样判断接对：** objectives为3×1，值0/5/1；violations三行0，errors=0。耗时和线程调度不作固定断言。工具统计不自动增加运行中的 Solver 预算；这也是不能绕过正式评估面调用它的原因。

**运行入口：** `python parallel_probe.py`。本轮没有执行；它会真正调用三次Problem.evaluate。

### 变体：进程隔离

**目的：** 验证自己的 Problem 是否可被工作进程构造。**改在哪里：** 顶层增加 build_problem，并将with行及其参数替换如下，保留 main 保护。

```python
def build_problem():
    return SphereProblem(dimension=2)

# main 中
with ParallelEvaluator(backend="process", max_workers=1, strict=True,
        retry_errors=False, max_retries=0, problem_factory=build_problem) as evaluator:
    result = evaluator.evaluate_population(candidates, problem,
                                           enable_bias=False, return_detailed=True)
```

**行为变化：** 在进程中创建 Problem。**限制：** 顶层函数和模块可导入；不传锁、客户端、lambda或活Provider。此工具的fallback行为仍须检查日志，不能据构造参数宣称并行已验证。

## tool.context_store_redis · 给一个运行配置轻量共享存储

**什么时候用：** 已有可用Redis，希望轻量context引用在多个消费者间共享。它不替代SnapshotStore、SolutionPool或ArtifactStore，也不负责跨Case复制候选权威。

**先准备什么：** 当前框架、redis Python驱动、可访问的授权Redis；地址放在 `TUTORIAL_REDIS_URL` 环境变量，认证信息不要写入脚本或日志。复制完整bias_gallery；本轮没有连接该服务。

**放在哪：** Case runtime/redis_options.py 与 build_solver.py 的构造参数。完整使用者基于 CONTROL_STATE_APPLICATIONS_CN.md 已给出的全部文件，替换 common 的构造即可；不能在solver创建后偷偷替换一个新ContextStore而留下旧binding。

**接入步骤：** redis_options.py 完整内容：

```python
import os
import uuid
from nsgablack.core.state.context_store import RedisContextStore


def store_options():
    url = os.environ["TUTORIAL_REDIS_URL"]
    prefix = "tutorial:context:" + uuid.uuid4().hex
    return dict(context_store_backend="redis", context_store_redis_url=url,
                context_store_key_prefix=prefix, context_store_serializer="safe")


def inspect_one_value():
    options = store_options()
    store = RedisContextStore(redis_url=options["context_store_redis_url"],
        key_prefix=options["context_store_key_prefix"], serializer="safe")
    key = "case.redis_probe"
    try:
        store.set(key, {"label": "manual_probe", "step": 0}, ttl_seconds=30)
        value = store.get(key)
        if value != {"label": "manual_probe", "step": 0}:
            raise ValueError("Redis round trip differs")
        return value
    finally:
        store.delete(key)
```

在完整控制面builder导入store_options，再在构造solver前对common应用：

```python
from .runtime.redis_options import store_options

common.update(store_options())
```

这是构造位置的两行替换，不是独立运行文件。可选inspect_one_value只检查独立私有前缀，不能对共享运行前缀执行clear。safe编码闭包与大小限制由底座实现；TTL30是测试小值生命周期，不应给权威恢复引用随意加过期。

**怎样判断接对：** 启动正式Case时构造实际RedisContextStore；独立探针返回原小字典，随后仅删除本键。地址认证失败应传播，不应静默改内存；本例不证明跨机器授权、恢复或候选寻址。随机前缀隔离新运行，若要复用持久状态须由运行身份/恢复配置显式决定，不能每次随机化后声称已恢复旧数据。

**运行入口：** 完整Project的`python run_project.py --check --build-check`可能实际访问Redis，再运行Project。仅看源码无需执行。独立探针可在副本根 `python -c "from cases.bias_gallery.runtime.redis_options import inspect_one_value; print(inspect_one_value())"`，输出不含URL。

### 变体：只共享轻量引用

**目的：** 存已有Snapshot引用的轻量描述，不复制候选矩阵。**改在哪里：** 自己已有真实snapshot key的调用点使用：

```python
def publish_locator(store, snapshot_key, scope):
    if not snapshot_key or not scope:
        raise ValueError("an existing snapshot locator and scope are required")
    store.set("case.snapshot_locator", {"key": str(snapshot_key), "scope": str(scope)})
```

**行为变化：** context只保存定位描述。**限制：** 正式Case需在context_keys.json声明此键；这不是AuthorityIdentity验证或Snapshot复制，读取仍须验证原store/版本/摘要/owner。

## tool.dynamic_cli_signal · 把交互输入作为可选停止信号

**什么时候用：** 开发时希望输入一行JSON，在下次尝试前请求停止；不是把stdin当恢复日志、生产API或无声明的算法策略。

**先准备什么：** 完整控制面Case书的副本与三文件；前台终端必须能提供stdin。构造CLISignalProvider立即启动daemon读线程，它没有join/停止读线程实现；close继承空操作。不能在每次build/check时都构造一个读取者。

**放在哪：** runtime/cli_stop.py，并在builder装配extension；provider仅在setup创建，检查构造不会抢占stdin。

**接入步骤：** cli_stop.py完整内容：

```python
from nsgablack.utils.dynamic import CLISignalProvider
from nsgablack.core.semantic_extension import SolverSemanticExtension


class CLIStop(SolverSemanticExtension):
    name = "case.cli_stop"

    def __init__(self):
        self.provider = None

    def setup(self, solver):
        if self.provider is None:
            self.provider = CLISignalProvider()

    def before_step(self, solver):
        signals = self.provider.read()
        if signals.get("stop") is True:
            solver.request_stop("user_cli_stop")
```

完整控制面builder在return前增加两行：

```python
from .runtime.cli_stop import CLIStop
solver.register_semantic_extension(CLIStop())
```

进入before_step才读一次最新小字典；不把所有用户输入写进共享命名空间。CLISignalProvider会合并新键，未给的旧键仍保留。JSON的true必须为布尔；`stop=1`解析为整数，本例使用is True因此不会触发；用`stop=true`或JSON。

**怎样判断接对：** 前台运行后输入`{"stop": true}`，运行在下一个可检查的控制边界请求停止，stop_reason包含user_cli_stop；不是强杀正在计算的一行。搜索过快结束时可能来不及输入；不据此虚构读线程失败。当前尝试已开始时request_stop不会自动撤销本次，正式预算/提交规则继续生效。

**运行入口：** `python run_project.py`须在可交互前台；若Project运行器子进程不继承stdin，使用标准Case `run_solver.py`的前台入口并提供正常授权环境。服务端和Web不采用本方法；本轮未启动线程。

### 变体：由环境关闭交互

**目的：** 无人值守时保持同一builder。**改在哪里：** builder的CLIStop登记改为：

```python
import os
if os.environ.get("TUTORIAL_INTERACTIVE") == "1":
    solver.register_semantic_extension(CLIStop())
```

**行为变化：** 默认不读stdin。**限制：** 这是装配选择，不是运行中动态退出daemon；单个终端不能让多个并行Case争读同一stdin。

## tool.metrics · 对已经取得的目标矩阵做帕累托分析

**什么时候用：** 离线分析明确的最小化目标矩阵；不修改Pool成员、不进行硬可行性准入。pareto_filter返回目标行，不返回原候选索引或SolutionRef，不能据数值相等回推候选身份。

**先准备什么：** NumPy和当前nsgablack。以下显式二维目标是输入示例；实际使用时从已验证的本轮结果/反馈中取raw或selection之一，并在报告标明。可行性需先按原始违反量筛选。

**放在哪：** 独立Project根 analyse_objectives.py；不是Adapter的选择实现。若需要从Pool选最终精英，应使用有引用身份的chosen回调，不能将本函数返回的裸F当解。

**接入步骤：** 完整脚本：

```python
import json
import numpy as np
from nsgablack.utils.analysis import pareto_filter, hypervolume_2d


def main():
    F = np.array([[1., 4.], [2., 2.], [4., 1.], [3., 3.]])
    V = np.array([0., 0., 0., 0.])
    feasible = np.isfinite(F).all(axis=1) & np.isfinite(V) & (V <= 0.)
    front = pareto_filter(F[feasible])
    hv = hypervolume_2d(front, reference_point=np.array([5., 5.]))
    if front.shape != (3, 2) or not np.isclose(hv, 11.):
        raise ValueError("unexpected example geometry")
    print(json.dumps(dict(view="explicit_minimization_input", front=front.tolist(), hv=hv)))


if __name__ == "__main__":
    main()
```

**怎样判断接对：** 去掉被支配的[3,3]，三点保留；相对固定[5,5]的二维HV为11。最大化目标须先统一方向；参考点应固定且在所比较前沿之外，不能每次用不同自动参考点比较进步。NaN/inf先排除，本函数不替你做数据审计。

**运行入口：** `python analyse_objectives.py`。没有Problem求值或优化结果生成。

### 变体：排除一个不可行点

**目的：** 明确可行性发生在帕累托工具之前。**改在哪里：** V换为`[0., 2., 0., 0.]`，检查条件换成如下：

```python
if front.shape != (3, 2) or not np.isclose(hv, 8.):
    raise ValueError("unexpected feasible-only front")
```

**行为变化：** [2,2]被原始违反量排除，[3,3]不再被它支配，前沿为[1,4]/[4,1]/[3,3]。**限制：** Bias软化V不能代替这里的raw可行性；HV数值变化不代表同一可行域内算法优劣。

## tool.catalog_curate · 已有AI说明的幂等检查与离线维护

**什么时候用：** curate_packets是可注入generator/store的说明发布器，会按key+source_digest+model+prompt_version检查缓存；它不是“打开目录就自动完善”。当前需求禁止付费调用，因此主例只使用真实已导出的缓存，缺失时在调度前停止，不生成或伪造任何说明。

**先准备什么：** 已有且有来源的knowledge packet文件、对应index、当前examples索引，以及已有AI记录导出JSON。用build子命令可离线构建来源，run子命令会调用配置的模型，当前不执行。模型名必须填导出记录真实model，不用“offline”冒充审核身份。

**放在哪：** 三仓已安装的维护目录保存check_cached_notes.py；它不是Case/Plugin，不修改Catalog事实或AI数据库。文件参数只读，输出是缓存覆盖检查。

**接入步骤：** 完整脚本如下；记录不足时不会进入curate_packets，更不会把错误转成成功。

```python
import argparse
import json
from pathlib import Path
from nsgablack.catalog.curate import load_packets, curate_packets, PROMPT_VERSION


class ExistingNotes:
    def __init__(self, records):
        self.records = records

    def get(self, key, source_digest, *, model, prompt_version):
        return next((r for r in self.records if r["entry_key"] == key
            and r["source_digest"] == source_digest and r["model"] == model
            and r["prompt_version"] == prompt_version), None)

    def put(self, record):
        raise RuntimeError("this maintenance adapter is read-only")


class RefuseGeneration:
    def generate(self, packet):
        raise RuntimeError("model generation disabled by the user")


def main():
    parser = argparse.ArgumentParser()
    for name in ("packets", "index", "records", "model", "key"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    packets = load_packets(Path(args.packets), index_path=Path(args.index))
    records = json.loads(Path(args.records).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("supply a JSON list of actual exported knowledge records")
    store = ExistingNotes(records)
    packet = packets[args.key]
    if store.get(args.key, packet["source_digest"], model=args.model,
                 prompt_version=PROMPT_VERSION) is None:
        raise ValueError("no matching cached note; nothing was generated or written")
    report = curate_packets({args.key: packet}, store, RefuseGeneration(),
        model=args.model, limit=1, workers=1, keys=(args.key,))
    if not report["ok"] or report["generated"] != 0 or report["cached"] != 1:
        raise ValueError("unexpected cached-only maintenance result")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

curate_packets本身并不是网络隔离器；这里的注入对象明确拒绝生成并先核对缓存。新的来源摘要、不同模型/提示版本会缓存失配，不能伪改digest把旧说明标为最新。packet证据、手写完整教程、AI独立审核、真实运行验证分别统计。

**怎样判断接对：** 真正匹配记录时cached=1/generated=0/pending=0；不匹配就明确报错。没有凭空补一项教程，也不会增加AI整理计数。要补手写教程，编辑来源文档/显式manifest，再构建examples索引；不能给未经审核的文字添AI审核通过标签。

**运行入口：** `python check_cached_notes.py --packets packets.json --index sources.json --records exported-records.json --model <记录中的真实模型名> --key adapter.nsga2`。尖括号处必须实际替换；没有对应文件就先不执行。

### 变体：只规划缺口，不需要AI记录或generator

**目的：** 完全离线查看当前examples索引还有哪些字段缺失。**改在哪里：** 新建独立plan_material.py如下，输入路径由命令行给出。

```python
import argparse
from nsgablack.catalog.material_plan import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("index")
    parser.add_argument("output")
    args = parser.parse_args()
    raise SystemExit(main(["--input", args.index, "--output", args.output]))
```

**行为变化：** `python plan_material.py examples.json plan.json`只读本地索引并生成缺口清单。**限制：** 完整字段/AST通过只说明资料质量，不证明Case跑过，更不算AI审核。
