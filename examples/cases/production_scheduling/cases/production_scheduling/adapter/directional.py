"""在既有解池和搜索计划上装配方向精修，不改写 Problem 原始目标。"""
from __future__ import annotations

import math

from nsgablack.adapters import (
    MOEADAdapter,
    MOEADConfig,
    MultiStrategyConfig,
    PoolTaskSpec,
    SearchPlanAdapter,
    StrategySpec,
    VNSAdapter,
    VNSConfig,
    repeat,
    serial,
    stage,
    subpools,
)


def current_refined_results(control, context):
    """返回本次精修请求的最终引用，避免把累计接纳历史当作最终解。"""
    del context
    return control.adapter.get_pool_task_results(control, "local")


def _positive_int(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def build_moead_adapter(problem, args):
    """Same MOEA/D constructor for isolated and hybrid ablation arms."""
    if problem.get_num_objectives() != 4:
        raise ValueError("directional production search requires the original four objectives")
    return MOEADAdapter(MOEADConfig(
        population_size=int(args.moead_pop_size),
        neighborhood_size=min(int(args.moead_pop_size), max(2, int(args.moead_neighborhood))),
        batch_size=max(8, int(args.pop_size)), delta=float(args.moead_delta),
        nr=max(1, int(args.moead_nr)), decomposition="tchebycheff", variation="pipeline",
        objective_scales=(float(args.objective_output_scale), 1.0, 1.0, 1.0),
        random_seed=args.seed), name="production_directions")


def build_directional_adapter(problem, args):
    """复用一个 MOEA/D 所有者：搜索 → 方向任务 → 原种群竞争，按轮重复。

    搜索步数按已接纳更新计数；精修与返回阶段必须等待池任务完成。
    精修的每个起点都先送评，再在冻结方向投影中比较后继。母池反馈仍是
    原始四目标，目标尺度只属于 MOEA/D 的比较与所发布的方向视图。
    """
    if int(problem.get_num_objectives()) != 4:
        raise ValueError("directional production search requires the original four objectives")
    if (str(getattr(args, "explorer_adapter", "moead")) != "moead"
            or str(getattr(args, "exploiter_adapter", "vns")) != "vns"):
        raise ValueError("directional cooperation requires the moead explorer and vns refiner")
    cycles = _positive_int(getattr(args, "quality_cycles", 2), "quality_cycles")
    explore_steps = _positive_int(getattr(args, "explore_steps", 12), "explore_steps")
    local_steps = _positive_int(getattr(args, "refine_steps", 5), "refine_steps")
    if local_steps < 2:
        raise ValueError("refine_steps includes the seed baseline and must allow a neighborhood update")
    directions = _positive_int(int(args.moead_pop_size), "moead_pop_size")
    if directions < 2:
        raise ValueError("MOEA/D requires at least two directions")
    selected = getattr(args, "refine_directions", 8)
    if type(selected) is not int or selected < 0 or selected > directions:
        raise ValueError("refine_directions must be zero (all) or at most moead_pop_size")
    output_scale = float(getattr(args, "objective_output_scale", 100000.0))
    if not math.isfinite(output_scale) or output_scale <= 0:
        raise ValueError("objective_output_scale must be finite and positive")
    budget = max(8, int(args.pop_size))
    # A finite search stage must deliver every initial member before a view can
    # be frozen. The Solver's global max_steps remains an independent limit.
    if explore_steps < math.ceil(directions / budget):
        raise ValueError("explore_steps cannot complete the configured MOEA/D initialization")

    moead = build_moead_adapter(problem, args)
    local = VNSAdapter(
        VNSConfig(
            batch_size=max(1, int(args.vns_batch_size)),
            k_max=max(1, int(args.vns_k_max)),
            base_sigma=float(args.vns_base_sigma),
            scale=1.6,
            objective_aggregation="first",
            restart_on_stagnation=False,
        ),
        name="direction_refinement",
    )
    selection = subpools.all(moead) if selected == 0 else subpools.random(selected, moead)
    return SearchPlanAdapter(
        repeat(times=cycles, body=serial(
            stage("moead", label="explore", steps=explore_steps),
            stage("local", label="refine"),
            stage("moead", label="return"),
        )),
        strategies=[
            StrategySpec(moead, "moead", pool_task=PoolTaskSpec(
                current_refined_results, mode="compete", phases=("return",),
                on_insufficient="available", shuffle=False,
            )),
            StrategySpec(local, "local", pool_task=PoolTaskSpec(
                selection, mode="refine", count=1, steps=local_steps,
                shuffle=False,
            )),
        ],
        config=MultiStrategyConfig(total_batch_size=budget, adapt_weights=False),
        name="production_directional_search",
    )


__all__ = ["build_directional_adapter"]
