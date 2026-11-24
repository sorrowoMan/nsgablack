"""Small deterministic settings that expose one full recovery cycle."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoConfig:
    seed: int = 23
    max_steps: int = 8
    initial_count_per_population: int = 3
    population_size: int = 3
    offspring_size: int = 2
    producer_batch_size: int = 3
    stagnation_steps: int = 1
    recovery_steps: int = 2
    sigma: float = 0.04

    def __post_init__(self):
        for name in ("max_steps", "initial_count_per_population", "population_size",
                     "offspring_size", "producer_batch_size", "stagnation_steps", "recovery_steps"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.population_size < 2 or self.sigma <= 0:
            raise ValueError("population_size >= 2 and sigma > 0 are required")
