from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Mapping

from nsgablack.adapters import (
    GradientDescentAdapter,
    GradientDescentConfig,
    TrustRegionDFOAdapter,
    TrustRegionDFOConfig,
)
from nsgablack.core.composable_solver import ComposableSolver

from pipeline.main import build_pipeline
from problem.main import LearnableConvRefinementProblem


class LearnableConvRefinementSolver(ComposableSolver):
    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.problem.set_case_runtime(runtime)
        return self

    def export_case_result(self, raw_output):
        result = super().export_case_result(raw_output)
        return replace(
            result,
            metadata={
                **dict(result.metadata or {}),
                "refinement": self.problem.result_summary(
                    mode=str(self.problem.cfg.refinement_mode),
                    solver_name=str(self.adapter.name),
                ),
            },
        )


def build_solver(
    config=None,
    *,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
):
    del config
    overrides = dict(component_overrides or {})
    default_config = {
        "refinement_mode": "gradient_descent",
        "refinement_coeff_bound": 2.0,
        "refinement_steps": 1,
        "refinement_gradient_learning_rate": 0.2,
        "refinement_gradient_epsilon": 0.05,
        "refinement_gradient_max_directions": 1,
        "refinement_gradient_lr_growth": 1.05,
        "refinement_gradient_lr_decay": 0.7,
        "refinement_gradient_min_lr": 1.0e-5,
        "refinement_trust_region_batch_size": 2,
        "refinement_trust_region_initial_radius": 0.7,
        "refinement_trust_region_min_radius": 1.0e-3,
        "refinement_trust_region_max_radius": 2.0,
        "refinement_trust_region_radius_expand": 1.35,
        "refinement_trust_region_radius_shrink": 0.7,
        "inner_threads": 1,
        "inner_compute_backend": "numpy",
        "inner_device": "cpu",
        "inner_train_ratio": 0.75,
        "inner_n_samples": 96,
        "inner_image_height": 8,
        "inner_image_width": 8,
        "inner_noise_scale": 0.06,
        "inner_trainer_key": "ridge",
        "inner_trainer_l2": 0.05,
        "refinement_test_rmse_weight": 1.0,
        "refinement_gap_weight": 1.0,
        "seed": 42,
    }
    default_bundle = {
        "component_path": "pipeline.learnable_conv1d",
        "input_layout": "image2d",
        "image_shape": [8, 8],
        "kernel_shape": [3, 3],
        "symbolic_kernel_object": {
            "kind": "symbolic_kernel",
            "kernel_shape": [3, 3],
            "basis_terms": ["identity", "sobel_x"],
        },
        "include_input": False,
        "stride": 1,
        "stride_shape": [1, 1],
        "padding": "same",
        "pooling": "stats",
        "output_mode": "pooled",
        "update_mode": "check",
    }
    cfg = SimpleNamespace(**dict(overrides.pop("config", default_config)))
    structure_bundle = dict(overrides.pop("structure_bundle", default_bundle))
    output_dir = str(overrides.pop("output_dir", "runs/learnable_conv_refinement"))
    label_prefix = str(overrides.pop("label_prefix", "standalone"))
    seed = int(overrides.pop("seed", 42))
    if overrides:
        raise ValueError(f"unsupported refinement overrides: {sorted(overrides)}")

    problem = LearnableConvRefinementProblem(
        cfg,
        structure_bundle=structure_bundle,
        output_dir=output_dir,
        label_prefix=label_prefix,
    )
    mode = str(cfg.refinement_mode).strip().lower()
    if mode == "gradient_descent":
        adapter = GradientDescentAdapter(
            GradientDescentConfig(
                learning_rate=float(cfg.refinement_gradient_learning_rate),
                epsilon=float(cfg.refinement_gradient_epsilon),
                max_directions=max(1, int(cfg.refinement_gradient_max_directions)),
                lr_growth=float(cfg.refinement_gradient_lr_growth),
                lr_decay=float(cfg.refinement_gradient_lr_decay),
                min_lr=float(cfg.refinement_gradient_min_lr),
                objective_aggregation="sum",
            ),
            name="learnable_conv_inner_gradient_descent",
        )
    elif mode == "trust_region_dfo":
        adapter = TrustRegionDFOAdapter(
            TrustRegionDFOConfig(
                batch_size=max(2, int(cfg.refinement_trust_region_batch_size)),
                initial_radius=float(cfg.refinement_trust_region_initial_radius),
                min_radius=float(cfg.refinement_trust_region_min_radius),
                max_radius=float(cfg.refinement_trust_region_max_radius),
                radius_expand=float(cfg.refinement_trust_region_radius_expand),
                radius_shrink=float(cfg.refinement_trust_region_radius_shrink),
                include_center=True,
                random_seed=seed,
            ),
            name="learnable_conv_inner_trust_region_dfo",
        )
    else:
        raise ValueError(f"unsupported refinement_mode={cfg.refinement_mode!r}")

    solver = LearnableConvRefinementSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=build_pipeline(problem),
    )
    solver.set_max_steps(max(1, int(cfg.refinement_steps)))
    solver.set_random_seed(seed)
    solver.set_resource_context(resource_context)
    return solver


__all__ = ["LearnableConvRefinementSolver", "build_solver"]
