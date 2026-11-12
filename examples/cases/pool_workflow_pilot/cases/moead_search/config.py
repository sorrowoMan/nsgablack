"""方向数、提案批次与母池种子数量分别声明。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    seed: int = 37
    source_count: int = 8
    directions: int = 6
    max_steps: int = 10
    batch_size: int = 3
