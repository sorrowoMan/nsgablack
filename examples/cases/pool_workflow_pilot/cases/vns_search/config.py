"""规模与随机种子；母池种子数量不等于池容量。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    seed: int = 31
    source_count: int = 3
    max_steps: int = 10
    batch_size: int = 3
