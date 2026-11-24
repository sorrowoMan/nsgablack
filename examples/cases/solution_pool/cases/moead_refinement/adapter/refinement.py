"""只装配既有组件：方向子池、局部精修、返回种群竞争。"""
from nsgablack.adapters import (
    MOEADAdapter, NSGA2Adapter, VNSAdapter, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, MultiStrategyConfig, SimulatedAnnealingAdapter,
    PatternSearchAdapter, subpools,
    GaussianSearchAdapter, MASAdapter, GradientDescentAdapter,
    TrustRegionDFOAdapter, TrustRegionMODFOAdapter, TrustRegionNonSmoothAdapter,
    TrustRegionSubspaceAdapter,
)


def phase_policy(context):
    if context["step"] == 0:
        return "explore"
    tasks = context["pool_tasks"]
    local = [state for key, state in tasks.items() if key.startswith("local:")]
    if not all(state["status"] == "done" for state in local):
        return "refine"
    return "search" if tasks["moead:0"]["status"] == "done" else "return"


def local_search(index, algorithm="vns"):
    if algorithm == "vns":
        return VNSAdapter(name=f"vns_{index}", batch_size=2, base_sigma=0.1,
                          restart_on_stagnation=False)
    if algorithm == "sa":
        return SimulatedAnnealingAdapter(name=f"sa_{index}", batch_size=2, base_sigma=0.1)
    if algorithm == "pattern":
        return PatternSearchAdapter(name=f"pattern_{index}")
    if algorithm == "gaussian":
        return GaussianSearchAdapter(name=f"gaussian_{index}", population_size=2,
                                     initialization="center", mutation_scale=.1)
    if algorithm == "mas":
        return MASAdapter(name=f"mas_{index}", batch_size=2)
    if algorithm == "finite_difference":
        return GradientDescentAdapter(name=f"finite_difference_{index}", max_directions=2)
    regions = {"trust_region": TrustRegionDFOAdapter, "trust_region_mo": TrustRegionMODFOAdapter,
               "trust_region_nonsmooth": TrustRegionNonSmoothAdapter, "trust_region_subspace": TrustRegionSubspaceAdapter}
    if algorithm in regions:
        return regions[algorithm](name=f"{algorithm}_{index}", batch_size=2, initial_radius=.1)
    raise ValueError(f"unsupported local algorithm: {algorithm}")


def build_refinement_adapter(*, directions=100, view_count=20, workers=4, local_steps=3, local_algorithm="vns"):
    moead = MOEADAdapter(name="adapter1", population_size=directions, batch_size=4,
                         decomposition="tchebycheff")
    selection = subpools.all(moead) if view_count is None else subpools.random(view_count, moead)
    def ready_phase(context):
        if not moead.pool_views_ready:
            return "bootstrap"
        if context["pool_tasks"]["ga:0"]["status"] != "done":
            return "explore"
        return phase_policy({**context, "step": max(1, context["step"])})
    def refiner(index):
        return local_search(index, local_algorithm)
    return StrategyRouterAdapter(name="directions", roles=[
        RoleSpec("moead", moead,
                 pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",))),
        # The explore phase lasts one dispatch: fit the initial GA intake in
        # its share of the 16-proposal router budget before pausing for VNS.
        RoleSpec("ga", NSGA2Adapter(population_size=min(8, directions), offspring_size=4),
                 pool_task=PoolTaskSpec(mode="initialize")),
        RoleSpec("local", refiner, n_units=workers,
                 pool_task=PoolTaskSpec(selection, steps=local_steps, output="refined")),
    ], config=MultiStrategyConfig(
        total_batch_size=16, adapt_weights=False, phase_policy=ready_phase,
        phase_roles={"bootstrap": ["moead"], "explore": ["ga"], "refine": ["local"],
                     "return": ["moead"], "search": ["moead", "ga"]},
    ))


def nested_phase_policy(context):
    """只决定阶段；引用选择、投影继承和事务仍由池任务负责。"""
    if context["step"] == 0:
        return "explore"
    tasks = context["pool_tasks"]
    for role in ("coarse", "fine", "moead"):
        if tasks[f"{role}:0"]["status"] != "done":
            return "return" if role == "moead" else role
    return "search"


def build_nested_refinement_adapter(*, directions=100, view_count=20, local_steps=3,
                                    fine_steps=3, decomposition="tchebycheff"):
    """方向视图 → 粗搜结果视图 → 细搜结果视图 → MOEA/D 返回竞争。

    两层各用一个明确的 VNS 实例，使来源选择能直接写成
    ``subpools.all(coarse_vns)``。增加层数只需按同样方式装配下一角色。
    """
    moead = MOEADAdapter(name="adapter1", population_size=directions, batch_size=4,
                         decomposition=decomposition)
    coarse_vns = VNSAdapter(name="coarse_vns", batch_size=2, base_sigma=0.2,
                            restart_on_stagnation=False)
    fine_vns = VNSAdapter(name="fine_vns", batch_size=2, base_sigma=0.05,
                          restart_on_stagnation=False)
    selection = subpools.all(moead) if view_count is None else subpools.random(view_count, moead)
    def ready_phase(context):
        if not moead.pool_views_ready:
            return "bootstrap"
        if context["pool_tasks"]["ga:0"]["status"] != "done":
            return "explore"
        return nested_phase_policy({**context, "step": max(1, context["step"])})
    return StrategyRouterAdapter(name="nested_directions", roles=[
        RoleSpec("moead", moead,
                 pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",))),
        RoleSpec("ga", NSGA2Adapter(population_size=min(8, directions), offspring_size=4),
                 pool_task=PoolTaskSpec(mode="initialize")),
        RoleSpec("coarse", coarse_vns,
                 pool_task=PoolTaskSpec(selection, steps=local_steps, output="coarse_results",
                                        shuffle=False)),
        RoleSpec("fine", fine_vns,
                 pool_task=PoolTaskSpec(subpools.all(coarse_vns), steps=fine_steps,
                                        output="refined", shuffle=False)),
    ], config=MultiStrategyConfig(
        total_batch_size=16, adapt_weights=False, phase_policy=ready_phase,
        phase_roles={"bootstrap": ["moead"], "explore": ["ga"], "coarse": ["coarse"],
                     "fine": ["fine"], "return": ["moead"], "search": ["moead", "ga"]},
    ))
