# 搜索组合Adapter：同一候选语义，不同的调度与交接

这是五套可独立应用的Case配方，均沿现有正式Project/L0入口。所有代码按源码核对，未运行算法、模型、服务或试验。事件队列、角色包装、精英注入、池准备恢复和逐起点任务分别说明；它们不是五种名字指向同一种自动融合。

## orchestration.host · 共用的完整正式Case与结果观察

完整复制 `nsgablack/examples/cases/catalog_recipes` Project，保留project_config.py默认stage_1/composite、run_project.py、Case规范入口与包。原Project L0拥有资源分配，Case只消费resource_context。下文路径相对 `cases/composite/`，每种recipe只使用一份独立副本。

新增 `problem/orchestration_problem.py`，目标有一个明确的平坦区，便于观察停滞恢复；不以随机效果证明任何算法优越性：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class Plateau(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="orchestration_plateau", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["cost"])

    def evaluate(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return [max(0., float(x @ x) - 1.)]

    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return np.maximum(-2. - x, 0.) + np.maximum(x - 2., 0.)
```

新增 `pipeline/orchestration_pipeline.py`。叶Adapter如需另配initializer/mutator，会在自己工厂显式声明；默认问题修复只在正式候选路径执行。

```python
from nsgablack.representation import (RepresentationPipeline,
    UniformInitializer, GaussianMutation, ClipRepair)


def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(-.15, .15),
        mutator=GaussianMutation(sigma=.08), repair=ClipRepair(-2., 2.))
```

新增 `plugins/orchestration_report.py`，工厂保留真实owner对象，不按类型名寻找“唯一种群”。报告只读，不调用ensure_unit、不发新提案。

```python
import math
import numpy as np
from nsgablack.plugins.base import Plugin
from nsgablack.adapters import StrategyOrigin
from nsgablack.utils.engineering.file_io import atomic_write_json


def json_data(value):
    if isinstance(value, np.ndarray):
        return json_data(value.tolist())
    if isinstance(value, np.generic):
        return json_data(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): json_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_data(v) for v in value]
    return value


class OrchestrationReport(Plugin):
    def __init__(self, root, owners, output):
        super().__init__(name="orchestration_report")
        self.root, self.owners, self.output = root, owners, output
        self.records = []

    def observe(self):
        control, pool = self.solver, self.solver.solution_pool
        owners = {}
        for name, owner in self.owners.items():
            refs = tuple(owner.get_population_solution_refs(control) or ())
            row = {"unit_exists": getattr(owner, "algorithm_unit", None) is not None,
                "refs": [ref.as_dict() for ref in refs]}
            if refs:
                f, v = pool.read_raw_feedback(refs)
                row.update(candidates=control.read_solutions(refs).numeric_matrix.tolist(),
                    raw_objectives=f.tolist(), raw_violations=v.tolist())
            owners[name] = row
        tasks = []
        for unit in getattr(self.root, "units", ()):
            worker = unit.adapter
            status = getattr(worker, "task_status", None)
            if status is not None:
                item = {"role": unit.role, "unit_id": unit.unit_id, "status": status}
                if status.get("status") == "done":
                    selected = tuple(worker.get_pool_task_results(control))
                    item["final_refs"] = [r.as_dict() for r in selected]
                    item["final_origins"] = [[o.as_dict() for o in StrategyOrigin.from_candidate(s)]
                        for s in control.read_solutions(selected).semantic_states] if selected else []
                tasks.append(item)
        hub = control.get_plugin("async_event_hub")
        return json_data({"generation": int(control.generation),
            "pool_sequence": pool.timestamp.sequence, "pool_records": pool.record_count,
            "owners": owners, "tasks": tasks,
            "phase": getattr(self.root, "phase", None),
            "runtime": dict(self.root.get_runtime_context_projection(control) or {}),
            "hub": None if hub is None else hub.get_report()})

    def on_generation_committed(self, generation, outcome):
        if not outcome.get("committed"):
            raise ValueError("this observation requires a committed step")
        self.records.append(self.observe())

    def on_solver_finish(self, result):
        state = self.root.get_state()
        self.payload = {"run_id": self.solver.run_session.run_id,
            "records": self.records, "final": self.observe(),
            "elite_archive": json_data(state.get("archive", []))}

    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

