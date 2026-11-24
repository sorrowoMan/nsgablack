"""正式组合 Adapter 与独立普通循环的配对，没有第二个运行入口。

所有 multi 只表示同一步合并提案，孩子算法仍由一个 Solver 顺序执行。
真正跨 Case 并行与资源授权由标准 Project 负责。本模块的裸编排不调用
框架组合器、ExecutionPlan/ExecutionCursor 或组合器 checkpoint 状态。
"""
from __future__ import annotations

from functools import partial
import numpy as np

from benchmarks.transparency_trajectory import (
    TrajectoryReference, make_trajectory_adapter, make_trajectory_problem, trajectory_state,
)


COMPOSITION_NAMES = (
    "composite", "strategy_chain", "strategy_router", "role_adapter", "role_router",
    "search_plan_serial", "search_plan_multi", "search_plan_nested",
)
WRAPPER_NAMES = ("elite_retention", "pool_task", "pool_search")
LEAVES = ("sa", "gaussian_search")


def _leaf_adapters(seed):
    # Explicit child algorithm seeds are stable under nesting and scheduling.
    return {name: make_trajectory_adapter(name, int(seed) + 101 * index)
            for index, name in enumerate(LEAVES)}


def make_composition_adapter(seed, *, kind):
    from nsgablack.adapters import CompositeAdapter
    from nsgablack.adapters.multi_strategy import StrategyRouterAdapter, StrategySpec, MultiStrategyConfig
    from nsgablack.adapters.serial_strategy import StrategyChainAdapter, SerialPhaseSpec, SerialStrategyConfig
    from nsgablack.adapters.role_adapters import RoleAdapter, RoleRouterAdapter
    from nsgablack.adapters.search_plan import SearchPlanAdapter, stage, serial, multi, repeat

    leaves = _leaf_adapters(seed)
    if kind == "composite":
        return CompositeAdapter(list(leaves.values()))
    if kind == "role_adapter":
        return RoleAdapter("anneal", leaves["sa"])
    if kind == "role_router":
        return RoleRouterAdapter([RoleAdapter("anneal", leaves["sa"]),
                                  RoleAdapter("sample", leaves["gaussian_search"])])
    if kind == "strategy_chain":
        return StrategyChainAdapter([SerialPhaseSpec("anneal", leaves["sa"], steps=2),
                                     SerialPhaseSpec("sample", leaves["gaussian_search"], steps=4)],
                                    config=SerialStrategyConfig(repeat_last=False))
    strategies = [StrategySpec(adapter=adapter, name=name) for name, adapter in leaves.items()]
    config = MultiStrategyConfig(total_batch_size=8, adapt_weights=False, phase_schedule=(("explore", -1),),
                                seeds_per_task=0)
    if kind == "strategy_router":
        return StrategyRouterAdapter(strategies=strategies, config=config)
    if kind == "search_plan_serial":
        plan = serial(stage("sa", steps=2, label="anneal"), stage("gaussian_search", steps=2, label="sample"))
    elif kind == "search_plan_multi":
        plan = multi(stage("sa", steps=3, label="anneal"), stage("gaussian_search", steps=2, label="sample"))
    elif kind == "search_plan_nested":
        plan = repeat(times=2, body=serial(
            multi(stage("sa", steps=2, label="joint_sa"), stage("gaussian_search", steps=1, label="joint_sample")),
            stage("gaussian_search", steps=1, label="solo_sample")))
    else:
        raise ValueError(f"unknown composition fixture: {kind}")
    return SearchPlanAdapter(plan, strategies, config=config, name=kind)


def _framework_leaves(adapter):
    from nsgablack.adapters import CompositeAdapter
    from nsgablack.adapters.multi_strategy import StrategyRouterAdapter
    from nsgablack.adapters.serial_strategy import StrategyChainAdapter
    from nsgablack.adapters.role_adapters import RoleAdapter, RoleRouterAdapter

    if isinstance(adapter, RoleRouterAdapter):
        return {role.inner.name: role.inner for role in adapter.roles}
    if isinstance(adapter, RoleAdapter):
        return {adapter.inner.name: adapter.inner}
    if isinstance(adapter, StrategyRouterAdapter):
        return {unit.adapter.name: unit.adapter for unit in adapter.units}
    if isinstance(adapter, StrategyChainAdapter):
        return {child.name: child for child in adapter._adapters}
    if isinstance(adapter, CompositeAdapter):
        return {child.name: child for child in adapter.adapters}
    raise TypeError("unsupported composition fixture")


