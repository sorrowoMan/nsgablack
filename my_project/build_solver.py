# -*- coding: utf-8 -*-
"""脚手架语法规范草案（规则 + 顺序）。

装配层只做“注册与协调”，不在此处设定组件参数；参数在各层 registry，选择在 build_solver。
语义分层规则：L0/L1/L2/L3/L4 仅用于插件类，目录名不决定层级。

装配顺序（与 build_solver 调用一致）：
1) problem
2) pipeline
3) bias
4) solver core
5) adapter
6) flow plugins（运行编排 / L3）
7) L0 plugins（计算后端）
8) L4 plugins（评估接管）
9) ops plugins（观测/工程保障 / L1-L2）
10) checkpoint（可选）

可执行判定句：
- 改记录/重放/审计/存储，不改搜索或评估语义 -> L1/L2
- 改搜索时序/策略路由/调度 -> L3
- 改评估来源或执行通路 -> L4

数据流锚点（不可打断）：
adapter.propose -> representation -> evaluation(problem 或 L4 provider) -> adapter.update -> plugin hooks -> snapshot/context

Stage-gate 提醒：
- Gate 1: problem 语义
- Gate 2: 层级归位
- Gate 3: catalog 组件筛选
- Gate 4: 装配落位（本文件）
"""
from __future__ import annotations
from datetime import datetime
from nsgablack.core.evolution_solver import EvolutionSolver

from acceleration.config import apply_acceleration_backends
from adapter.config import (
    all_of,
    any_of,
    ctx,
    custom,
    event,
    exists,
    gt,
    group,
    lt,
    multi,
    phase,
    serial,
    truthy,
)
from bias.domain.config import build_bias
from config import get_project_config
from evaluation.config import register_evaluation_runtime
from pipeline.config import build_pipeline
from plugins.config import apply_observability_profile, build_flow_plugins, build_ops_plugins
from problem.config import build_problem
from solver.config import create_evolution_solver
def build_solver(run_id: str | None = None) -> EvolutionSolver:
    cfg = get_project_config()
    # --- Modeling ---------------------------------------------------------
    problem = build_problem(cfg.problems, "example")
    bias_module = build_bias(cfg.biases, "none")
    solver = create_evolution_solver(
        problem,
        bias_module=bias_module,
        store_registry=cfg.store_profiles,
    )
    #上面是搭建基本的solver出来，即solver对象
    pipeline = build_pipeline(cfg.pipelines, "default")
    solver.set_representation_pipeline(pipeline)
    #依旧属于建模层的管线
    register_evaluation_runtime(solver, cfg.evaluation, ())
    #理论上属于评估层，那么在我们设计的时候有奖，评估本身属于建模的一部分，因此l4的后端应该是属于这一层
    # --- L0 ----------------------------------------------------------
    apply_acceleration_backends(solver, cfg.acceleration, ())
    #计算后端，这里我指出一个点，我的计算后端是实现了只要任何组件有计算需求都可以走计算后端的，这样实现还行吗？
    # --- L3 / Search ------------------------------------------------------
    search_adapter = compose_search(cfg.adapters, primary_key="vns", mode="single")
    if search_adapter is not None:
        solver.set_adapter(search_adapter)
    for plugin in build_flow_plugins(cfg.flow_plugins, ()):
        solver.add_plugin(plugin)
    #compose_search在后面的代码编排了；
    run_id = str(run_id) if run_id else datetime.now().strftime("%Y%m%d_%H%M%S")
    # --- L1/L2 ------------------------------------------------------------
    apply_observability_profile(solver, cfg.observability, "default", run_id)
    for plugin in build_ops_plugins(cfg.ops_plugins, ()):
        solver.add_plugin(plugin)
    #L1L2一般挂上就行，会自己取字段
    return solver


# --- L3 编排 -----------------------------------------------
def compose_search(registry, *, primary_key: str, mode: str) -> object | None:
    # Orchestration is explicit here; parameters stay in registry.
    explore = group(registry, "explore", [primary_key])
    exploit = group(registry, "exploit", [primary_key])

    mode = str(mode or "single").lower()
    if "serial" in mode or "multi" in mode:
        mixed = multi(registry, "mix", [explore, exploit])
        # ctx 语义示例：exists/比较/组合/自定义
        # advance_when=all_of(gt(ctx("generation"), 10), lt(ctx("best_objective"), ctx("target.objective")))
        # advance_when=any_of(truthy(ctx("signal.next_phase")), custom(lambda c: c.get("mode") == "exploit"))
        phases = [
            phase("mix", mixed, advance_when=exists(ctx("best_x"))),
            phase("exploit", exploit),
        ]
        return serial(registry, "search_flow", phases)

    if "event" in mode:
        return event(registry, "event_flow", [explore, exploit])

    return explore



