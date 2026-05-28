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
7) L0 runtime（资源、worker、后端、数据流）
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
from plugins.config import apply_observability_profile, attach_flow_plugins, attach_ops_plugins
from problem.config import build_problem
from runtime.config import apply_runtime_profile
from solver.config import create_evolution_solver


def build_solver(
    run_id: str | None = None,
    *,
    problem_key: str = "example",
    pipeline_key: str = "default",
    bias_key: str = "none",
    flow_plugin_keys: tuple[str, ...] = (),
    ops_plugin_keys: tuple[str, ...] = (),
    component_overrides: dict[str, dict[str, object]] | None = None,
) -> EvolutionSolver:
    cfg = get_project_config()
    # --- Modeling ---------------------------------------------------------
    problem = build_problem(cfg.problems, str(problem_key))
    bias_module = build_bias(cfg.biases, str(bias_key), component_overrides=component_overrides)
    solver = create_evolution_solver(
        problem,
        bias_module=bias_module,
        store_registry=cfg.store_profiles,
    )
    #上面是搭建基本的solver出来，即solver对象
    pipeline = build_pipeline(cfg.pipelines, str(pipeline_key))
    solver.set_representation_pipeline(pipeline)
    #依旧属于建模层的管线
    register_evaluation_runtime(solver, cfg.evaluation, ())
    #理论上属于评估层，那么在我们设计的时候有奖，评估本身属于建模的一部分，因此l4的后端应该是属于这一层
    # --- L0 ----------------------------------------------------------
    apply_runtime_profile(solver, cfg.runtime, "local_cpu")
    # L0 只声明默认运行资源和后端。组件先按业务编排，后续再根据执行图局部覆盖 runtime profile。
    # --- L3 / Search ------------------------------------------------------
    search_adapter = compose_search(cfg.adapters, primary_key="vns", mode="single")
    if search_adapter is not None:
        solver.set_adapter(search_adapter)
    attach_flow_plugins(solver, cfg.flow_plugins, tuple(flow_plugin_keys), component_overrides=component_overrides)
    # compose_search在后面的代码编排了；
    run_id = str(run_id) if run_id else datetime.now().strftime("%Y%m%d_%H%M%S")
    # --- L1/L2 ------------------------------------------------------------
    apply_observability_profile(solver, cfg.observability, "default", run_id)
    attach_ops_plugins(solver, cfg.ops_plugins, tuple(ops_plugin_keys), component_overrides=component_overrides)
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


def main(argv=None):
    import argparse
    import sys as _sys
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--quickstart", action="store_true")
    p.add_argument("--strategy", type=str, default="nsga2")
    _args, _ = p.parse_known_args(argv)
    if _args.check:
        adapter_key = _args.strategy if _args.strategy else "nsga2"
        _solver = build_solver()
        _name = getattr(getattr(_solver, "adapter", None), "name", None) or type(getattr(_solver, "adapter", None)).__name__
        print(f"adapter={_name}")
        if _args.quickstart:
            _solver.set_max_steps(2)
            _solver.run()
            print("quickstart=ok")
        return 0
    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())

