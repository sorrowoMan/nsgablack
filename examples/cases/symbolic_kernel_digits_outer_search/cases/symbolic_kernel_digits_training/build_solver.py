from __future__ import annotations

from typing import Any, Mapping

from evaluation.trainer import SymbolicKernelDigitsTrainingCase


def build_solver(
    config=None,
    *,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
):
    del config
    overrides = dict(component_overrides or {})
    training_config = dict(
        overrides.pop(
            "config",
            {
                "seed": 42,
                "dataset_key": "digits",
                "train_ratio": 0.75,
                "max_rows": 320,
                "trainer_key": "ridge",
                "trainer_l2": 0.05,
            },
        )
    )
    bundle = dict(
        overrides.pop(
            "bundle",
            {
                "component_path": "pipeline.learnable_conv1d",
                "image_shape": [8, 8],
                "kernel_shape": [3, 3],
                "coefficients": [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                "symbolic_kernel_weights": [1.0],
                "include_input": True,
                "stride_shape": [1, 1],
                "padding": "same",
                "pooling": "stats",
                "output_mode": "pooled",
            },
        )
    )
    label = str(overrides.pop("label", "standalone"))
    if overrides:
        raise ValueError(f"unsupported digits training overrides: {sorted(overrides)}")
    return SymbolicKernelDigitsTrainingCase(
        config=training_config,
        bundle=bundle,
        label=label,
        resource_context=resource_context,
    )


__all__ = ["build_solver"]
