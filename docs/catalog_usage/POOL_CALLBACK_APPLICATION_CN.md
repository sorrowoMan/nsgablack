# 一次变化交付两个孩子，再用最终成员维护历史精英

本页共享主例对应六个真实组件：`tool.change_request`、`tool.change_result`、`tool.change_batch_result`、`tool.pool_output`、`tool.pool_edit`、`tool.pool_maintenance_request`。它们处在同一条正式数据流的不同位置，不需要为每个类型另建运行器。以下只做源码与装配说明，没有运行改装后的算法或生成运行收据。

## tool.change_request · 完整提案与成员档案回调链

**什么时候用：** 自定义双孩子交叉，保存已接纳提案，再以历代最终成员维护精英档案；生成、生存选择、归档分开，不重复求值。

**先准备什么：** 复制完整 `examples/cases/pool_workflow_pilot` Project，依赖当前 nsgablack、blackbase、NumPy。

TwoCenters 候选 `(2,)`，双目标为到 `(-1,0)/(1,0)` 的平方距离；反馈 `(n,2)`、违反量 `(n,)`。Pipeline 为 UniformInitializer/ClipRepair，范围 `[-2,2]`。保留 seed=37、source_count=8、population_size=6、offspring_size=4、max_steps=10；源数、容量、后继预算不同。

PipelineSource 先生成未评估种子、reference 与空 elite，不建 Unit。Router 取六个输入，送评后建立成员。后续 request.parents 是 NSGA2 的父代 `(2,2)`，source_refs 对齐；同一父成员可选两次，不去重。rng 来自所属 Adapter。

**放在哪：** 新建 `cases/ga_search/adapter/pool_callbacks.py`，复用原 workflow.py。替换同 Case 的 build_solver.py，在 project_config.py 末尾追加 ga 分组，其它文件保留。

**接入步骤：** 新工厂绑定 maintain_archive；旧 archive_source 只控制原 workflow 工厂，不切换本节绑定。

`cases/ga_search/adapter/pool_callbacks.py` 完整内容：

```python
from functools import partial
import numpy as np
from nsgablack.adapters import (
    ChangeRequest, ChangeResult, ChangeBatchResult, PoolOutput, PoolEdit,
    PoolMaintenanceRequest, NSGA2Adapter, StrategyRouterAdapter,
    MultiStrategyConfig, RoleSpec, PoolTaskSpec,
)
from .workflow import choose_survivors, elite_key


def paired_change(request: ChangeRequest, *, rng) -> ChangeBatchResult:
    if len(request.parents) != 2 or len(request.source_refs) != 2:
        raise ValueError("this GA change needs two exactly identified parents")
    a, b = request.parents
    mask = rng.random(a.shape) < 0.5
    children = (np.where(mask, a, b), np.where(mask, b, a))
    return ChangeBatchResult(results=tuple(
        ChangeResult(
            child + rng.normal(0.0, 0.1, child.shape),
            source_refs=request.source_refs,
            outputs=(PoolOutput("ga_trials", create=True),),
        )
        for child in children[:request.max_outputs]
    ))


def maintain_archive(request: PoolMaintenanceRequest, *, rng) -> tuple[PoolEdit]:
    del rng
    if request.members is None:
        raise ValueError("this archive requires the owning GA's final members")
    old = request.pool.subpool("elite")
    incoming = request.members
    kept = old.merge(incoming).top(20, key=elite_key)
    return (request.pool.replace_members("elite", kept.refs),)


def build_adapter(settings):
    ga = NSGA2Adapter(name="ga", population_size=settings.population_size,
                     offspring_size=settings.offspring_size, change=paired_change)
    ga.set_selector(partial(choose_survivors, count=settings.population_size))
    ga.set_pool_maintenance(maintain_archive)
    return StrategyRouterAdapter(name="ga_workflow", roles=[
        RoleSpec("search", ga, pool_task=PoolTaskSpec(
            mode="initialize", count=settings.population_size,
            shuffle=False, change_sources=("elite",),
        )),
    ], config=MultiStrategyConfig(
        total_batch_size=max(settings.population_size, settings.offspring_size),
        adapt_weights=False,
    ))
```

mask 产生互补草稿再各加噪声。批结果保留孩子顺序，每项是单个 ChangeResult，矩阵不自动视为批返回。max_outputs 是剩余名额，先切片；NSGA2 继续调用直到满足 offspring_size 或返回空批。

控制面派生孩子 token，source_refs 声明父代版本。context 不自动含 pool；`request.pool` 只在调用内有效，不缓存活对象供回调后读取。

Solver 负责预算、repair、求值与硬接纳。PoolOutput 只声明目的地；接纳提案的已评估版本提交后才加入 ga_trials。create=True 不立即建池，拒绝/回滚不发布。

choose_survivors 按约束支配和拥挤度选位置。成员选择后 maintenance 每个叶 update 调一次，含首次基准。members 是本 NSGA2 有序最终成员；accepted 是本叶本批硬接纳提案。轨迹算法 members 可为 None，本函数拒绝。

elite_key 以 raw_feedback 按“是否违反、正违反量、原始目标和”排序；档案规则不改 Pareto 生存选择或 raw。merge 按精确 SolutionRef 去重，不按坐标。

