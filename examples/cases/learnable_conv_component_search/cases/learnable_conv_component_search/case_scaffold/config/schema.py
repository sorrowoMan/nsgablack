from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearnableConvComponentSearchConfig:
    output_dir: str = "runs/learnable_conv_component_search"
    seed: int = 42
    pop_size: int = 4
    offspring_size: int = 2
    generations: int = 1
    mutation_sigma: float = 0.18
    crossover_rate: float = 0.9
    inner_train_ratio: float = 0.75
    inner_n_samples: int = 96
    inner_input_dim: int = 64
    inner_image_height: int = 8
    inner_image_width: int = 8
    inner_noise_scale: float = 0.06
    inner_trainer_key: str = "ridge"
    inner_trainer_l2: float = 0.05
    inner_compute_backend: str = "numpy"
    inner_device: str = "cpu"
    inner_execution_backend: str = "serial"
    inner_threads: int = 1
    refinement_mode: str = "gradient_descent"
    refinement_steps: int = 1
    refinement_coeff_bound: float = 2.0
    refinement_test_rmse_weight: float = 1.0
    refinement_gap_weight: float = 1.0
    kernel_alignment_prior_weight: float = 1.0
    refinement_gradient_learning_rate: float = 0.35
    refinement_gradient_epsilon: float = 0.05
    refinement_gradient_max_directions: int = 1
    refinement_gradient_lr_growth: float = 1.05
    refinement_gradient_lr_decay: float = 0.7
    refinement_gradient_min_lr: float = 1.0e-5
    refinement_trust_region_batch_size: int = 6
    refinement_trust_region_initial_radius: float = 0.7
    refinement_trust_region_min_radius: float = 1.0e-3
    refinement_trust_region_max_radius: float = 2.0
    refinement_trust_region_radius_expand: float = 1.35
    refinement_trust_region_radius_shrink: float = 0.7


__all__ = ["LearnableConvComponentSearchConfig"]
