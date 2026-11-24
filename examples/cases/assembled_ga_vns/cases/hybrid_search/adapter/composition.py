"""用公开角色、池任务和操作绑定装配 GA → VNS → GA 返回竞争。"""
from functools import partial

from nsgablack.adapters import (
    MultiStrategyConfig, NSGA2Adapter, Pool, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, VNSAdapter, subpools,
)
from nsgablack.representation import ContextGaussianMutation, GaussianMutation, UniformInitializer
from nsgablack.units import UnitBinding
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort
from ..pipeline.population import AgePopulationBuilder


ELITE_POOL_NAME = "ga_elite"


def select_elite_refs(control, context):
    """准确公共名读取，不把PoolTask的相对名称规则套到选择副结果上。"""
    del context
    return control.solution_pool.subpool_refs(ELITE_POOL_NAME)


def select_current_refinement_results(control, context):
    """本轮已提交的最终选择；不把历史refined提案当作当前轮精选。"""
    del context
    return control.adapter.get_pool_task_results(control, "vns")


def selection_key(pool):
    """本例单目标：按当前选择反馈的可行性、违反量、目标排序。"""
    import numpy as np
    return np.column_stack((pool.violations > 0., np.maximum(pool.violations, 0.),
                            pool.objectives[:, 0]))


def choose_members_and_elite(pool, *, count, elite_count, rng):
    """保留NSGA约束支配/拥挤度选择，再从主成员中明确选精英副池。"""
    objectives, violations = pool.objectives, pool.violations
    fronts, _ = FastNonDominatedSort.sort(objectives, violations)
    indices = []
    for front in fronts:
        remaining = count - len(indices)
        if len(front) <= remaining:
            indices.extend(front)
        else:
            distance = FastNonDominatedSort.calculate_crowding_distance(objectives, list(front))
            indices.extend(sorted(front, key=lambda index: float(distance[index]), reverse=True)[:remaining])
        if len(indices) == count:
            break
    members = pool.take(indices)
    elite = Pool(parent=members, name=ELITE_POOL_NAME)
    elite.inject(members.chosen(lambda offered: offered.top(elite_count, key=selection_key),
                                rng=rng), replace=True)
    return members


def build_adapter(settings):
    ga = NSGA2Adapter(
        name="ga", population_size=settings.population_size, offspring_size=settings.population_size,
        initializer=UniformInitializer(-4.0, 4.0),
        mutator=GaussianMutation(sigma=settings.ga_sigma),
        unit_binding=UnitBinding(AgePopulationBuilder()),
    )
    vns = VNSAdapter(
        name="vns", batch_size=settings.local_batch, k_max=3,
        base_sigma=settings.vns_sigma, scale=1.5, max_sigma=0.8,
        restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=settings.vns_sigma),
    )
    source = subpools.all(ga)
    if settings.refinement_source == "elite":
        ga.set_selector(partial(choose_members_and_elite, count=settings.population_size,
                                elite_count=settings.elite_count))
        source = select_elite_refs
    if settings.schedule == "plan":
        from nsgablack.adapters.search_plan import SearchPlanAdapter, repeat, serial, stage
        from nsgablack.adapters import StrategySpec
        return SearchPlanAdapter(
            repeat(times=settings.rounds, body=serial(
                stage("ga", steps=settings.ga_steps, label="ga"),
                stage("vns", label="vns"),
                stage("ga", label="return"),
            )), strategies=[
                StrategySpec(name="ga", adapter=ga, pool_task=PoolTaskSpec(
                    select_current_refinement_results, mode="compete",
                    phases=("return",), count="all", shuffle=False)),
                StrategySpec(name="vns", adapter=vns, pool_task=PoolTaskSpec(
                    source, mode="refine", count="all", steps=settings.local_steps,
                    output="refined", shuffle=False)),
            ], config=MultiStrategyConfig(total_batch_size=settings.proposal_budget,
                                          adapt_weights=False),
            name="ga_vns",
        )
    local_steps = settings.refinement_count * settings.local_steps
    return StrategyRouterAdapter(
        name="ga_vns", roles=[
            RoleSpec("global", ga, pool_task=PoolTaskSpec(
                "refined", mode="compete", phases=("return",), count="all", shuffle=False)),
            # 默认精修全部成员；显式elite模式读取同次choose发布的准确公共名。
            # 每项任务包含起点重新求值的一步，聚合output不冒充最终精选。
            RoleSpec("refinement", vns, pool_task=PoolTaskSpec(
                source, mode="refine", count="all",
                steps=settings.local_steps, output="refined", shuffle=False)),
        ], config=MultiStrategyConfig(
            # 提案上限，允许最后一次竞争读完整聚合池；不是种群或池容量。
            total_batch_size=settings.proposal_budget, adapt_weights=False,
            phase_schedule=(("ga", settings.ga_steps), ("vns", local_steps), ("return", 1)),
            phase_roles={"ga": ["global"], "vns": ["refinement"], "return": ["global"]},
        ),
    )
