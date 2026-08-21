from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from blackbase.project import CaseRunRequest
from nsgablack.core.base import BlackBoxProblem

try:
    from ..config import PhiBundleImageSearchConfig
except ImportError:  # direct case-local debug import
    from config import PhiBundleImageSearchConfig


PHI_FAMILIES: tuple[str, ...] = (
    "edge",
    "patch_pool",
    "patch_texture",
    "orthogonal_frequency",
    "moment",
    "region",
    "symmetry",
    "row_projection",
    "col_projection",
    "mass",
)

LANE_PARAMETER_SPECS: Mapping[str, tuple[str, ...]] = {
    "edge": ("edge_direction", "edge_scope", "edge_operator"),
    "patch_pool": ("patch_size", "patch_stride", "patch_pooling", "patch_region"),
    "patch_texture": ("patch_size", "patch_stride", "texture_operator", "patch_region"),
    "orthogonal_frequency": ("dct_band", "dct_orientation"),
    "moment": ("moment_axis", "moment_stat"),
    "region": ("region_mode",),
    "symmetry": ("symmetry_axis",),
    "row_projection": ("row_band",),
    "col_projection": ("col_band",),
    "mass": (),
}

BUDGET_FIELDS: tuple[str, ...] = (
    "representation_max_features",
    "representation_max_pair_abs_corr",
    "max_sources",
    "orth_max_pair_abs_corr",
    "candidate_keep_top",
)


def _clip_int(value: float, *, low: int, high: int) -> int:
    return int(np.clip(np.round(float(value)), int(low), int(high)))


def _clip_float(value: float, *, low: float, high: float) -> float:
    return float(np.clip(float(value), float(low), float(high)))


def _bucket(value: float, labels: tuple[Any, ...]) -> Any:
    if not labels:
        return ""
    idx = int(np.clip(np.floor(float(value) * len(labels)), 0, len(labels) - 1))
    return labels[idx]


def _typed_lane_from_genes(family: str, genes: Mapping[str, float]) -> dict[str, Any]:
    lane: dict[str, Any] = {"family": str(family), "enabled": True}
    if family == "edge":
        lane["edge_direction"] = _bucket(float(genes.get("edge_direction", 1.0)), ("horizontal", "vertical", "both"))
        lane["edge_scope"] = _bucket(float(genes.get("edge_scope", 1.0)), ("local", "global", "all"))
        lane["edge_operator"] = _bucket(float(genes.get("edge_operator", 1.0)), ("abs", "signed", "squared", "all"))
        lane["edge_mode"] = "all"
    elif family == "patch_pool":
        lane["patch_size"] = int(_bucket(float(genes.get("patch_size", 0.0)), (2, 4)))
        lane["patch_stride"] = _bucket(float(genes.get("patch_stride", 1.0)), (1, 2, 4, "all"))
        lane["patch_pooling"] = _bucket(float(genes.get("patch_pooling", 1.0)), ("sum", "mean", "max", "all"))
        lane["patch_region"] = _bucket(float(genes.get("patch_region", 1.0)), ("all", "center", "corner", "outer"))
    elif family == "patch_texture":
        lane["patch_size"] = int(_bucket(float(genes.get("patch_size", 0.0)), (2, 4)))
        lane["patch_stride"] = _bucket(float(genes.get("patch_stride", 1.0)), (1, 2, 4, "all"))
        lane["texture_operator"] = _bucket(float(genes.get("texture_operator", 1.0)), ("var", "std", "range", "all"))
        lane["patch_region"] = _bucket(float(genes.get("patch_region", 1.0)), ("all", "center", "corner", "outer"))
    elif family == "orthogonal_frequency":
        lane["dct_band"] = _bucket(float(genes.get("dct_band", 1.0)), ("low", "mid", "high", "all"))
        lane["dct_orientation"] = _bucket(float(genes.get("dct_orientation", 1.0)), ("row", "col", "diagonal", "all"))
    elif family == "moment":
        lane["moment_axis"] = _bucket(float(genes.get("moment_axis", 1.0)), ("row", "col", "both"))
        lane["moment_stat"] = _bucket(float(genes.get("moment_stat", 1.0)), ("center", "variance", "all"))
        lane["moment_mode"] = "all"
    elif family == "region":
        lane["region_mode"] = _bucket(float(genes.get("region_mode", 1.0)), ("center", "outer_ring", "all"))
    elif family == "symmetry":
        lane["symmetry_axis"] = _bucket(float(genes.get("symmetry_axis", 1.0)), ("left_right", "top_bottom", "all"))
    elif family == "row_projection":
        lane["row_band"] = _bucket(float(genes.get("row_band", 1.0)), ("top", "middle", "bottom", "all"))
    elif family == "col_projection":
        lane["col_band"] = _bucket(float(genes.get("col_band", 1.0)), ("left", "middle", "right", "all"))
    elif family == "mass":
        lane["mass_mode"] = "total"
    return lane


