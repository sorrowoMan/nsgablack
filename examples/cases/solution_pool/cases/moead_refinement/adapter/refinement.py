"""只装配既有组件：方向子池、局部精修、返回种群竞争。"""
from nsgablack.adapters import (
    MOEADAdapter, NSGA2Adapter, VNSAdapter, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, MultiStrategyConfig, subpools,
)


def phase_policy(context):
    if context["step"] == 0:
        return "explore"
    tasks = context["pool_tasks"]
    local = [state for key, state in tasks.items() if key.startswith("local:")]
    if not all(state["status"] == "done" for state in local):
        return "refine"
    return "search" if tasks["moead:0"]["status"] == "done" else "return"


def local_search(index):
    return VNSAdapter(name=f"vns_{index}", batch_size=2, base_sigma=0.1,
                      restart_on_stagnation=False)


def build_refinement_adapter(*, directions=100, view_count=20, workers=4, local_steps=3):
    moead = MOEADAdapter(name="adapter1", population_size=directions, batch_size=4,
                         decomposition="tchebycheff")
    selection = subpools.all(moead) if view_count is None else subpools.random(view_count, moead)
    return StrategyRouterAdapter(name="directions", roles=[
        RoleSpec("moead", moead,
                 pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",))),
        # The explore phase lasts one dispatch: fit the initial GA intake in
        # its share of the 16-proposal router budget before pausing for VNS.
        RoleSpec("ga", NSGA2Adapter(population_size=min(8, directions), offspring_size=4),
                 pool_task=PoolTaskSpec(mode="initialize")),
        RoleSpec("local", local_search, n_units=workers,
                 pool_task=PoolTaskSpec(selection, steps=local_steps, output="refined")),
    ], config=MultiStrategyConfig(
        total_batch_size=16, adapt_weights=False, phase_policy=phase_policy,
        phase_roles={"explore": ["moead", "ga"], "refine": ["local"],
                     "return": ["moead"], "search": ["moead", "ga"]},
    ))
