"""可选的池驱动搜索装配；在 build_solver 中显式选择，不自动启用。"""
from nsgablack.adapters import (
    NSGA2Adapter, NSGA3Adapter, PoolSearchAdapter, PoolSearchSpec,
    SimulatedAnnealingAdapter,
)


def build_pool_adapter(population_size=100, *, stagnation_steps=20, recovery_steps=5):
    return PoolSearchAdapter(
        producer=SimulatedAnnealingAdapter(name="seed_sa", batch_size=2 * population_size - 1, random_seed=7),
        searches=[
            PoolSearchSpec(NSGA2Adapter(name="population_a", population_size=population_size, offspring_size=population_size), population_size),
            PoolSearchSpec(NSGA3Adapter(name="population_b", population_size=population_size, offspring_size=population_size), population_size),
        ],
        stagnation_steps=stagnation_steps, recovery_steps=recovery_steps,
    )
