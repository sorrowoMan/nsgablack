"""普通函数只产生新候选；VNS 继续拥有比较、邻域切换和当前点。"""
import numpy as np
from nsgablack.adapters import (ChangeResult, MultiStrategyConfig, PoolOutput, PoolTaskSpec,
                               RoleSpec, StrategyRouterAdapter, VNSAdapter)


def neighborhood_change(request, *, rng):
    """当前点与参考池共同产生提案；输出由接纳与提交链统一交付。"""
    if len(request.source_refs) != 1 or request.parents.flags.writeable:
        raise ValueError("expected one immutable, exactly identified parent")
    direction = rng.normal(size=request.candidate.shape)
    direction /= max(float(np.linalg.norm(direction)), 1e-12)
    reference = request.pool.subpool("reference").random(1, rng=rng).values[0]
    center = .8 * request.candidate + .2 * reference
    child = center + float(request.parameters["sigma"]) * direction
    return ChangeResult(child, outputs=(PoolOutput("vns_trials", create=True),))


def elite_key(selection):
    """全局档案显式按 raw 可行性、违反量、目标和排序。"""
    objectives, violations = selection.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(violations, 0.),
                            np.sum(objectives, axis=1)))


def maintain_elite(request, *, rng):
    """每个真实更新批次只整理一次，包含本批已硬接纳的反馈。"""
    del rng
    kept = request.pool.subpool("elite").merge(request.accepted).top(20, key=elite_key)
    return (request.pool.replace_members("elite", kept.refs),)


def build_adapter(settings):
    worker = VNSAdapter(name="vns", batch_size=settings.batch_size, k_max=3,
                        base_sigma=.15, scale=1.7, max_sigma=.7,
                        restart_on_stagnation=False, change=neighborhood_change)
    worker.set_pool_maintenance(maintain_elite)
    return StrategyRouterAdapter(name="vns_workflow", roles=[RoleSpec("search", worker,
        pool_task=PoolTaskSpec(mode="initialize", count=1, shuffle=False,
                              change_sources=("reference", "elite"), change_allow_main=True))],
        config=MultiStrategyConfig(total_batch_size=settings.batch_size, adapt_weights=False))
