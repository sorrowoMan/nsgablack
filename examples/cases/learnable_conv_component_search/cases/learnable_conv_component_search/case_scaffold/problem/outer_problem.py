from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from ..config import LearnableConvComponentSearchConfig
from .inner_refinement import run_inner_refinement


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

def _toggle(value: float) -> bool:
    return float(value) >= 0.5


class LearnableConvComponentSearchProblem(BlackBoxProblem):
    def __init__(self, cfg: LearnableConvComponentSearchConfig, *, output_dir: str | Path) -> None:
        self.cfg = cfg
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.evaluation_records: list[dict[str, Any]] = []
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._structure_access_count: dict[str, int] = {}
        self.best_result: dict[str, Any] | None = None
        self.best_score: float | None = None
        self.max_kernel_shape = (5, 5)
        self.coeff_dims = int(self.max_kernel_shape[0] * self.max_kernel_shape[1])
        self.symbolic_basis_library = ("identity", "sobel_x", "sobel_y", "laplacian")
        dimension = 12
        bounds = {f"x{i}": [0.0, 1.0] for i in range(dimension)}
        super().__init__(
            name="LearnableConvComponentSearchProblem",
            dimension=dimension,
            bounds=bounds,
            objectives=("test_rmse", "generalization_gap", "feature_complexity", "kernel_recovery_penalty"),
        )

    @staticmethod
    def _typed_choice(value: float, labels: tuple[Any, ...]) -> Any:
        idx = int(np.clip(np.floor(float(value) * len(labels)), 0, len(labels) - 1))
        return labels[idx]

    def _embed_kernel(self, kernel: np.ndarray, kernel_shape: tuple[int, int]) -> np.ndarray:
        canvas = np.zeros(self.max_kernel_shape, dtype=float)
        block = np.asarray(kernel, dtype=float).reshape(kernel_shape)
        row_start = max(0, (self.max_kernel_shape[0] - int(kernel_shape[0])) // 2)
        col_start = max(0, (self.max_kernel_shape[1] - int(kernel_shape[1])) // 2)
        canvas[
            row_start : row_start + int(kernel_shape[0]),
            col_start : col_start + int(kernel_shape[1]),
        ] = block
        return canvas.reshape(-1)

    def _kernel_alignment_metrics(
        self,
        *,
        candidate_kernel: np.ndarray,
        candidate_shape: tuple[int, int],
        hidden_kernel: np.ndarray,
        hidden_shape: tuple[int, int],
    ) -> dict[str, float]:
        cand_embed = self._embed_kernel(candidate_kernel, candidate_shape)
        hidden_embed = self._embed_kernel(hidden_kernel, hidden_shape)
        diff = cand_embed - hidden_embed
        cand_norm = max(float(np.linalg.norm(cand_embed)), 1.0e-12)
        hidden_norm = max(float(np.linalg.norm(hidden_embed)), 1.0e-12)
        cosine = float(np.dot(cand_embed, hidden_embed) / (cand_norm * hidden_norm))
        return {
            "kernel_l2_distance": float(np.linalg.norm(diff)),
            "kernel_cosine_similarity": cosine,
        }

    def _kernel_recovery_penalty(self, kernel_alignment: dict[str, float]) -> float:
        cosine = float(kernel_alignment.get("kernel_cosine_similarity", -1.0) or -1.0)
        cosine = float(np.clip(cosine, -1.0, 1.0))
        return float(self.cfg.kernel_alignment_prior_weight) * (0.5 * (1.0 - cosine))

    def get_cache_summary(self) -> dict[str, Any]:
        requested = int(getattr(self, "evaluation_count", 0) or 0)
        unique = len(self.evaluation_records)
        return {
            "requested_evaluation_count": requested,
            "unique_structure_count": int(unique),
            "cache_hit_count": int(self._cache_hits),
            "cache_miss_count": int(self._cache_misses),
            "cache_hit_rate": (float(self._cache_hits) / float(requested)) if requested > 0 else 0.0,
            "most_requested_structure_key": (
                max(self._structure_access_count.items(), key=lambda item: item[1])[0]
                if self._structure_access_count
                else ""
            ),
            "max_structure_request_count": (
                max(self._structure_access_count.values()) if self._structure_access_count else 0
            ),
        }

    def decode_structure_bundle(self, x: np.ndarray) -> dict[str, Any]:
        arr = np.asarray(x, dtype=float).reshape(self.dimension)
        kernel_rows = int(self._typed_choice(arr[0], (2, 3, 5)))
        kernel_cols = int(self._typed_choice(arr[1], (2, 3, 5)))
        stride_shape = tuple(int(v) for v in self._typed_choice(arr[2], ((1, 1), (1, 2), (2, 2))))
        padding = str(self._typed_choice(arr[3], ("same", "valid", "zero")))
        pooling = str(self._typed_choice(arr[4], ("stats", "mean_max", "mean", "max")))
        output_mode = str(self._typed_choice(arr[5], ("pooled", "flattened_features")))
        include_input = bool(_toggle(arr[6]))
        basis_count = int(self._typed_choice(arr[7], (2, 3, 4)))
        basis_slots = [
            str(self._typed_choice(arr[8], self.symbolic_basis_library)),
            str(self._typed_choice(arr[9], self.symbolic_basis_library)),
            str(self._typed_choice(arr[10], self.symbolic_basis_library)),
            str(self._typed_choice(arr[11], self.symbolic_basis_library)),
        ]
        basis_terms: list[str] = []
        for term in basis_slots:
            if term not in basis_terms:
                basis_terms.append(term)
            if len(basis_terms) >= basis_count:
                break
        if len(basis_terms) < basis_count:
            for fallback in self.symbolic_basis_library:
                if fallback not in basis_terms:
                    basis_terms.append(str(fallback))
                if len(basis_terms) >= basis_count:
                    break
        kernel_shape = (int(kernel_rows), int(kernel_cols))
        symbolic_kernel_object = {
            "kind": "symbolic_kernel",
            "kernel_shape": list(kernel_shape),
            "basis_terms": list(basis_terms),
        }
        return {
            "component_path": "pipeline.learnable_conv1d",
            "input_layout": "image2d",
            "image_shape": (int(self.cfg.inner_image_height), int(self.cfg.inner_image_width)),
            "kernel_shape": kernel_shape,
            "symbolic_kernel_object": symbolic_kernel_object,
            "include_input": include_input,
            "stride": int(stride_shape[0]),
            "stride_shape": stride_shape,
            "padding": padding,
            "pooling": pooling,
            "output_mode": output_mode,
            "update_mode": f"outer_structure::{self.cfg.refinement_mode}",
        }

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        _ensure_mlblack_path()
        structure_bundle = self.decode_structure_bundle(candidate)
        bundle_key = hashlib.sha1(json.dumps(structure_bundle, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        self._structure_access_count[bundle_key] = int(self._structure_access_count.get(bundle_key, 0)) + 1
        cached = self._cache.get(bundle_key)
        if cached is not None:
            self._cache_hits += 1
            return np.asarray(cached["objectives"], dtype=float)
        self._cache_misses += 1

        label = f"eval_{len(self.evaluation_records):04d}_{bundle_key}"
        eval_dir = self.output_dir / "evaluations" / label
        eval_dir.mkdir(parents=True, exist_ok=True)
        refinement_seed = int(self.cfg.seed) + int(bundle_key[:8], 16)
        refinement = run_inner_refinement(
            self.cfg,
            structure_bundle=structure_bundle,
            output_dir=eval_dir / "refinement",
            label_prefix=label,
            seed=refinement_seed,
        )
        best_inner = dict(refinement.get("best_result", {}) or {})
        bundle = dict(refinement.get("best_bundle", {}) or {})
        metrics = dict(refinement.get("best_metrics", {}) or {})
        dataset_metadata = dict(best_inner.get("dataset_metadata", {}) or {})
        output_dim = int(best_inner.get("pipeline_output_dim", 0) or 0)
        input_dim = max(1, int(dataset_metadata.get("input_dim", self.cfg.inner_input_dim)))
        hidden_kernel = np.asarray(tuple(dataset_metadata.get("hidden_kernel", ()) or ()), dtype=float).reshape(-1)
        hidden_shape = tuple(int(v) for v in tuple(dataset_metadata.get("hidden_kernel_shape", (3, 3)) or (3, 3)))
        kernel_alignment = self._kernel_alignment_metrics(
            candidate_kernel=np.asarray(bundle["coefficients"], dtype=float),
            candidate_shape=tuple(int(v) for v in tuple(bundle["kernel_shape"])),
            hidden_kernel=hidden_kernel,
            hidden_shape=hidden_shape,
        )
        symbolic_term_count = len(tuple(dict(bundle.get("symbolic_kernel_object", {}) or {}).get("basis_terms", ()) or ()))
        objectives = np.asarray(
            [
                float(metrics.get("test_rmse", 10.0) or 10.0),
                max(0.0, float(metrics.get("generalization_gap", 10.0) or 10.0)),
                (
                    float(output_dim) / float(input_dim)
                    + float(np.prod(bundle["kernel_shape"])) / float(self.coeff_dims)
                    + float(symbolic_term_count) / float(len(self.symbolic_basis_library))
                ),
                self._kernel_recovery_penalty(kernel_alignment),
            ],
            dtype=float,
        )
        legacy_score = float(np.sum(objectives[:3]))
        record = {
            "label": label,
            "bundle_key": bundle_key,
            "search_mode": f"outer_symbolic_kernel_object_inner_{self.cfg.refinement_mode}",
            "structure_bundle": structure_bundle,
            "bundle": bundle,
            "objectives": objectives.tolist(),
            "score": float(np.sum(objectives)),
            "legacy_score": legacy_score,
            "metrics": metrics,
            "kernel_alignment": kernel_alignment,
            "kernel_recovery_penalty": float(objectives[3]),
            "dataset_metadata": dataset_metadata,
            "pipeline_state": dict(best_inner.get("pipeline_state", {}) or {}),
            "pipeline_output_dim": int(output_dim),
            "resource_context": dict(best_inner.get("resource_context", {}) or {}),
            "refinement": refinement,
            "output_dir": str(best_inner.get("output_dir", eval_dir)),
            "artifacts": dict(best_inner.get("artifacts", {}) or {}),
            "status": "ok",
        }
        self.evaluation_records.append(record)
        self._cache[bundle_key] = record
        score = float(record["score"])
        if self.best_score is None or score < float(self.best_score):
            self.best_score = score
            self.best_result = dict(record)
        return objectives

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        _ = candidate
        return np.zeros(0, dtype=float)


__all__ = ["LearnableConvComponentSearchProblem"]
