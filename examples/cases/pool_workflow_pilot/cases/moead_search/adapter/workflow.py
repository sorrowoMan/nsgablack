"""按方向调用普通函数；分解、邻域和目标比较仍由原 MOEA/D 维护。"""
import numpy as np
from nsgablack.adapters import (ChangeResult, MOEADAdapter, MultiStrategyConfig, PoolOutput,
                               PoolTaskSpec, RoleSpec, StrategyRouterAdapter)


def crossover_then_mutation(a, b, rng):
    child = (a + b) / 2.
    return child + rng.normal(0., .12, size=child.shape)


def mutation_then_crossover(a, b, rng):
    first = a + rng.normal(0., .12, size=a.shape)
    second = b + rng.normal(0., .12, size=b.shape)
    return (first + second) / 2.


def direction_change(request, *, rng):
    """同一 change 内自由组合多父代操作；输出仍是原 Problem 的候选。"""
    if len(request.source_refs) != len(request.parents) or request.parents.flags.writeable:
        raise ValueError("expected immutable parents with aligned exact pool references")
    mother = request.pool.main(stage="accepted").random(1, rng=rng)
    reference = request.pool.subpool("reference").random(1, rng=rng)
    donors = mother.merge(reference).values
    a, b = request.candidate, donors.mean(axis=0)
    if int(request.parameters["subproblem_index"]) % 2 == 0:
        child = crossover_then_mutation(a, b, rng)
    else:
        child = mutation_then_crossover(a, b, rng)
    return ChangeResult(child, outputs=(PoolOutput("moead_trials", create=True),))


def elite_key(selection):
    """仅全局精英档案用 raw 目标和，不替代 MOEA/D 方向比较。"""
    objectives, violations = selection.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(violations, 0.),
                            np.sum(objectives, axis=1)))


def maintain_elite(request, *, rng):
    """普通档案使用raw；每批一次，不改MOEA/D方向比较。"""
    del rng
    kept = request.pool.subpool("elite").merge(request.accepted).top(20, key=elite_key)
    return (request.pool.replace_members("elite", kept.refs),)


def build_adapter(settings):
    worker = MOEADAdapter(name="moead", population_size=settings.directions,
                          batch_size=settings.batch_size, neighborhood_size=3,
                          decomposition="weighted_sum", change=direction_change,
                          random_seed=settings.seed)
    worker.set_pool_maintenance(maintain_elite)
    return StrategyRouterAdapter(name="moead_workflow", roles=[RoleSpec("search", worker,
        pool_task=PoolTaskSpec(mode="initialize", count=settings.directions, shuffle=False,
                              change_sources=("reference", "elite"), change_allow_main=True))],
        config=MultiStrategyConfig(total_batch_size=settings.directions, adapt_weights=False))
