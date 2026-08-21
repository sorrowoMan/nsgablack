from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from blackbase.project import CaseRunRequest
from nsgablack.core.base import BlackBoxProblem


def _normalize(values):
    flat = np.asarray(values, dtype=float).reshape(-1)
    return flat / max(float(np.linalg.norm(flat)), 1.0e-12)


def _basis(term: str, shape: tuple[int, int]) -> np.ndarray:
    rows, cols = shape
    rr = np.linspace(-1.0, 1.0, rows).reshape(rows, 1)
    cc = np.linspace(-1.0, 1.0, cols).reshape(1, cols)
    name = str(term).strip().lower()
    if name == "identity":
        raw = np.zeros(shape)
        raw[rows // 2, cols // 2] = 1.0
    elif name == "sobel_x":
        raw = np.repeat(cc, rows, axis=0) * np.exp(-2.0 * rr**2)
    elif name == "sobel_y":
        raw = np.repeat(rr, cols, axis=1) * np.exp(-2.0 * cc**2)
    elif name == "laplacian":
        radius = np.repeat(rr**2, cols, axis=1) + np.repeat(cc**2, rows, axis=0)
        raw = 1.0 - 2.5 * radius
        raw -= np.mean(raw)
    else:
        raise ValueError(f"unsupported symbolic basis term: {term!r}")
    return raw / max(float(np.linalg.norm(raw)), 1.0e-12)


class SymbolicKernelDigitsRefinementProblem(BlackBoxProblem):
    def __init__(self, cfg, *, structure_bundle, output_dir, label_prefix):
        self.cfg = cfg
        self.structure_bundle = dict(structure_bundle)
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.label_prefix = str(label_prefix)
        symbolic = dict(self.structure_bundle.get("symbolic_kernel_object", {}) or {})
        self.coeff_dim = len(tuple(symbolic.get("basis_terms", ()) or ()))
        self._case_runtime: Any | None = None
        self.evaluation_records: list[dict[str, Any]] = []
        self._cache: dict[str, dict[str, Any]] = {}
        self.best_result: dict[str, Any] | None = None
        self.best_score: float | None = None
        bound = float(cfg.refinement_coeff_bound)
        super().__init__(
            name="SymbolicKernelDigitsRefinementProblem",
            dimension=self.coeff_dim,
            bounds={f"x{i}": [-bound, bound] for i in range(self.coeff_dim)},
            objectives=("refinement_score",),
        )

    def set_case_runtime(self, runtime: Any) -> None:
        self._case_runtime = runtime

    def evaluate(self, candidate):
        if self._case_runtime is None:
            raise RuntimeError("refinement Problem did not receive the shared Case runtime")
        weights = _normalize(candidate)
        shape = tuple(int(v) for v in self.structure_bundle["kernel_shape"])
        terms = tuple(
            dict(self.structure_bundle.get("symbolic_kernel_object", {}) or {}).get(
                "basis_terms", ()
            )
            or ()
        )
        kernel = np.zeros(shape, dtype=float)
        for index, term in enumerate(terms):
            kernel += float(weights[index]) * _basis(str(term), shape)
        kernel = _normalize(kernel)
        bundle = dict(self.structure_bundle)
        bundle["coefficients"] = kernel.tolist()
        bundle["symbolic_kernel_weights"] = weights.tolist()
        bundle["update_mode"] = "inner_trust_region_dfo"
        key = hashlib.sha1(json.dumps(bundle, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        cached = self._cache.get(key)
        if cached is not None:
            return np.asarray(cached["objectives"], dtype=float)

        label = f"{self.label_prefix}_inner_{len(self.evaluation_records):04d}_{key}"
        child = self._case_runtime.invoke(
            CaseRunRequest(
                project_name="symbolic_kernel_digits_outer_search",
                stage_name="digits_training",
                case_name="symbolic_kernel_digits_training",
                case_kind="trainer",
                resource_request={
                    "workers": 1,
                    "threads": max(1, int(self.cfg.inner_threads)),
                    "gpus": 0,
                    "backend": "local",
                    "compute_backend": "numpy",
                    "device": "cpu",
                },
                component_overrides={
                    "config": {
                        "seed": int(self.cfg.seed),
                        "dataset_key": str(self.cfg.inner_dataset_key),
                        "train_ratio": float(self.cfg.inner_train_ratio),
                        "max_rows": int(self.cfg.inner_max_rows),
                        "trainer_key": str(self.cfg.inner_trainer_key),
                        "trainer_l2": float(self.cfg.inner_trainer_l2),
                    },
                    "bundle": bundle,
                    "label": label,
                },
                metadata={"candidate_digest": key},
            )
        )
        child.raise_for_failure("digits training Case failed")
        payload = dict(child.output or {})
        if str(payload.get("protocol_type", "")) != "blackbase.trainer_result":
            raise TypeError("digits training Case did not return TrainerResult")
        summary = dict(dict(payload.get("report", {}) or {}).get("summary", {}) or {})
        metrics = dict(summary.get("metrics", {}) or {})
        test_error = 1.0 - float(metrics.get("test_accuracy", 0.0) or 0.0)
        gap = max(0.0, float(metrics.get("generalization_gap", 1.0) or 1.0))
        score = (
            float(self.cfg.refinement_test_error_weight) * test_error
            + float(self.cfg.refinement_gap_weight) * gap
        )
        objectives = np.asarray([score], dtype=float)
        record = {
            "label": label,
            "bundle": bundle,
            "objectives": objectives.tolist(),
            "score": score,
            "metrics": metrics,
            "pipeline_state": dict(summary.get("pipeline_state", {}) or {}),
            "pipeline_output_dim": int(summary.get("pipeline_output_dim", 0) or 0),
            "dataset_metadata": dict(summary.get("dataset_metadata", {}) or {}),
            "resource_context": dict(summary.get("resource_context", {}) or {}),
            "artifacts": dict(payload.get("artifact_refs", {}) or {}),
            "child_case_run": child.request.identity.as_dict(),
            "status": "ok",
        }
        self.evaluation_records.append(record)
        self._cache[key] = record
        if self.best_score is None or score < self.best_score:
            self.best_score = score
            self.best_result = dict(record)
        return objectives

    def evaluate_constraints(self, candidate):
        del candidate
        return np.zeros(0, dtype=float)

    def result_summary(self, *, solver_name: str):
        best = dict(self.best_result or {})
        return {
            "mode": "trust_region_dfo",
            "solver_name": solver_name,
            "evaluation_count": len(self.evaluation_records),
            "best_score": self.best_score,
            "best_result": best,
            "best_bundle": dict(best.get("bundle", {}) or {}),
            "best_metrics": dict(best.get("metrics", {}) or {}),
        }


__all__ = ["SymbolicKernelDigitsRefinementProblem"]