空refs仅表示此owner没有L2成员，不表示其轨迹为空。对轨迹算法看runtime的current/best字段；有序种群读实际owner的成员引用，不把根accepted历史当成员。json_data将观察里的非有限占位显示null，绝不改原始反馈或把未评估点变成已评估点。

完整替换 `build_solver.py`。下文各recipe给出整个adapter/composition.py，并统一返回 `(root, owners, extras)`；extras是明确需要挂载的插件。

```python
from pathlib import Path
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.project import apply_solver_component_overrides
from .adapter.composition import build_bundle, MAX_STEPS
from .pipeline.orchestration_pipeline import build_pipeline
from .plugins.orchestration_report import OrchestrationReport
from .problem.orchestration_problem import Plateau


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit this recipe's explicit composition")
    root, owners, extras = build_bundle()
    solver = ComposableSolver(problem=Plateau(), representation_pipeline=build_pipeline(),
        adapter=root, resource_context=resource_context,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(MAX_STEPS)
    solver.set_max_step_attempts(MAX_STEPS * 4)
    for plugin in extras:
        solver.add_plugin(plugin)
    solver.add_plugin(OrchestrationReport(root, owners,
        Path(__file__).resolve().parents[2] / "results" / "orchestration.json"))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

普通运行不保证这些观察记录可在中途checkpoint后拼成完整历史；核心Adapter/池事务仍有自己的恢复状态。本例没有给仅观察的records宣称额外checkpoint承诺。正式运行入口为副本根 `python run_project.py --check --build-check`，随后 `python run_project.py`；本轮没有执行。确认本次Case成功与run_id再看results/orchestration.json，旧结果文件不会因失败自动清除。

## orchestration.roles_events · 角色全派发与事件配额两种实际组合

**什么时候用：** 一个Case中有独立种群与局部轨迹，想统一送评并将结果还给原所有者。角色控制器每次调用所有角色；事件控制器按队列机会调用子算法，二者调度含义不同。

**先准备什么：** 完成本书host。候选都是同一个Plateau问题的二维数值点；每个算法实例拥有自己的Unit，不能把它们合并成矩阵。NSGA容量4/后代2，VNS每步最多2候选；这些数值都不是池的容量。

**放在哪：** 完整替换 `adapter/composition.py`。

**接入步骤：**

```python
from nsgablack.adapters import (NSGA2Adapter, VNSAdapter, VNSConfig, RoleAdapter,
    MultiRoleControllerAdapter, AsyncEventDrivenAdapter, AsyncEventDrivenConfig,
    EventStrategySpec, EventCaseSpec)
from nsgablack.plugins import AsyncEventHubPlugin, AsyncEventHubConfig
from nsgablack.representation import GaussianMutation, ContextGaussianMutation

MODE = "roles"
LOCAL_CAP = 2
MAX_STEPS = 8


def local_phase(context):
    return int(context["generation"]) >= 4


def build_bundle():
    ga = NSGA2Adapter(name="population", population_size=4, offspring_size=2,
        crossover_rate=0., mutator=GaussianMutation(sigma=.12))
    vns = VNSAdapter(VNSConfig(batch_size=2, k_max=2, base_sigma=.06,
        restart_on_stagnation=False), name="local",
        mutator=ContextGaussianMutation(base_sigma=.06))
    if MODE == "roles":
        root = MultiRoleControllerAdapter([
            RoleAdapter("population_role", ga, name="global_role", max_candidates=2),
            RoleAdapter("local_role", vns, name="local_role", max_candidates=LOCAL_CAP)])
        extras = []
    else:
        if MODE == "events":
            specs = [EventStrategySpec(ga, "population", weight=1.),
                EventStrategySpec(vns, "local", weight=1.)]
        elif MODE == "event_cases":
            specs = [EventCaseSpec(ga, "population", priority=0),
                EventCaseSpec(vns, "local", when=local_phase, priority=10)]
        else:
            raise ValueError("unknown orchestration mode")
        root = AsyncEventDrivenAdapter(specs, config=AsyncEventDrivenConfig(
            total_batch_size=4, target_queue_size=4, bootstrap_events_per_strategy=2,
            max_queue_size=32, max_archive_size=16, max_event_history=64))
        extras = [AsyncEventHubPlugin(AsyncEventHubConfig(mode="async",
            commit_policy="generation_end", max_pending=128))]
    return root, {"population": ga, "local": vns}, extras
