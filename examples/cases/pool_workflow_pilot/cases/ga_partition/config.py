"""种群容量、后代数量与母池种子数量分别声明。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    seed: int = 37
    source_count: int = 100
    population_size: int = 100
    max_steps: int = 3
    offspring_size: int = 80
    working_pool: str | None = None
