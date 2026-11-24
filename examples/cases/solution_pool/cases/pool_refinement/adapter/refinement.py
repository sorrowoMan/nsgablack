"""由现有角色调度器分发子池精修，再交给种群自身选择。"""
import numpy as np

from nsgablack.adapters import (
    MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, VNSAdapter,
)


def select_twenty(control, context):
    """本例是单目标；选择已提交且已求值的候选版本。"""
    refs = control.solution_pool.select(stage="accepted")
    if not refs:
        return ()
    objectives, violations = control.solution_pool.read_raw_feedback(refs)
    order = np.lexsort((objectives[:, 0], violations))[:20]
    return tuple(refs[i] for i in order)


def phase_policy(context):
    if context["step"] < 1:
        return "explore"
    tasks = context["pool_tasks"]
    local = [state for key, state in tasks.items() if not key.startswith("ga:")]
    if not all(state["status"] == "done" for state in local):
        return "refine"
    if tasks["ga:0"]["status"] != "done":
        return "return"
    return "search"


def fine_vns(unit_id):
    return VNSAdapter(name=f"fine_{unit_id}", batch_size=2,
                      base_sigma=0.05, restart_on_stagnation=False)


def coarse_vns(unit_id):
    return VNSAdapter(name=f"coarse_{unit_id}", batch_size=2,
                      base_sigma=0.25, restart_on_stagnation=False)


def build_refinement_adapter():
    task = PoolTaskSpec(select_twenty, steps=2, output="refined", count="all")
    return StrategyRouterAdapter(name="refinement", roles=[
        RoleSpec("ga", NSGA2Adapter(population_size=20, offspring_size=20),
                 pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",))),
        RoleSpec("fine", fine_vns, n_units=2, pool_task=task),
        RoleSpec("coarse", coarse_vns, n_units=2, pool_task=task),
    ], config=MultiStrategyConfig(
        total_batch_size=40, adapt_weights=False, phase_policy=phase_policy,
        phase_roles={"explore": ["ga"], "refine": ["fine", "coarse"],
                     "return": ["ga"], "search": ["ga"]},
    ))