replace_members 返回冻结 descriptor 的 PoolEdit，不立即写成员。elite 已建，无需 create=True；`change_sources=("elite",)` 授权读取/替换，须保留。计划与 Unit/输出同一步提交；漂移/冲突拒绝，回滚不退求值费用。

`cases/ga_search/build_solver.py` 完整内容：

```python
from nsgablack.core import ComposableSolver
from nsgablack.plugins import ParetoArchivePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter.pool_callbacks import build_adapter
from .config import CaseConfig
from .pipeline import build_pipeline
from .plugins import PipelineSource, WorkflowTrace
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = CaseConfig(**dict(config or {}))
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(PipelineSource(settings.source_count))
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(WorkflowTrace(case_name="ga_search", max_steps=settings.max_steps))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

在原 project_config.py 的 STAGES/GROUPS 后追加一次，保留 L0 与其它分组。

```python
STAGES.append({
    "name": "ga_only", "cases": ["ga_search"], "policy": "serial",
    "resource_requests": {
        "ga_search": {"threads": 1, "gpus": 0, "backend": "local"},
    },
})
GROUPS["ga"] = {"stages": ["ga_only"]}
```

**怎样判断接对：** 先看本次 Project 终态，再读 WorkflowTrace 的 `results/ga_search.json` 核对 run_id；旧文件不会因失败消失，不替代权威 receipt。

- `initial.initial_refs` 是未评估种子；initial.unit_exists 仍应 False，8个种子不等于8次求值。
- `records[].steps/evaluations/accepted_count` 是提交进度、累计求值与接纳历史量，不是回调次数。
- `result.refs/candidates/raw_objectives/raw_violations/provenance` 是对齐的最终成员；正常完整预算下容量6，raw 目标符合 TwoCenters 公式。
- `change_output.name/refs/provenance` 是 ga_trials 的已接纳后代，不含初始化。provenance 的 `metadata.change_source_refs` 有两条父代来源，`metadata.change_outputs.proposal_token` 对应输出 candidate_token；坐标可同，token 独立。
- `final.elite.refs/descriptor`、`records[].elite` 是旧档案加最终成员取 raw 前20。历史精英可已离开 Unit；view_id 保持，revision 随成员变化。
- `accepted.refs/raw_objectives/raw_violations` 是全运行接纳历史，可含被淘汰后代，不是最终成员。

四类集合范围不同；elite 也不是 ParetoArchivePlugin 的前沿或 Solver incumbent。

**运行入口：** 仓库根目录运行新增 ga 组。

```powershell
python examples/cases/pool_workflow_pilot/run_project.py --group ga
```

原 default、run_and_report.py 固定三 Case，后者按 accepted 归档校验，不适用本页。保留10步；若仅首步初始化，ga_trials 未建，原观察器可能读取失败。

### 变体一：把被生存选择淘汰的已接纳试探也纳入精英竞争

**目的：** 让硬接纳但未留存的试探也竞争档案。

**改在哪里：** 完整替换 maintain_archive，保留其它代码，不只改旧 archive_source。

```python
def maintain_archive(request: PoolMaintenanceRequest, *, rng) -> tuple[PoolEdit]:
    del rng
    old = request.pool.subpool("elite")
    incoming = request.accepted
    kept = old.merge(incoming).top(20, key=elite_key)
    return (request.pool.replace_members("elite", kept.refs),)
```

**行为变化：** 输入改为旧 elite + 本批 accepted，淘汰孩子也竞争前20；按 accepted 增量解释 records[].elite，最终成员仍由 NSGA2 选择，不扩读 pending。

**限制：** 硬接纳不保证改进，elite 会裁剪；替换不删除 main/ga_trials 历史。比较前保存两次 ga_search.json。

### 变体二：每次父代配对只交付一个孩子

**目的：** 每个孩子重新抽父代，减少相关性。

**改在哪里：** 从基线替换 paired_change，其它代码与 offspring_size 保留。

```python
def paired_change(request: ChangeRequest, *, rng):
    if len(request.parents) != 2 or len(request.source_refs) != 2:
        raise ValueError("this GA change needs two exactly identified parents")
    if request.max_outputs == 0:
        return ChangeBatchResult()
    a, b = request.parents
    child = np.where(rng.random(a.shape) < 0.5, a, b)
    return ChangeResult(
        child + rng.normal(0.0, 0.1, child.shape),
        source_refs=request.source_refs,
        outputs=(PoolOutput("ga_trials", create=True),),
    )
```

**行为变化：** NSGA2 支持单个 ChangeResult，会再取父代补后继预算；offspring_size=4 不变成每轮1个，原评估/输出/归档保留。

**限制：** RNG 消耗改变，同 seed 不保证同轨迹；VNS 等单候选消费者不据此获得批返回支持。

来源：[请求/来源](../../adapters/change.py)、[返回/输出/编辑/Pool](../../adapters/change_pool.py)、[批消费](../../adapters/change_batch.py)、[维护请求](../../adapters/pool_maintenance.py)、[复用的真实选择规则](../../examples/cases/pool_workflow_pilot/cases/ga_search/adapter/workflow.py)、[报告字段与发布时点](../../examples/cases/pool_workflow_pilot/workflow_trace.py)。