class PhiBundleImageSearchProblem(BlackBoxProblem):
    """Outer objective: search a bundle of symbolic image objectification lanes."""

    def __init__(self, cfg: PhiBundleImageSearchConfig, *, output_dir: str | Path) -> None:
        self.cfg = cfg
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.evaluation_records: list[dict[str, Any]] = []
        self._cache: dict[str, dict[str, Any]] = {}
        self.best_result: dict[str, Any] | None = None
        self.best_accuracy_result: dict[str, Any] | None = None
        self.best_score: float | None = None
        self._case_runtime: Any | None = None
        self.toggle_offset = 0
        self.typed_param_fields: tuple[tuple[str, str], ...] = tuple(
            (family, field)
            for family in PHI_FAMILIES
            for field in tuple(LANE_PARAMETER_SPECS.get(family, ()))
        )
        self.param_offset = len(PHI_FAMILIES)
        self.budget_offset = self.param_offset + len(self.typed_param_fields)
        dimension = self.budget_offset + len(BUDGET_FIELDS)
        bounds = {f"x{i}": [0.0, 1.0] for i in range(len(PHI_FAMILIES))}
        bounds.update({f"x{self.param_offset + i}": [0.0, 1.0] for i in range(len(self.typed_param_fields))})
        bounds.update(
            {
                f"x{self.budget_offset + 0}": [8.0, 64.0],
                f"x{self.budget_offset + 1}": [0.70, 0.995],
                f"x{self.budget_offset + 2}": [4.0, 24.0],
                f"x{self.budget_offset + 3}": [0.50, 0.90],
                f"x{self.budget_offset + 4}": [8.0, 120.0],
            }
        )
        super().__init__(
            name="PhiBundleImageSearchProblem",
            dimension=dimension,
            bounds=bounds,
            objectives=("classification_error", "redundancy", "complexity", "instability", "cost"),
        )

    def set_case_runtime(self, runtime: Any) -> None:
        self._case_runtime = runtime

    def decode_bundle(self, x: np.ndarray) -> dict[str, Any]:
        arr = np.asarray(x, dtype=float).reshape(self.dimension)
        toggles = arr[: len(PHI_FAMILIES)]
        raw_params = arr[self.param_offset : self.budget_offset]
        typed_params: dict[str, dict[str, float]] = {family: {} for family in PHI_FAMILIES}
        for (family, field), value in zip(self.typed_param_fields, raw_params):
            typed_params[str(family)][str(field)] = float(value)
        enabled = [
            _typed_lane_from_genes(family, typed_params.get(family, {}))
            for family, value in zip(PHI_FAMILIES, toggles)
            if float(value) >= 0.5
        ]
        if not enabled:
            top = np.argsort(-toggles)[:3]
            enabled = [_typed_lane_from_genes(PHI_FAMILIES[int(i)], typed_params.get(PHI_FAMILIES[int(i)], {})) for i in top]
        base = self.budget_offset
        return {
            "bundle_kind": "representation_formula_bundle",
            "lanes": tuple(enabled),
            "lane_parameterization": "typed_family_lane_genome_v3",
            "genome_layout": {
                "families": PHI_FAMILIES,
                "typed_param_fields": self.typed_param_fields,
                "budget_fields": BUDGET_FIELDS,
            },
            "representation_max_features": _clip_int(arr[base + 0], low=8, high=64),
            "representation_max_pair_abs_corr": _clip_float(arr[base + 1], low=0.70, high=0.995),
            "max_sources": _clip_int(arr[base + 2], low=4, high=24),
            "orth_max_pair_abs_corr": _clip_float(arr[base + 3], low=0.50, high=0.90),
            "representation_candidate_keep_top": _clip_int(arr[base + 4], low=8, high=120),
            "orth_candidate_keep_top": _clip_int(arr[base + 4], low=8, high=120),
        }

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        bundle = self.decode_bundle(candidate)
        key = hashlib.sha1(json.dumps(bundle, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
        cached = self._cache.get(key)
        if cached is not None:
            return np.asarray(cached["objectives"], dtype=float)

        label = f"eval_{len(self.evaluation_records):05d}_{key}"
        if self._case_runtime is None:
            raise RuntimeError(
                "phi_bundle_image_search requires an injected Case runtime; "
                "run it through its standard Project entry"
            )
        child = self._case_runtime.invoke(
            CaseRunRequest(
                project_name="phi_bundle_image_search",
                stage_name="bundle_evaluation",
                case_name="phi_bundle_image_evaluation",
                case_kind="trainer",
                resource_request={
                    "workers": 1,
                    "threads": 1,
                    "gpus": 0,
                    "backend": "local",
                    "compute_backend": "numpy",
                    "device": "cpu",
                },
                component_overrides={
                    "config": {
                        "dataset_key": str(self.cfg.dataset_key),
                        "train_ratio": float(self.cfg.train_ratio),
                        "seed": int(self.cfg.seed),
                        "max_rows": int(self.cfg.max_rows),
                    },
                    "bundle": bundle,
                    "label": label,
                },
                metadata={"bundle_digest": key},
            )
        )
        child.raise_for_failure("PhiBundle evaluation Case failed")
        payload = dict(child.output or {})
        if str(payload.get("protocol_type", "")) != "blackbase.trainer_result":
            raise TypeError("PhiBundle evaluation Case did not return TrainerResult")
        result = dict(dict(payload.get("report", {}) or {}).get("summary", {}) or {})
        objectives = np.asarray(result.get("objectives", (10.0, 10.0, 10.0, 10.0, 10.0)), dtype=float)
        record = {
            "label": label,
            "bundle_key": key,
            "bundle": bundle,
            "objectives": objectives.tolist(),
            "score": float(np.sum(objectives)),
            "metrics": dict(result.get("metrics", {}) or {}),
            "representation_report": dict(result.get("representation_report", {}) or {}),
            "source_report": dict(result.get("source_report", {}) or {}),
            "artifact_dir": "",
            "child_case_run": child.request.identity.as_dict(),
            "status": str(result.get("status", "")),
        }
        self.evaluation_records.append(record)
        self._cache[key] = record
        score = float(record["score"])
        if self.best_score is None or score < float(self.best_score):
            self.best_score = score
            self.best_result = dict(record)
        accuracy = float(record.get("metrics", {}).get("best_accuracy", 0.0) or 0.0)
        current_accuracy = 0.0
        if self.best_accuracy_result is not None:
            current_accuracy = float(self.best_accuracy_result.get("metrics", {}).get("best_accuracy", 0.0) or 0.0)
        if self.best_accuracy_result is None or accuracy > current_accuracy:
            self.best_accuracy_result = dict(record)
        return objectives

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        bundle = self.decode_bundle(candidate)
        lane_count = len(tuple(bundle.get("lanes", ())))
        selected_features = int(bundle.get("representation_max_features", 0))
        max_sources = int(bundle.get("max_sources", 0))
        return np.asarray(
            [
                max(0.0, 1.0 - float(lane_count)),
                max(0.0, float(max_sources - selected_features)),
            ],
            dtype=float,
        )


__all__ = ["BUDGET_FIELDS", "LANE_PARAMETER_SPECS", "PHI_FAMILIES", "PhiBundleImageSearchProblem"]
