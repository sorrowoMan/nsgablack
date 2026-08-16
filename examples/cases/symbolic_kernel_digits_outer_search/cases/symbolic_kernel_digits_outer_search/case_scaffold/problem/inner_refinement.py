from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from nsgablack.adapters import TrustRegionDFOAdapter, TrustRegionDFOConfig
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from blackbase.resources import ResourceAllocator, ResourceOffer, ResourcePolicy, ResourceRequest
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, UniformInitializer

from ..config import SymbolicKernelDigitsOuterSearchConfig


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


def _missing_inner_case(name: str):
    raise RuntimeError(
        f"Missing inner standard Case: {name}. Restore it as a Project/Case scaffold "
        "and call it through the formal build_solver/resource_context surface; "
        "legacy direct demo imports are no longer supported."
    )

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
    weights = np.asarray(coefficients, dtype=float).reshape(-1)
    return normalize_kernel(weights), weights


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


class SymbolicKernelDigitsRefinementProblem(BlackBoxProblem):
    def __init__(
        self,
        cfg: SymbolicKernelDigitsOuterSearchConfig,
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
            name="SymbolicKernelDigitsRefinementProblem",
            dimension=self.coeff_dim,
            bounds=bounds,
            objectives=("refinement_score",),
        )

    def _refinement_score(self, metrics: Mapping[str, Any]) -> float:
        test_error = 1.0 - float(metrics.get("test_accuracy", 0.0) or 0.0)
        gap = max(0.0, float(metrics.get("generalization_gap", 1.0) or 1.0))
        return (
            float(self.cfg.refinement_test_error_weight) * test_error
            + float(self.cfg.refinement_gap_weight) * gap
        )

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        _ = candidate
        _ensure_mlblack_path()
        _missing_inner_case("symbolic_kernel_digits_classification")

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        _ = candidate
        return np.zeros(0, dtype=float)


def build_refinement_pipeline(problem: SymbolicKernelDigitsRefinementProblem) -> RepresentationPipeline:
    low = np.asarray([problem.bounds[f"x{i}"][0] for i in range(problem.dimension)], dtype=float)
    high = np.asarray([problem.bounds[f"x{i}"][1] for i in range(problem.dimension)], dtype=float)
    return RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        repair=ClipRepair(low=low, high=high),
    )


def run_inner_refinement(
    cfg: SymbolicKernelDigitsOuterSearchConfig,
    *,
    structure_bundle: Mapping[str, Any],
    output_dir: str | Path,
    label_prefix: str,
    seed: int,
) -> dict[str, Any]:
    if str(cfg.refinement_mode).strip().lower() != "trust_region_dfo":
        raise ValueError("symbolic kernel digits outer search currently requires refinement_mode='trust_region_dfo'")
    problem = SymbolicKernelDigitsRefinementProblem(
        cfg,
        structure_bundle=structure_bundle,
        output_dir=output_dir,
        label_prefix=label_prefix,
    )
    pipeline = build_refinement_pipeline(problem)
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
        name="symbolic_kernel_digits_inner_trust_region_dfo",
    )
    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(max(1, int(cfg.refinement_steps)))
    solver.set_random_seed(int(seed))
    solver.run(max_steps=max(1, int(cfg.refinement_steps)))
    final_candidate = getattr(adapter, "_center", None)
    if final_candidate is not None:
        problem.evaluate(np.asarray(final_candidate, dtype=float))
    best_record = dict(problem.best_result or {})
    return {
        "mode": "trust_region_dfo",
        "solver_name": adapter.name,
        "seed": int(seed),
        "evaluation_count": len(problem.evaluation_records),
        "best_score": None if problem.best_score is None else float(problem.best_score),
        "best_result": best_record,
        "best_bundle": dict(best_record.get("bundle", {}) or {}),
        "best_metrics": dict(best_record.get("metrics", {}) or {}),
    }


__all__ = [
    "SymbolicKernelDigitsRefinementProblem",
    "build_component_overrides",
    "build_full_bundle",
    "normalize_kernel",
    "run_inner_refinement",
]
