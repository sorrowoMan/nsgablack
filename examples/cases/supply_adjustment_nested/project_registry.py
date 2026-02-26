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
            summary="Optimize SUPPLY.xlsx by whole-event early shifts with inner production evaluation.",
            companions=("project.problem.supply_event_shift", "project.tool.production_inner_eval"),
            context_requires=(),
            context_provides=(),
            context_mutates=(),
            context_cache=(),
            context_notes=("Assembly entrypoint for outer supply adjustment + inner production evaluation model.",),
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
            companions=("project.tool.production_inner_eval",),
            context_requires=(),
            context_provides=("inner_metrics",),
            context_mutates=(),
            context_cache=(),
            context_notes=(
                "Rules: day0 fixed, only early shift, whole-event move (no split).",
            ),
            use_when=("Need to optimize movement count/distance while preserving event integrity.",),
            minimal_wiring=(
                "from problem.supply_event_shift_problem import SupplyEventShiftProblem",
                "problem = SupplyEventShiftProblem(base_supply=..., inner_model=...)",
            ),
            required_companions=("project.tool.production_inner_eval",),
            config_keys=("base_supply", "events", "bounds"),
            example_entry="build_solver:build_solver",
        ),
        CatalogEntry(
            key="tool.production_inner_eval",
            title="ProductionInnerEvaluationModel",
            kind="tool",
            import_path="evaluation.production_inner_eval:ProductionInnerEvaluationModel",
            tags=("project", "inner", "evaluation", "production"),
            summary="Inner model: evaluates adjusted supply with deterministic production simulation.",
            companions=(),
            context_requires=(),
            context_provides=("inner_metrics",),
            context_mutates=(),
            context_cache=(),
            context_notes=("Inner layer is evaluation semantics, not a sibling outer optimization problem.",),
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
