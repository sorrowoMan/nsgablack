from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolicKernelDigitsOuterSearchConfig:
    output_dir: str = "runs/symbolic_kernel_digits_outer_search"
    seed: int = 42
    pop_size: int = 6
    offspring_size: int = 6
    generations: int = 2
    mutation_sigma: float = 0.18
    crossover_rate: float = 0.9
    inner_dataset_key: str = "digits"
    inner_train_ratio: float = 0.75
    inner_max_rows: int = 1797
    inner_trainer_key: str = "mlp_torch"
    inner_trainer_l2: float = 0.05
    inner_mlp_hidden_dims: tuple[int, ...] = (128, 64)
    inner_mlp_epochs: int = 50
    inner_mlp_batch_size: int = 128
    inner_mlp_lr: float = 1.0e-3
    inner_mlp_weight_decay: float = 1.0e-4
    inner_compute_backend: str = "torch"
    inner_device: str = "auto"
    inner_execution_backend: str = "serial"
    inner_threads: int = 1
    outer_accuracy_weight: float = 1.0
    outer_gap_weight: float = 0.12
    outer_complexity_weight: float = 0.02
    outer_prior_weight: float = 0.01
    refinement_mode: str = "trust_region_dfo"
    refinement_steps: int = 3
    refinement_coeff_bound: float = 2.0
    refinement_test_error_weight: float = 1.0
    refinement_gap_weight: float = 0.75
    refinement_trust_region_batch_size: int = 6
    refinement_trust_region_initial_radius: float = 0.7
    refinement_trust_region_min_radius: float = 1.0e-3
    refinement_trust_region_max_radius: float = 2.0
    refinement_trust_region_radius_expand: float = 1.35
    refinement_trust_region_radius_shrink: float = 0.7


__all__ = ["SymbolicKernelDigitsOuterSearchConfig"]
