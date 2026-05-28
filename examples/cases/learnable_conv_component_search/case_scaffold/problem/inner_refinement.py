from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from nsgablack.adapters import (
    GradientDescentAdapter,
    GradientDescentConfig,
    TrustRegionDFOAdapter,
    TrustRegionDFOConfig,
)
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.solver_manager import ResourceAllocator, ResourceOffer, ResourcePolicy, ResourceRequest
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, UniformInitializer

from ..config import LearnableConvComponentSearchConfig


def _ensure_mlblack_path() -> None:
    repo_root = None
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists() and (parent / "__init__.py").exists():
            repo_root = parent
            break
    if repo_root is None:
        return
    mlblack_root = repo_root.parent / "mlblack"
    if mlblack_root.exists() and str(mlblack_root) not in sys.path:
        sys.path.insert(0, str(mlblack_root))


def normalize_kernel(coefficients: np.ndarray) -> np.ndarray:
    flat = np.asarray(coefficients, dtype=float).reshape(-1)
    norm = max(float(np.linalg.norm(flat)), 1.0e-12)
    return flat / norm


def _compile_symbolic_kernel_if_needed(
    structure_bundle: Mapping[str, Any],
    coefficients: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None]:
    symbolic_kernel_object = dict(structure_bundle.get("symbolic_kernel_object", {}) or {})
    if not symbolic_kernel_object:
        return normalize_kernel(coefficients), None
    _ensure_mlblack_path()
    from examples.cases.learnable_conv_component_demo.case_scaffold.pipeline import compile_symbolic_kernel_object  # type: ignore

    weights = np.asarray(coefficients, dtype=float).reshape(-1)
    compiled = np.asarray(compile_symbolic_kernel_object(symbolic_kernel_object, weights), dtype=float).reshape(-1)
    return normalize_kernel(compiled), weights


def build_full_bundle(
    structure_bundle: Mapping[str, Any],
    coefficients: np.ndarray,
    *,
    update_mode: str,
) -> dict[str, Any]:
    bundle = dict(structure_bundle)
    compiled, symbolic_weights = _compile_symbolic_kernel_if_needed(structure_bundle, coefficients)
    if symbolic_weights is not None:
        bundle["symbolic_kernel_weights"] = symbolic_weights.tolist()
    bundle["coefficients"] = compiled.tolist()
    bundle["update_mode"] = str(update_mode)
    return bundle


