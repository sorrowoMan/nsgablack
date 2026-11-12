"""GA一次选择交付成员与副池，下一代从已提交精英池抽父代。"""
from functools import partial
import numpy as np
from nsgablack.adapters import (
    ChangeBatchResult, ChangeResult, MixedPoolParentSelector, MultiStrategyConfig, NSGA2Adapter,
    Pool, PoolOutput, PoolTaskSpec, RoleSpec, SerialPhaseSpec, StrategyChainAdapter,
    StrategyRouterAdapter, partition,
)


def paired_change(request, *, rng):
    """一次掩码交叉产生互补孩子，共享父代且各自拥有提案身份。"""
    if len(request.parents) < 2 or len(request.source_refs) != len(request.parents):
        raise ValueError("paired crossover needs exactly identified parents")
    a, b = request.parents[:2]
    mask = rng.random(a.shape) < .5
    children = (np.where(mask, a, b), np.where(mask, b, a))
    return ChangeBatchResult(results=tuple(
        ChangeResult(child + rng.normal(0., .1, child.shape),
            source_refs=request.source_refs[:2],
            outputs=(PoolOutput("ga_trials", create=True),))
        for child in children[:min(2, request.max_outputs)]))


def choose_twenty(pool):
    """本例明确采用raw可行性、违反量、目标和，不冒充默认NSGA排序。"""
    return pool.top(20, key=elite_key)


def choose_survivors(pool, *, count, rng):
    """规则只算一次；副池复用同一offered根，精英明确取自最终成员。"""
    selected, remaining = partition(pool, by=choose_twenty, rng=rng)
    needed = min(count, len(pool)) - len(selected)
    members = selected.concat(remaining.take(range(needed)))
    elite = Pool(parent=members, name="elite")
    elite.inject(members.take(range(len(selected))), replace=True)
    reserve = Pool(parent=pool, name="reserve")
    reserve.inject(remaining.take(range(needed, len(remaining))), replace=True)
    return members


def elite_key(pool):
    objectives, violations = pool.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(violations, 0.),
                            np.sum(objectives, axis=1)))


def build_adapter(settings):
    ga = NSGA2Adapter(name="ga", population_size=settings.population_size,
        offspring_size=settings.offspring_size, change=paired_change,
        parent_selector=MixedPoolParentSelector("elite", pool_fraction=1.0))
    ga.set_selector(partial(choose_survivors, count=settings.population_size))
    router = StrategyRouterAdapter(name="ga_workflow", roles=[RoleSpec("search", ga,
        pool_task=PoolTaskSpec(mode="initialize", count=settings.population_size,
                              # 首轮只初始化；之后父代只能取已提交的上一轮 elite。
                              shuffle=False, change_sources=("elite",)))],
        config=MultiStrategyConfig(total_batch_size=max(settings.population_size,
            settings.offspring_size), adapt_weights=False))
    if settings.working_pool is None:
        return router
    # 只有外层Chain绑定区域；Router和未指定select的子任务自然继承。
    return StrategyChainAdapter(name="workspace_workflow", working_pool=settings.working_pool,
        phases=[SerialPhaseSpec("search", router)])
