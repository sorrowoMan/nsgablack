"""Compose the public pool preparation/search/recovery/return state machine."""
from nsgablack.adapters import (
    NSGA2Adapter, SPEA2Adapter, PoolSearchAdapter, PoolSearchSpec,
    SimulatedAnnealingAdapter,
)
from nsgablack.representation import UniformInitializer, GaussianMutation, ContextGaussianMutation


def build_adapter(settings):
    # Separate mutable operator instances: no shared RNG or hidden aliasing.
    sa = SimulatedAnnealingAdapter(
        name="seed_and_recovery_sa", batch_size=settings.producer_batch_size,
        base_sigma=settings.sigma, initial_temperature=0.4, cooling_rate=0.9,
        initializer=UniformInitializer(low=-0.15, high=0.15),
        mutator=ContextGaussianMutation(base_sigma=settings.sigma),
    )
    searchers = [
        NSGA2Adapter(name="population_a", population_size=settings.population_size,
                     offspring_size=settings.offspring_size,
                     mutator=GaussianMutation(sigma=settings.sigma)),
        SPEA2Adapter(name="population_b", population_size=settings.population_size,
                     offspring_size=settings.offspring_size,
                     mutator=GaussianMutation(sigma=settings.sigma)),
    ]
    return PoolSearchAdapter(
        producer=sa,
        searches=[PoolSearchSpec(adapter, initial_count=settings.initial_count_per_population)
                  for adapter in searchers],
        stagnation_steps=settings.stagnation_steps, recovery_steps=settings.recovery_steps,
        restart_recovery=True, name="pooled_search",
    )
