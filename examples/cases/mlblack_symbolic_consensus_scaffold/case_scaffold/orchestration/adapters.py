# -*- coding: utf-8 -*-
"""Outer adapter assembly for the mlblack symbolic consensus scaffold."""

from __future__ import annotations

import argparse

from nsgablack.adapters import (
    DEConfig,
    DifferentialEvolutionAdapter,
    MultiStrategyConfig,
    MultiStrategyControlRule,
    NSGA2Adapter,
    NSGA2Config,
    PatternSearchAdapter,
    PatternSearchConfig,
    RoleSpec,
    SPEA2Adapter,
    SPEA2Config,
    StrategyRouterAdapter,
    TrustRegionNonSmoothAdapter,
    TrustRegionNonSmoothConfig,
    VNSAdapter,
    VNSConfig,
)


def build_vns_adapter(args: argparse.Namespace) -> VNSAdapter:
    return VNSAdapter(
        VNSConfig(
            batch_size=max(4, int(args.batch_size)),
            k_max=max(1, int(args.vns_k_max)),
            base_sigma=float(args.vns_base_sigma),
            scale=1.6,
            objective_aggregation="sum",
        )
    )


def build_complex_adapter(args: argparse.Namespace) -> StrategyRouterAdapter:
    total_batch = max(6, int(args.batch_size))

    def nsga2_factory(_unit_id: int = 0):
        return NSGA2Adapter(
            NSGA2Config(
                population_size=max(4, int(args.nsga_pop_size)),
                offspring_size=max(2, total_batch),
                crossover_rate=0.9,
                objective_aggregation="sum",
            ),
            name="global_pareto_nsga2",
        )

    def spea2_factory(_unit_id: int = 0):
        return SPEA2Adapter(
            SPEA2Config(
                population_size=max(4, int(args.nsga_pop_size)),
                offspring_size=max(2, total_batch),
                archive_size=max(4, int(args.spea_archive_size)),
                objective_aggregation="sum",
            ),
            name="archive_spea2",
        )

    def de_factory(_unit_id: int = 0):
        return DifferentialEvolutionAdapter(
            DEConfig(
                population_size=max(4, int(args.de_pop_size)),
                batch_size=max(2, total_batch),
                differential_weight=0.65,
                crossover_rate=0.85,
                strategy="rand1bin",
                objective_aggregation="sum",
            ),
            name="exploration_de",
        )

    def vns_factory(_unit_id: int = 0):
        return VNSAdapter(
            VNSConfig(
                batch_size=max(2, total_batch),
                k_max=max(1, int(args.vns_k_max)),
                base_sigma=float(args.vns_base_sigma),
                scale=1.45,
                objective_aggregation="sum",
            ),
            name="local_vns",
        )

    def trust_region_factory(_unit_id: int = 0):
        return TrustRegionNonSmoothAdapter(
            TrustRegionNonSmoothConfig(
                batch_size=max(2, int(args.trust_region_batch_size)),
                initial_radius=max(0.05, float(args.vns_base_sigma)),
                min_radius=1e-3,
                max_radius=1.5,
                radius_expand=1.25,
                radius_shrink=0.65,
                include_center=True,
                score_mode="l1",
                random_seed=int(args.seed) + 1000 + int(_unit_id),
            ),
            name="nonsmooth_trust_region",
        )

    def pattern_factory(_unit_id: int = 0):
        return PatternSearchAdapter(
            PatternSearchConfig(
                max_directions=8,
                step_size=float(args.pattern_step_size),
                expansion=1.15,
                contraction=0.65,
                min_step=1e-3,
                objective_aggregation="sum",
            ),
            name="coordinate_pattern_refine",
        )

    return StrategyRouterAdapter(
        roles=(
            RoleSpec("global_pareto", nsga2_factory, n_units=1, weight=2.0),
            RoleSpec("archive_pressure", spea2_factory, n_units=1, weight=1.2),
            RoleSpec("exploration", de_factory, n_units=1, weight=1.0),
            RoleSpec("structure_refine", vns_factory, n_units=1, weight=1.4),
            RoleSpec("nonsmooth_refine", trust_region_factory, n_units=1, weight=1.1),
            RoleSpec("coordinate_refine", pattern_factory, n_units=1, weight=0.8),
        ),
        config=MultiStrategyConfig(
            total_batch_size=total_batch,
            objective_aggregation="sum",
            violation_penalty=1e6,
            adapt_weights=True,
            stagnation_boost=0.35,
            stagnation_window=3,
            phase_schedule=(("global", 2), ("hybrid", -1)),
            phase_roles={
                "global": ["global_pareto", "archive_pressure", "exploration"],
                "hybrid": [
                    "global_pareto",
                    "archive_pressure",
                    "exploration",
                    "structure_refine",
                    "nonsmooth_refine",
                    "coordinate_refine",
                ],
            },
            phase_weight_multipliers={
                "global": {"global_pareto": 1.5, "exploration": 1.25},
                "hybrid": {
                    "structure_refine": 1.35,
                    "nonsmooth_refine": 1.25,
                    "coordinate_refine": 1.1,
                },
            },
            control_rules=(
                MultiStrategyControlRule(
                    name="late_refinement",
                    when_dsl={"ge": ["$generation", 3]},
                    then={
                        "weight_multipliers": {
                            "structure_refine": 1.25,
                            "nonsmooth_refine": 1.25,
                            "coordinate_refine": 1.2,
                        }
                    },
                ),
            ),
            enable_regions=True,
            n_regions=4,
            region_overlap=0.15,
            region_update_interval=2,
            seeds_per_task=2,
            seeds_source="pareto",
        ),
        name="known_relation_symbolic_outer_multi_strategy",
    )


def build_outer_adapter(args: argparse.Namespace):
    return build_complex_adapter(args) if str(args.outer_adapter) == "complex" else build_vns_adapter(args)
