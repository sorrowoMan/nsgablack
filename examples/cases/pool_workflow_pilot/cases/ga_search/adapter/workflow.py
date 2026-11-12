"""一对父代共同产生两个后代；选择和档案维护都用引用集合。"""
from functools import partial
import numpy as np
from nsgablack.adapters import (
    ChangeBatchResult, ChangeResult, MultiStrategyConfig, NSGA2Adapter,
    Pool, PoolOutput, PoolTaskSpec, RoleSpec, StrategyRouterAdapter,
)
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort


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


def choose_survivors(pool, *, count, rng):
    """Pool进、Pool出；复用约束支配排序，末层以拥挤度裁剪。"""
    del rng
    objectives, violations = pool.objectives, pool.violations
    fronts, _ = FastNonDominatedSort.sort(objectives, violations)
    selected = []
    for front in fronts:
        remaining = count - len(selected)
        if len(front) <= remaining:
            selected.extend(front)
        else:
            distances = FastNonDominatedSort.calculate_crowding_distance(objectives, front)
            selected.extend(sorted(front, key=lambda i: (-distances[i], i))[:remaining])
        if len(selected) == count:
            break
    return pool.take(selected)


def elite_key(pool):
    objectives, violations = pool.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(violations, 0.),
                            np.sum(objectives, axis=1)))


def maintain_elite(request, *, rng):
    """本批接纳后立即维护普通精英池，不等同于GA生存成员。"""
    del rng
    kept = request.pool.subpool("elite").merge(request.accepted).top(20, key=elite_key)
    return (request.pool.replace_members("elite", kept.refs),)


def maintain_final_members(request, *, rng):
    """历史精英只与本轮最终成员归并；已接纳但被淘汰的试探不入档。"""
    if request.members is None:
        raise ValueError("final-member archive requires the owning population's result")
    names = request.pool.describe()["subpools"]
    old = request.pool.subpool("elite") if "elite" in names else request.members.take(())
    kept = old.merge(request.members).chosen(lambda pool: pool.top(20, key=elite_key), rng=rng)
    archive = Pool(parent=request.pool, name="elite")
    archive.inject(kept, replace=True)


def build_adapter(settings):
    if settings.archive_source not in {"accepted", "members"}:
        raise ValueError("archive_source must be 'accepted' or 'members'")
    if settings.parallel_archive:
        if settings.archive_source != "members":
            raise ValueError("parallel_archive requires archive_source='members'")
        roles = []
        for name in ("first", "second"):
            ga = NSGA2Adapter(name=name, population_size=settings.population_size,
                offspring_size=settings.offspring_size, change=paired_change)
            ga.set_selector(choose_survivors)
            roles.append(RoleSpec(name, ga, pool_task=PoolTaskSpec(mode="initialize",
                count=settings.population_size, shuffle=False, change_sources=("elite",))))
        return StrategyRouterAdapter(name="shared_archive_workflow", roles=roles,
            config=MultiStrategyConfig(total_batch_size=2*max(settings.population_size,
                settings.offspring_size), adapt_weights=False),
            pool_maintenance=maintain_final_members)
    ga = NSGA2Adapter(name="ga", population_size=settings.population_size,
        offspring_size=settings.offspring_size, change=paired_change)
    ga.set_selector(partial(choose_survivors, count=settings.population_size))
    ga.set_pool_maintenance(maintain_final_members if settings.archive_source == "members" else maintain_elite)
    return StrategyRouterAdapter(name="ga_workflow", roles=[RoleSpec("search", ga,
        pool_task=PoolTaskSpec(mode="initialize", count=settings.population_size,
                              shuffle=False, change_sources=("elite",)))],
        config=MultiStrategyConfig(total_batch_size=max(settings.population_size,
            settings.offspring_size), adapt_weights=False))