```

RoleAdapter加入role信息与本地候选上限，并在repair/disposition中组合索引映射，不能先丢pending再调用update。初始化输入有池游标时不使用此本地cap裁掉输入；本例没有PoolTask。MultiRoleControllerAdapter是RoleRouterAdapter的具名子类，不是RoleSpec/n_units的多实例Router；需要逐起点任务请用下一节。

Async的“异步”是事件级调度；没有自动启动线程或跨Case并行。total_batch_size限制调度的队列事件数量，再按某子策略累计预算裁剪其一次提案；不是保证本步恰好有4次求值。子策略本来提案较少、预算截断或raw准入都可使数量减少。事件archive是调度记录，不能当真实成员、Pareto档案或最优候选交付。

Hub由Async内部_log_event明确调用record_event。尝试内事件等最终committed才进入提交队列；非提交事件留在noncommitted审计。commit_policy的历史名字generation_end实际在on_step_attempt_end收尾后commit。get_committed_context返回Hub重放的观察副本，不直接把这些事件写回Solver共享ContextStore，也不能反向成为调度权威。Hub队列/审计是有界观察，不是求值证据日志或持久恢复协议；开启Hub不是算法正确性的前提。

**怎样判断接对：** 报告owners.population.refs/candidates/raw_objectives同序；local的Unit与runtime轨迹分开。roles模式runtime有candidate_roles/role_reports；events模式event_shared.stats的proposed/completed和event_history解释哪个子算法收到机会。Hub report的committed/noncommitted是事件数量，不是成功generation数。组合人口authority是分区，不能读取一份根population代替两算法的结构。

**运行入口：** 使用host的两条标准命令；8是逻辑提交上限，物理尝试上限32，未运行本例。

### 变体一：把本地角色每次最多送评两点改成一点

**目的：** 只改变局部提案配额，保留同一个VNS实例。

**改在哪里：** 保留MODE=roles，只替换常量：

```python
LOCAL_CAP = 1
```

**行为变化：** VNS原提案仍经过正式disposition压缩，只消费最后获准的一行反馈。**限制：** 这不是把batch_size永久改1，也不更改另一角色的配额；最大值不是保证接纳量。

### 变体二：用规则事件路由代替每次都调用两个角色

**目的：** 前4个已提交逻辑步使用GA，随后主要使用VNS，而非手写循环取模。

**改在哪里：** 同一文件只替换MODE。

```python
MODE = "event_cases"
```

**行为变化：** 高priority且when命中的local成为当前case；进入时清空不属于当前case的旧调度队列。**限制：** 这只是调用时机切换，没有GA候选到VNS的池交接；VNS从本Case管线独立初始化。若要精修GA成员，须显式PoolTask。无case命中时实现可保留当前或选首个enabled，不是“没有命中就停止”。不要把它当严格停止门。

源码：adapters/role_adapters/adapter.py、async_event_driven/adapter.py、plugins/system/async_event_hub.py。

## orchestration.elite · 精英派生在原步骤送评之前发生

**什么时候用：** 需要从已评估历史精英产生少量新提案，并让它们经历同一repair/评估/接纳/提交，而不是代提交后再偷偷写种群。

**先准备什么：** 完整host。选择可被替换提案的NSGA2；A*、整批CMA或有结构约束的候选不能只套同一个wrapper就认定有效。构造与setup会检查inner.can_replace_proposals。

**放在哪：** 完整替换 `adapter/composition.py`。报告中的elite_archive来自真实wrapper状态，population仍由inner拥有。

**接入步骤：**

```python
from nsgablack.adapters import NSGA2Adapter, EliteRetentionAdapter, EliteRetentionConfig
from nsgablack.representation import GaussianMutation

