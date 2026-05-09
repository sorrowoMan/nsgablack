from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhiBundleImageSearchConfig:
    dataset_key: str = "digits"
    train_ratio: float = 0.75
    seed: int = 42
    max_rows: int = 700
    pop_size: int = 8
    generations: int = 3
    offspring_size: int = 8
    mutation_sigma: float = 0.18
    crossover_rate: float = 0.9
    output_dir: str = "runs/phi_bundle_image_search"


__all__ = ["PhiBundleImageSearchConfig"]

