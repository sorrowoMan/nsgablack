"""Multi-role exploration followed by serial refinement strategies."""

from __future__ import annotations

from nsgablack.adapters import (
    DEConfig,
    DifferentialEvolutionAdapter,
    MultiStrategyConfig,
    RoleSpec,
    SerialPhaseSpec,
    StrategyChainAdapter,
    StrategyRouterAdapter,
    TrustRegionDFOAdapter,
    TrustRegionDFOConfig,
    VNSAdapter,
    VNSConfig,
)


def _exploration_router() -> StrategyRouterAdapter:
    roles = (
        RoleSpec(
            name="neighborhood_explorer",
            adapter=lambda unit_id: VNSAdapter(
                VNSConfig(batch_size=2, k_max=2, base_sigma=0.18),
                name=f"explore_vns_{unit_id}",
            ),
            n_units=2,
            weight=2.0,
        ),
        RoleSpec(
            name="region_probe",
            adapter=lambda unit_id: TrustRegionDFOAdapter(
                TrustRegionDFOConfig(
                    batch_size=2,
                    initial_radius=0.3,
                    include_center=True,
                    random_seed=100 + unit_id,
                ),
                name=f"explore_tr_{unit_id}",
            ),
            n_units=1,
            weight=1.0,
        ),
    )
    return StrategyRouterAdapter(
        roles=roles,
        config=MultiStrategyConfig(
            total_batch_size=3,
            adapt_weights=False,
            phase_schedule=(("explore", -1),),
            phase_roles={"explore": ["neighborhood_explorer", "region_probe"]},
        ),
        name="multi_role_exploration",
    )


def build_topology_adapter() -> StrategyChainAdapter:
    return StrategyChainAdapter(
        phases=(
            SerialPhaseSpec("explore", _exploration_router(), steps=1),
            SerialPhaseSpec(
                "vns_refine",
                VNSAdapter(VNSConfig(batch_size=1, k_max=1, base_sigma=0.08)),
                steps=1,
            ),
            SerialPhaseSpec(
                "trust_region_refine",
                TrustRegionDFOAdapter(
                    TrustRegionDFOConfig(
                        batch_size=1,
                        initial_radius=0.15,
                        include_center=True,
                        random_seed=211,
                    )
                ),
                steps=1,
            ),
            SerialPhaseSpec(
                "de_refine",
                DifferentialEvolutionAdapter(
                    DEConfig(population_size=4, batch_size=1, differential_weight=0.6)
                ),
                steps=1,
            ),
        ),
        name="explore_then_refine",
    )


def describe_topology() -> dict:
    return {
        "controller": "StrategyChainAdapter",
        "phases": ["explore", "vns_refine", "trust_region_refine", "de_refine"],
        "exploration": {
            "controller": "StrategyRouterAdapter",
            "roles": {
                "neighborhood_explorer": {"units": 2, "adapter": "VNSAdapter"},
                "region_probe": {"units": 1, "adapter": "TrustRegionDFOAdapter"},
            },
        },
        "refinement": ["VNSAdapter", "TrustRegionDFOAdapter", "DifferentialEvolutionAdapter"],
    }
