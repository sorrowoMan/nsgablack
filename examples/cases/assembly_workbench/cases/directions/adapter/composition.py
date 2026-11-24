"""相同的池任务接上 VNS 和 Pattern Search，不私写嵌套求解循环。"""
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PatternSearchAdapter, PoolTaskSpec,
    SearchPlanAdapter, StrategySpec, VNSAdapter, multi, serial, stage, subpools,
)
from nsgablack.representation import ContextGaussianMutation, GaussianMutation, UniformInitializer


def fine_results(control, context):
    """只交回本次任务的最终选择；不把历次已接纳试探当作结果。"""
    del context
    return control.adapter.get_pool_task_results(control, "fine")


def parallel_results(control, context):
    """两个独立精修分支的精确最终引用，按明确分支顺序交回。"""
    del context
    root = control.adapter
    return (root.get_pool_task_results(control, "coarse")
            + root.get_pool_task_results(control, "fine"))


def build_adapter(settings):
    moead = MOEADAdapter(
        name="direction_owner", population_size=settings.directions, batch_size=3,
        neighborhood_size=3, decomposition="tchebycheff", random_seed=settings.seed,
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.3),
    )
    coarse = VNSAdapter(name="coarse_vns", batch_size=1, base_sigma=0.35,
        restart_on_stagnation=False, mutator=ContextGaussianMutation(base_sigma=0.35))
    # The task/return wiring is unchanged if this instance is replaced with
    # another projection-capable refiner. Pattern Search polls two directions
    # in one dimension; its native geometry remains owned by this Adapter.
    fine = PatternSearchAdapter(name="fine_pattern", max_directions=1, step_size=0.08)
    directions = (subpools.all(moead) if settings.direction_sample is None
                  else subpools.random(settings.direction_sample, moead))
    parallel = settings.refinement_layout == "parallel"
    refinements = (multi(stage("coarse"), stage("fine")) if parallel
                   else serial(stage("coarse"), stage("fine")))
    return SearchPlanAdapter(
        serial(stage("moead", steps=settings.bootstrap_steps, label="search"),
               refinements, stage("moead", label="return")),
        strategies=[
            StrategySpec(moead, "moead", pool_task=PoolTaskSpec(parallel_results if parallel else fine_results,
                mode="compete", phases=("return",), shuffle=False)),
            StrategySpec(coarse, "coarse", pool_task=PoolTaskSpec(directions,
                count=1, steps=settings.local_steps, output=None, shuffle=False)),
            StrategySpec(fine, "fine", pool_task=PoolTaskSpec(directions if parallel else subpools.all(coarse),
                count=1, steps=settings.local_steps, output=None, shuffle=False)),
        ], config=MultiStrategyConfig(total_batch_size=settings.router_budget, adapt_weights=False),
        name="direction_plan",
    )
