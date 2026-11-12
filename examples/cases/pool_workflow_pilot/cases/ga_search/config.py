"""种群容量、后代数量与母池种子数量分别声明。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    seed: int = 37
    source_count: int = 8
    population_size: int = 6
    max_steps: int = 10
    offspring_size: int = 4
    archive_source: str = "accepted"
    parallel_archive: bool = False