def project_composition(solver, *, kind):
    adapter = solver.adapter
    result = {"children": {name: trajectory_state(name, child, solver)
                            for name, child in _framework_leaves(adapter).items()}}
    if kind == "composite":
        scheduler = {"kind": kind, "last_counts": {child.name: end - start
                     for child, start, end in adapter._last_ranges}}
    elif kind == "role_adapter":
        scheduler = {"kind": kind, "role": adapter.role}
    elif kind == "role_router":
        scheduler = {"kind": kind, "candidate_roles": list(adapter.last_candidate_roles)}
    elif kind == "strategy_chain":
        scheduler = {"kind": kind, "index": adapter._current_idx,
                     "local_updates": adapter._step_in_phase, "completed": adapter._schedule_completed}
    elif kind == "strategy_router":
        scheduler = {"kind": kind, "updates": adapter._step,
                     "allocations": {role: end - start for role, uid, start, end in adapter._last_allocations}}
    else:
        scheduler = {"kind": kind, "updates": adapter._step, "completed": adapter.cursor.completed,
                     "active": [{"name": item.name, "label": item.label, "count": item.count, "steps": item.steps}
                                for item in adapter.cursor.active()]}
    result["scheduler"] = scheduler
    return result


def _plan_timeline(kind):
    """Independent finite activation table; no shared framework cursor logic."""
    if kind == "search_plan_serial":
        return [[("sa", "anneal", 0, 2)], [("sa", "anneal", 1, 2)],
                [("gaussian_search", "sample", 0, 2)], [("gaussian_search", "sample", 1, 2)]]
    if kind == "search_plan_multi":
        return [[("sa", "anneal", 0, 3), ("gaussian_search", "sample", 0, 2)],
                [("sa", "anneal", 1, 3), ("gaussian_search", "sample", 1, 2)],
                [("sa", "anneal", 2, 3)]]
    if kind == "search_plan_nested":
        one_cycle = [[("sa", "joint_sa", 0, 2), ("gaussian_search", "joint_sample", 0, 1)],
                     [("sa", "joint_sa", 1, 2)], [("gaussian_search", "solo_sample", 0, 1)]]
        return one_cycle + one_cycle
    return None


class CompositionReference:
    def __init__(self, kind, seed, evaluate):
        if kind not in COMPOSITION_NAMES:
            raise ValueError(f"unknown composition fixture: {kind}")
        self.kind, self.updates = kind, 0
        names = ("sa",) if kind == "role_adapter" else LEAVES
        self.children = {name: TrajectoryReference(name, int(seed) + 101 * LEAVES.index(name), evaluate=evaluate)
                         for name in names}
        self.timeline = _plan_timeline(kind)
        self.last_counts = {}

    def active(self):
        if self.timeline is not None:
            return [item[0] for item in self.timeline[self.updates]] if self.updates < len(self.timeline) else []
        if self.kind == "strategy_chain":
            return ["sa" if self.updates < 2 else "gaussian_search"] if self.updates < 6 else []
        return list(self.children)

    def step(self):
        batches = [self.children[name].step() for name in self.active()]
        self.last_counts = {name: len(batch["candidates"]) for name, batch in zip(self.active(), batches)}
        self.updates += 1
        return {"candidates": [row for batch in batches for row in batch["candidates"]],
                "objectives": [row for batch in batches for row in batch["objectives"]],
                "violations": [row for batch in batches for row in batch["violations"]], "state": self.state()}

    def state(self):
        kind = self.kind
        if kind == "composite":
            scheduler = {"kind": kind, "last_counts": dict(self.last_counts)}
        elif kind == "role_adapter":
            scheduler = {"kind": kind, "role": "anneal"}
        elif kind == "role_router":
            scheduler = {"kind": kind, "candidate_roles": [role for name, role in
                         (("sa", "anneal"), ("gaussian_search", "sample"))
                         for _ in range(self.last_counts.get(name, 0))]}
        elif kind == "strategy_chain":
            scheduler = {"kind": kind, "index": 0 if self.updates < 2 else 1,
                         "local_updates": self.updates if self.updates < 2 else self.updates - 2,
                         "completed": self.updates >= 6}
        elif kind == "strategy_router":
            scheduler = {"kind": kind, "updates": self.updates, "allocations": dict(self.last_counts)}
        else:
            active = self.timeline[self.updates] if self.updates < len(self.timeline) else []
            scheduler = {"kind": kind, "updates": self.updates, "completed": self.updates >= len(self.timeline),
                         "active": [{"name": name, "label": label, "count": count, "steps": steps}
                                    for name, label, count, steps in active]}
        return {"children": {name: child.state() for name, child in self.children.items()}, "scheduler": scheduler}