RETENTION_RATIO = .5
MAX_STEPS = 8


def build_bundle():
    ga = NSGA2Adapter(name="population", population_size=6, offspring_size=4,
        crossover_rate=0., mutator=GaussianMutation(sigma=.08))
    wrapper = EliteRetentionAdapter(ga, EliteRetentionConfig(
        retention_probability=1., retention_ratio=RETENTION_RATIO,
        history_size=4, mutation_scale=.01), name="elite_search")
    return wrapper, {"population": ga}, []
```

已接纳行进入wrapper有限archive，按选择违反量/目标和排序保留4项。后续propose把本批最后ceil(batch*ratio)行替换成精英派生候选；archive抽取允许重复，但新提案有新身份，保留精确父版本provenance。它不是“保留原种群中的4个精英槽位”，也不是把过去反馈复制给新候选。池输入尚未消费时不注入替换，避免破坏初始化输入游标。

正常Solver有mutate_candidate，wrapper实际调用inner.mutate_candidate；这里消耗绑定的GaussianMutation(.08)。EliteRetentionConfig.mutation_scale仅用于缺少该控制接口时的后备数值分支，不能把.01写成当前案例真正采用的扰动尺度。archive比较默认目标和，不自动复用MOEA/D每个方向的投影；本例单目标避免该歧义。

**怎样判断接对：** elite_archive每项有candidate/objectives/violation/score/solution_ref；refs指向已评估父版本。owners.population是真实NSGA成员，可能和archive不相同。新派生行照常占求值次数；小概率/小历史/有限8步不保证增加目标改善。Wrapper、inner和池各有自己的步骤/恢复状态，不能手工把inner的checkpoint再重复塞进父步骤快照。

**运行入口：** 使用host标准入口与orchestration.json，核对同一run_id。没有本轮运行证明。

### 变体一：保留归档观察，关闭精英替换

**目的：** 隔离派生注入的影响，而非把历史记录也清除。

**改在哪里：** 同factory文件只改常量。

```python
RETENTION_RATIO = 0.
```

**行为变化：** update仍建立有限archive，propose不替换inner候选。**限制：** Wrapper仍在装配树中，报告归档存在不意味着发生过注入。

## migration.plugin.elite · 旧Plugin只是装配桥

**什么时候用：** 迁移仍add_plugin(BasicElitePlugin(...))的旧工程。本文新配方不挂载旧Plugin。

**先准备什么：** 了解utils/compat/elite_retention.py：Basic/Historical插件发出废弃警告，在attach或init时用EliteRetentionAdapter包住当前Adapter；并不是另一个后处理保留算法。

**放在哪：** 删除build_solver里的旧BasicElitePlugin/HistoricalElitePlugin挂载与import；在adapter/composition.py构造上节wrapper，builder只装配这一个root。

**接入步骤：** Basic的retention_prob/retention_ratio映射到retention_probability/retention_ratio，history_size=1；Historical的replacement_prob/replacement_ratio/history_size映射到同一Config的对应字段。保持inner名称、实际mutator与Project grant；不要同时装桥和wrapper造成双层派生。

**怎样判断接对：** root类型是EliteRetentionAdapter，plugin列表没有旧elite桥；archive和population按上节报告观察。桥的旧hook路径不应作为新项目最佳实践，旧类未装配也未在本轮执行。

**运行入口：** 迁移后的完整host入口与上节相同；需要旧工程兼容性时另做明确验证，不把本迁移材料计为旧Plugin已验证。

### 变体一：把单精英改成四项历史精英

**目的：** 迁移Historical意图而不引入第二个Plugin。

**改在哪里：** 使用上节完整工厂的history_size=4，retention_probability=1、ratio=.5保持独立可见。

**行为变化：** archive最多4个已评估父版本，抽取可重复；不是复制四份Unit。**限制：** history_size是历史候选条数，不是保留代数，也不保证四个不同数值位置。
