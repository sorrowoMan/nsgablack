# -*- coding: utf-8 -*-
"""Local catalog entries for supply_adjustment_nested case."""

from __future__ import annotations

from nsgablack.catalog import CatalogEntry


def get_project_entries():
    return [
        CatalogEntry(
            key="solver.supply_adjustment_nested",
            title="Supply Adjustment Nested Solver",
            kind="example",
            import_path="build_solver:build_solver",
            tags=("project", "nested", "supply", "event-shift"),
            summary="Optimize SUPPLY.xlsx by whole-event early shifts with standard nested inner solver.",
            companions=("project.problem.supply_event_shift", "project.tool.inner_production_solver"),
            context_requires=(),
            context_provides=(),
            context_mutates=(),
            context_cache=(),
            context_notes=("Assembly entrypoint for outer supply adjustment + inner production solver runtime.",),
            use_when=("Need event-level supply-table optimization with movement-cost objectives.",),
            minimal_wiring=("python build_solver.py",),
            required_companions=("project.problem.supply_event_shift",),
            config_keys=("bom", "supply", "days", "pop_size", "generations"),
            example_entry="build_solver:build_solver",
        ),
        CatalogEntry(
            key="problem.supply_event_shift",
            title="SupplyEventShiftProblem",
            kind="tool",
            import_path="problem.supply_event_shift_problem:SupplyEventShiftProblem",
            tags=("project", "problem", "outer", "supply", "shift"),
            summary="Outer problem: decide how many days each non-zero supply event should be advanced.",
            companions=("project.tool.inner_production_solver",),
            context_requires=(),
            context_provides=("inner_metrics",),
            context_mutates=(),
            context_cache=(),
            context_notes=(
                "Rules: day0 fixed, only early shift, whole-event move (no split).",
                "Nested runtime calls inner production solver for objective evaluation.",
            ),
            use_when=("Need to optimize movement count/distance while preserving event integrity.",),
            minimal_wiring=(
                "from problem.supply_event_shift_problem import SupplyEventShiftProblem",
                "problem = SupplyEventShiftProblem(base_supply=..., bom_matrix=..., production_case_dir=..., inner_solver_cfg=...)",
            ),
            required_companions=("project.tool.inner_production_solver",),
            config_keys=("base_supply", "events", "bounds"),
            example_entry="build_solver:build_solver",
        ),
        CatalogEntry(
            key="tool.inner_production_solver",
            title="Inner Production Solver Builder",
            kind="tool",
            import_path="inner_solver:build_inner_production_solver",
            tags=("project", "inner", "solver", "production"),
            summary="Builds standard production scheduling solver for nested runtime.",
            companions=(),
            context_requires=(),
            context_provides=(),
            context_mutates=(),
            context_cache=(),
            context_notes=("Inner layer uses standard solver construction, not ad-hoc evaluation.",),
            use_when=("Need nested production scheduling solve from adjusted supply tables.",),
            minimal_wiring=(
                "from inner_solver import build_inner_production_solver",
                "solver, problem = build_inner_production_solver(bom_matrix=..., supply_matrix=..., production_case_dir=..., cfg=...)",
            ),
            required_companions=(),
            config_keys=("bom_matrix", "supply_matrix", "production_case_dir", "cfg"),
            example_entry="build_solver:build_solver",
        ),
        CatalogEntry(
            key="tool.production_inner_eval",
            title="ProductionInnerEvaluationModel",
            kind="tool",
            import_path="evaluation.production_inner_eval:ProductionInnerEvaluationModel",
            tags=("project", "inner", "evaluation", "production"),
            summary="Legacy inner evaluation model (non-standard nested solver).",
            companions=(),
            context_requires=(),
            context_provides=("inner_metrics",),
            context_mutates=(),
            context_cache=(),
            context_notes=("Kept for fast proxy modes; standard nested runtime uses inner solver.",),
            use_when=("Need production-quality metric while keeping outer decision on supply events.",),
            minimal_wiring=(
                "from evaluation.production_inner_eval import ProductionInnerEvaluationModel",
                "inner = ProductionInnerEvaluationModel(bom_matrix=...)",
            ),
            required_companions=(),
            config_keys=("max_active_machines_per_day", "max_production_per_machine"),
            example_entry="build_solver:build_solver",
        ),
    ]