def run_composition_reference(seed, steps, evaluate, *, kind):
    reference = CompositionReference(kind, seed, evaluate)
    trace = [reference.step() for _ in range(steps)]
    return {"state": reference.state(), "trace": trace}


def make_elite_adapter(seed):
    from nsgablack.adapters.elite_retention import EliteRetentionAdapter, EliteRetentionConfig
    from nsgablack.representation import GaussianMutation

    child = make_trajectory_adapter("sa", seed)
    # Fixed-scale operator is explicit: retention calls mutation with the
    # parent call context, independently of SA's temperature-specific context.
    child.set_mutator(GaussianMutation(sigma=0.08))
    return EliteRetentionAdapter(child, EliteRetentionConfig(
        retention_probability=1.0, retention_ratio=0.5, history_size=3))


def _elite_archive(entries):
    return [{"candidate": np.asarray(getattr(item["candidate"], "values", item["candidate"])).tolist(),
             "objectives": np.asarray(item["objectives"]).tolist(), "violation": float(item["violation"]),
             "score": float(item["score"])} for item in entries]


def project_elite(solver):
    adapter = solver.adapter
    return {"child": trajectory_state("sa", adapter.inner, solver), "archive": _elite_archive(adapter._archive)}


class EliteReference:
    """Active retention replaces half the proposals; archive and RNG are real."""
    def __init__(self, seed, evaluate):
        root = np.random.default_rng(seed)
        self.rng = np.random.default_rng(int(root.integers(0, 2**63 - 1)))
        self.child = TrajectoryReference("sa", seed, evaluate=evaluate)
        self.child._draw = self._draw
        self.archive = []

    def _draw(self):
        child = self.child
        if child.current is None:
            rows = np.asarray([[1.5, -1.0]])
        else:
            rows = np.asarray([child.current + child.mutation_rng.normal(0.0, 0.08, 2) for _ in range(4)])
        if self.archive and self.rng.random() < 1.0:
            count = int(np.ceil(len(rows) * 0.5))
            selected = self.rng.choice(len(self.archive), size=count, replace=True)
            for offset, index in enumerate(selected):
                rows[len(rows) - count + offset] = (np.asarray(self.archive[int(index)]["candidate"])
                    + child.mutation_rng.normal(0.0, 0.08, 2))
        return rows, "retention"

    def step(self):
        batch = self.child.step()
        for x, f, v in zip(batch["candidates"], batch["objectives"], batch["violations"]):
            self.archive.append({"candidate": x, "objectives": f, "violation": v, "score": float(np.sum(f))})
        self.archive.sort(key=lambda item: (int(item["violation"] > 0), max(0.0, item["violation"]), item["score"]))
        self.archive = self.archive[:3]
        return {**batch, "state": self.state()}

    def state(self):
        return {"child": self.child.state(), "archive": _elite_archive(self.archive)}


def run_elite_reference(seed, steps, evaluate):
    reference = EliteReference(seed, evaluate)
    trace = [reference.step() for _ in range(steps)]
    return {"state": reference.state(), "trace": trace}