def build_component_overrides(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    payload = {
        "coefficients": list(bundle["coefficients"]),
        "input_layout": str(bundle["input_layout"]),
        "image_shape": list(bundle["image_shape"]),
        "kernel_shape": list(bundle["kernel_shape"]),
        "include_input": bool(bundle["include_input"]),
        "stride": int(bundle["stride"]),
        "stride_shape": list(bundle["stride_shape"]),
        "padding": str(bundle["padding"]),
        "pooling": str(bundle["pooling"]),
        "output_mode": str(bundle["output_mode"]),
        "update_mode": str(bundle["update_mode"]),
    }
    symbolic_kernel_object = dict(bundle.get("symbolic_kernel_object", {}) or {})
    if symbolic_kernel_object:
        payload["symbolic_kernel_object"] = symbolic_kernel_object
        payload["symbolic_kernel_weights"] = list(bundle.get("symbolic_kernel_weights", []))
    return {str(bundle["component_path"]): payload}


def _accelerator_tokens(device: str) -> tuple[str, ...]:
    key = str(device or "").strip().lower()
    if key in {"", "auto", "cpu", "none", "null"}:
        return tuple()
    if key == "cuda" or key.startswith("cuda:") or key == "mps":
        return (key,)
    if key.isdigit():
        return (f"cuda:{int(key)}",)
    return tuple()


class LearnableConvCoefficientRefinementProblem(BlackBoxProblem):
    def __init__(
        self,
        cfg: LearnableConvComponentSearchConfig,
        *,
        structure_bundle: Mapping[str, Any],
        output_dir: str | Path,
        label_prefix: str,
    ) -> None:
        self.cfg = cfg
        self.structure_bundle = dict(structure_bundle)
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.label_prefix = str(label_prefix)
        symbolic_kernel_object = dict(self.structure_bundle.get("symbolic_kernel_object", {}) or {})
        if symbolic_kernel_object:
            self.coeff_dim = len(tuple(symbolic_kernel_object.get("basis_terms", ()) or ()))
        else:
            self.coeff_dim = int(np.prod(tuple(self.structure_bundle["kernel_shape"])))
        self.evaluation_records: list[dict[str, Any]] = []
        self._cache: dict[str, dict[str, Any]] = {}
        self.best_result: dict[str, Any] | None = None
        self.best_score: float | None = None
        self.resource_allocator = ResourceAllocator(
            offer=ResourceOffer(
                threads=max(1, int(cfg.inner_threads)),
                backend=str(cfg.inner_execution_backend),
                device_tokens=_accelerator_tokens(str(cfg.inner_device)),
            ),
            policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
        )
        bounds = {f"x{i}": [-float(cfg.refinement_coeff_bound), float(cfg.refinement_coeff_bound)] for i in range(self.coeff_dim)}
        super().__init__(
            name="LearnableConvCoefficientRefinementProblem",
            dimension=self.coeff_dim,
            bounds=bounds,
            objectives=("refinement_score",),
        )

    def _refinement_score(self, metrics: Mapping[str, Any]) -> float:
        test_rmse = float(metrics.get("test_rmse", 10.0) or 10.0)
        gap = max(0.0, float(metrics.get("generalization_gap", 10.0) or 10.0))
        return (
            float(self.cfg.refinement_test_rmse_weight) * test_rmse
            + float(self.cfg.refinement_gap_weight) * gap
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        _ensure_mlblack_path()
        from examples.cases.learnable_conv_component_demo.build_solver import (  # type: ignore
            LearnableConvComponentDemoConfig,
            run_learnable_conv_component_demo,
        )

        candidate = normalize_kernel(np.asarray(x, dtype=float).reshape(self.dimension))
        bundle = build_full_bundle(
            self.structure_bundle,
            candidate,
            update_mode=f"inner_{self.cfg.refinement_mode}",
        )
        key = hashlib.sha1(json.dumps(bundle, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        cached = self._cache.get(key)
        if cached is not None:
            return np.asarray(cached["objectives"], dtype=float)

        label = f"{self.label_prefix}_inner_{len(self.evaluation_records):04d}_{key}"
        eval_dir = self.output_dir / label
        eval_dir.mkdir(parents=True, exist_ok=True)
        component_overrides = build_component_overrides(bundle)
        lease = self.resource_allocator.acquire(
            ResourceRequest(
                threads=int(self.cfg.inner_threads),
                backend=str(self.cfg.inner_execution_backend),
                label=label,
                device_tokens=_accelerator_tokens(str(self.cfg.inner_device)),
            ),
            owner_id=label,
            scope="nsgablack_outer_eval.mlblack_inner",
        )
        resource_context = lease.resource_context(
            compute_backend=str(self.cfg.inner_compute_backend),
            device=str(self.cfg.inner_device),
            execution_backend=str(self.cfg.inner_execution_backend),
            namespace=f"nsgablack.learnable_conv_component_search.{label}",
        )
        inner_cfg = LearnableConvComponentDemoConfig(
            output_dir=str(eval_dir),
            seed=int(self.cfg.seed),
            train_ratio=float(self.cfg.inner_train_ratio),
            dataset_kind="image2d",
            n_samples=int(self.cfg.inner_n_samples),
            input_dim=int(self.cfg.inner_input_dim),
            image_height=int(self.cfg.inner_image_height),
            image_width=int(self.cfg.inner_image_width),
            noise_scale=float(self.cfg.inner_noise_scale),
            trainer_key=str(self.cfg.inner_trainer_key),
            trainer_l2=float(self.cfg.inner_trainer_l2),
            resource_execution_backend=str(self.cfg.inner_execution_backend),
            resource_compute_backend=str(self.cfg.inner_compute_backend),
            resource_device=str(self.cfg.inner_device),
            resource_threads=int(self.cfg.inner_threads),
        )
        try:
            result = run_learnable_conv_component_demo(
                inner_cfg,
                suite_id=label,
                component_overrides=component_overrides,
                output_dir=eval_dir,
                resource_context=resource_context,
            )
        finally:
            self.resource_allocator.release(lease)
        summary = dict(result.get("summary", {}) or {})
        metrics = dict(summary.get("metrics", {}) or {})
        score = self._refinement_score(metrics)
        objectives = np.asarray([score], dtype=float)
        record = {
            "label": label,
            "bundle": bundle,
            "component_overrides": component_overrides,
            "objectives": objectives.tolist(),
            "score": float(score),
            "metrics": metrics,
            "pipeline_state": dict(summary.get("pipeline_state", {}) or {}),
            "pipeline_output_dim": int(summary.get("pipeline_output_dim", 0) or 0),
            "dataset_metadata": dict(summary.get("dataset_metadata", {}) or {}),
            "resource_context": dict(summary.get("resource_context", {}) or {}),
            "resource_lease": lease.as_dict(),
            "inner_config": asdict(inner_cfg),
            "output_dir": str(result.get("output_dir")),
            "artifacts": dict(result.get("artifacts", {}) or {}),
            "status": "ok",
        }
        self.evaluation_records.append(record)
        self._cache[key] = record
        if self.best_score is None or float(score) < float(self.best_score):
            self.best_score = float(score)
            self.best_result = dict(record)
        return objectives

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        _ = x
        return np.zeros(0, dtype=float)


def build_refinement_pipeline(problem: LearnableConvCoefficientRefinementProblem) -> RepresentationPipeline:
    low = np.asarray([problem.bounds[f"x{i}"][0] for i in range(problem.dimension)], dtype=float)
    high = np.asarray([problem.bounds[f"x{i}"][1] for i in range(problem.dimension)], dtype=float)
    return RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        repair=ClipRepair(low=low, high=high),
    )


def run_inner_refinement(
    cfg: LearnableConvComponentSearchConfig,
    *,
    structure_bundle: Mapping[str, Any],
    output_dir: str | Path,
    label_prefix: str,
    seed: int,
) -> dict[str, Any]:
    mode = str(cfg.refinement_mode).strip().lower()
    problem = LearnableConvCoefficientRefinementProblem(
        cfg,
        structure_bundle=structure_bundle,
        output_dir=output_dir,
        label_prefix=label_prefix,
    )
    pipeline = build_refinement_pipeline(problem)
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
                random_seed=int(seed),
            ),
            name="learnable_conv_inner_trust_region_dfo",
        )
    else:
        raise ValueError(f"Unsupported refinement_mode={cfg.refinement_mode!r}")

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(max(1, int(cfg.refinement_steps)))
    solver.set_random_seed(int(seed))
    solver.run(max_steps=max(1, int(cfg.refinement_steps)))

    final_candidate = None
    if mode == "gradient_descent":
        final_candidate = getattr(adapter, "current_x", None)
    else:
        final_candidate = getattr(adapter, "_center", None)
    if final_candidate is not None:
        problem.evaluate(np.asarray(final_candidate, dtype=float))

    best_record = dict(problem.best_result or {})
    return {
        "mode": mode,
        "solver_name": adapter.name,
        "seed": int(seed),
        "evaluation_count": len(problem.evaluation_records),
        "best_score": None if problem.best_score is None else float(problem.best_score),
        "best_result": best_record,
        "best_bundle": dict(best_record.get("bundle", {}) or {}),
        "best_metrics": dict(best_record.get("metrics", {}) or {}),
    }


__all__ = [
    "LearnableConvCoefficientRefinementProblem",
    "build_component_overrides",
    "build_full_bundle",
    "normalize_kernel",
    "run_inner_refinement",
]
