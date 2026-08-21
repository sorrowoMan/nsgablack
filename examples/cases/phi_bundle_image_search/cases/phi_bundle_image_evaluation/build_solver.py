from __future__ import annotations

from typing import Any, Mapping

from evaluation.trainer import PhiBundleEvaluationCase


def build_solver(
    config=None,
    *,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
):
    del config
    overrides = dict(component_overrides or {})
    evaluation_config = dict(
        overrides.pop(
            "config",
            {"dataset_key": "digits", "train_ratio": 0.75, "seed": 42, "max_rows": 320},
        )
    )
    bundle = dict(
        overrides.pop(
            "bundle",
            {
                "bundle_kind": "representation_formula_bundle",
                "lanes": [{"family": "mass", "enabled": True}],
                "representation_max_features": 16,
                "representation_max_pair_abs_corr": 0.95,
                "max_sources": 8,
                "orth_max_pair_abs_corr": 0.85,
                "representation_candidate_keep_top": 24,
                "orth_candidate_keep_top": 24,
            },
        )
    )
    label = str(overrides.pop("label", "standalone"))
    if overrides:
        raise ValueError(f"unsupported PhiBundle evaluation overrides: {sorted(overrides)}")
    return PhiBundleEvaluationCase(
        config=evaluation_config,
        bundle=bundle,
        label=label,
        resource_context=resource_context,
    )


__all__ = ["build_solver"]