def make_pool_task_adapter(seed):
    from nsgablack.adapters.multi_strategy import StrategySpec, MultiStrategyConfig
    from nsgablack.adapters.search_plan import SearchPlanAdapter, serial, stage
    from nsgablack.adapters.pool_tasks import PoolTaskSpec

    producer = make_trajectory_adapter("gaussian_search", seed + 101)
    child = make_trajectory_adapter("sa", seed)
    return SearchPlanAdapter(serial(stage("source", steps=1), stage("refine")),
        [StrategySpec(producer, "source"), StrategySpec(child, "refine", pool_task=PoolTaskSpec(
            mode="refine", count=1, steps=3, output="accepted_trials", shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False, seeds_per_task=0), name="pool_task_fixture")


def project_pool_task(solver):
    adapter = solver.adapter
    producer, task = adapter.units[0].adapter, adapter.units[1].adapter
    status = task.task_status
    done = status["status"] == "done"
    refs = task.get_pool_task_results(solver) if done else ()
    output = task._local.get("output")
    history = len(solver.solution_pool.subpool_refs(output)) if output is not None else 0
    return {"children": {"source": trajectory_state("gaussian_search", producer, solver),
                         "refine": trajectory_state("sa", task.inner, solver)},
            "scheduler": {"updates": adapter._step, "completed": adapter.cursor.completed,
                          "task": {key: status[key] for key in ("status", "next", "count", "steps")}},
            "selected_results": [] if not refs else solver.read_solutions(refs).numeric_matrix.tolist(),
            "accepted_history_count": history}


class PoolTaskReference:
    def __init__(self, seed, evaluate):
        self.source = TrajectoryReference("gaussian_search", seed + 101, evaluate=evaluate)
        self.refine = TrajectoryReference("sa", seed, evaluate=evaluate)
        self.updates, self.history = 0, 0

    def step(self):
        batch = self.source.step() if self.updates == 0 else self.refine.step()
        if self.updates:
            self.history += len(batch["candidates"])
        self.updates += 1
        return {**batch, "state": self.state()}

    def state(self):
        count = self.updates - 1
        done = count >= 3
        task = ({"status": None, "next": None, "count": None, "steps": None} if count <= 0 else
                {"status": "done" if done else "running", "next": 1 if done else 0, "count": 1, "steps": count})
        return {"children": {"source": self.source.state(), "refine": self.refine.state()},
                "scheduler": {"updates": self.updates, "completed": done, "task": task},
                "selected_results": [self.refine.best.tolist()] if done else [],
                "accepted_history_count": self.history if done else 0}


def run_pool_task_reference(seed, steps, evaluate):
    reference = PoolTaskReference(seed, evaluate)
    trace = [reference.step() for _ in range(steps)]
    return {"state": reference.state(), "trace": trace}


def _stagnation_zero(feedback):
    """Explicit control metric to exercise recovery independently of chance."""
    return 0.0


def make_pool_search_adapter(seed):
    from benchmarks.transparency_population import make_population_adapter
    from nsgablack.adapters.pool_search import PoolSearchAdapter, PoolSearchSpec

    return PoolSearchAdapter(make_trajectory_adapter("sa", seed + 101),
        [PoolSearchSpec(make_population_adapter(seed, algorithm="nsga2"), initial_count=2)],
        stagnation_steps=1, recovery_steps=2, metric=_stagnation_zero)


def project_pool_search(solver):
    adapter = solver.adapter
    population = adapter.searches[0].adapter
    if population.population is None:
        members = None
    else:
        x, f, v = population.get_population_snapshot()
        members = {"population": x.tolist(), "objectives": f.tolist(), "violations": v.tolist()}
    return {"children": {"source": trajectory_state("sa", adapter.producer, solver), "search": members},
            "scheduler": {key: getattr(adapter, key) for key in
                          ("phase", "prepared_count", "recovery_count", "stagnation", "best_metric")}}


class PoolSearchReference:
    def __init__(self, seed, evaluate):
        from benchmarks.transparency_population import PopulationReferenceKernel

        self.producer = TrajectoryReference("sa", seed + 101, evaluate=evaluate)
        self.search = PopulationReferenceKernel("nsga2", seed)
        self.evaluate = evaluate
        self.phase, self.prepared_count, self.recovery_count, self.stagnation = "preparing", 0, 0, 0
        self.best_metric, self.records, self.recovery_rows = None, [], []
        self.initialized = False

    def _evaluate_population(self, values):
        candidates = np.asarray(values, dtype=float)
        feedback = [self.evaluate(row.copy()) for row in candidates]
        f, v = np.asarray([item[0] for item in feedback]), np.asarray([item[1] for item in feedback])
        self.search.tell(candidates, f, v)
        return {"candidates": candidates.tolist(), "objectives": f.tolist(), "violations": v.tolist()}

    def step(self):
        phase = self.phase
        if phase == "preparing":
            batch = self.producer.step()
            self.prepared_count += len(batch["candidates"])
            if self.prepared_count >= 2:
                self.phase = "search"
        elif phase == "search":
            if not self.initialized:
                batch = self._evaluate_population(self.records[:2])
                self.initialized = True
            else:
                batch = self._evaluate_population(self.search.ask())
            if self.best_metric is None:
                self.best_metric, self.stagnation = 0.0, 0
            else:
                self.stagnation += 1
            if self.stagnation >= 1:
                self.phase, self.recovery_count = "recovery", 0
        elif phase == "recovery":
            if self.recovery_count == 0:
                # Explicit restart retains RNGs and consumes the latest exact
                # published candidate as its newly evaluated baseline.
                self.producer.current = self.producer.current_score = None
                self.producer.best = self.producer.best_score = None
                self.producer.temperature = 0.7
                seed = np.asarray(self.records[-1], dtype=float).copy()
                draw = self.producer._draw
                self.producer._draw = lambda: (seed[None, :], "baseline")
                batch = self.producer.step()
                self.producer._draw = draw
            else:
                batch = self.producer.step()
            self.recovery_rows.extend(batch["candidates"])
            self.recovery_count += 1
            if self.recovery_count >= 2:
                self.phase = "return"
        elif phase == "return":
            batch = self._evaluate_population(self.recovery_rows)
            self.phase, self.stagnation = "search", 0
            self.recovery_rows = []
        else:
            raise AssertionError("invalid independent pool schedule")
        self.records.extend(batch["candidates"])
        return {**batch, "state": self.state()}

    def state(self):
        members = self.search.project() if self.initialized else None
        return {"children": {"source": self.producer.state(), "search": members},
                "scheduler": {key: getattr(self, key) for key in
                              ("phase", "prepared_count", "recovery_count", "stagnation", "best_metric")}}


def run_pool_search_reference(seed, steps, evaluate):
    reference = PoolSearchReference(seed, evaluate)
    trace = [reference.step() for _ in range(steps)]
    return {"state": reference.state(), "trace": trace}


def specs():
    from benchmarks.transparency_core import PairSpec

    limits = {"search_plan_serial": 4, "search_plan_multi": 3}
    combinations = [PairSpec(name=kind, make_problem=partial(make_trajectory_problem, "sa"),
        make_adapter=partial(make_composition_adapter, kind=kind), make_pipeline=None,
        reference=partial(run_composition_reference, kind=kind),
        project=partial(project_composition, kind=kind), steps=limits.get(kind, 6),
        metadata={"family": "composition", "adapters": [kind],
                  "children": ["sa"] if kind == "role_adapter" else list(LEAVES),
                  "reference": "independent Python activation table plus independent trajectory numeric kernels",
                  "rng_pairing": "child explicit algorithm seeds seed and seed+101; normal operator binding slots preserved",
                  "execution": "single Solver, sequential in-process child calls; multi merges proposals, not parallel execution",
                  "scope": "child state, scoped feedback, local quotas, retained children across serial/multi/repeat; full admission",
                  "not_covered": ["dynamic router weights", "budget truncation", "domain backend", "cross-Case parallelism"]})
            for kind in COMPOSITION_NAMES]
    combinations.extend([
        PairSpec(name="elite_retention", make_problem=partial(make_trajectory_problem, "sa"),
            make_adapter=make_elite_adapter, make_pipeline=None, reference=run_elite_reference,
            project=project_elite, steps=6,
            metadata={"family": "composition", "adapters": ["EliteRetentionAdapter"],
                      "scope": "active retention probability1 ratio0.5 history3; actual proposal replacement, archive, child state",
                      "mutation": "explicit fixed sigma0.08 direct Gaussian operator, also used by elite injection",
                      "reference": "independent archive and injection plus independent SA numeric kernel"}),
        PairSpec(name="pool_task", make_problem=partial(make_trajectory_problem, "sa"),
            make_adapter=make_pool_task_adapter, make_pipeline=None, reference=run_pool_task_reference,
            project=project_pool_task, steps=4,
            metadata={"family": "composition", "adapters": ["PoolTaskAdapter", "SearchPlanAdapter"],
                      "scope": "ordinary pool source, single seed, three committed refinement updates, final best and all nine accepted trials",
                      "reference": "independent prepare/refine schedule, source and SA kernels; explicit reevaluation of intake seed",
                      "not_covered": ["objective projections", "multi-worker allocation", "partial admission"]}),
        PairSpec(name="pool_search", make_problem=partial(make_trajectory_problem, "sa"),
            make_adapter=make_pool_search_adapter, make_pipeline=None, reference=run_pool_search_reference,
            project=project_pool_search, steps=7,
            metadata={"family": "composition", "adapters": ["PoolSearchAdapter"],
                      "scope": "prepare source candidates, two-member NSGA2 intake, growth to10, recovery restart, re-evaluated return competition",
                      "metric": "explicit constant stagnation metric triggers recovery; objective remains sphere",
                      "reference": "independent append-only numeric record list and scheduling plus SA and population kernels",
                      "not_covered": ["multiple search populations", "partial intake", "objective projection", "pool GC"]}),
    ])
    return combinations
