from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from blackbase.project import CaseRunRequest

from ..config import LearnableConvComponentSearchConfig


def normalize_kernel(coefficients: np.ndarray) -> np.ndarray:
    flat = np.asarray(coefficients, dtype=float).reshape(-1)
    norm = max(float(np.linalg.norm(flat)), 1.0e-12)
    return flat / norm


def build_full_bundle(
    structure_bundle: Mapping[str, Any],
    coefficients: np.ndarray,
    *,
    update_mode: str,
) -> dict[str, Any]:
    """Compile a refinement candidate into the stable ML component payload."""

    bundle = dict(structure_bundle)
    symbolic = dict(bundle.get("symbolic_kernel_object", {}) or {})
    raw = normalize_kernel(coefficients)
    if symbolic:
        bundle["symbolic_kernel_weights"] = raw.tolist()
        shape = tuple(int(v) for v in bundle.get("kernel_shape", (3, 3)))
        rows, cols = shape
        rr = np.linspace(-1.0, 1.0, rows).reshape(rows, 1)
        cc = np.linspace(-1.0, 1.0, cols).reshape(1, cols)
        kernel = np.zeros(shape, dtype=float)
        for index, term in enumerate(tuple(symbolic.get("basis_terms", ()) or ())):
            name = str(term).strip().lower()
            if name == "identity":
                basis = np.zeros(shape, dtype=float)
                basis[rows // 2, cols // 2] = 1.0
            elif name == "sobel_x":
                basis = np.repeat(cc, rows, axis=0) * np.exp(-2.0 * rr**2)
            elif name == "sobel_y":
                basis = np.repeat(rr, cols, axis=1) * np.exp(-2.0 * cc**2)
            elif name == "laplacian":
                radius = np.repeat(rr**2, cols, axis=1) + np.repeat(cc**2, rows, axis=0)
                basis = 1.0 - 2.5 * radius
                basis -= np.mean(basis)
            else:
                raise ValueError(f"unsupported symbolic kernel term: {term!r}")
            basis /= max(float(np.linalg.norm(basis)), 1.0e-12)
            kernel += float(raw[index]) * basis
        bundle["coefficients"] = normalize_kernel(kernel).tolist()
    else:
        bundle["coefficients"] = raw.tolist()
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
    symbolic = dict(bundle.get("symbolic_kernel_object", {}) or {})
    if symbolic:
        payload["symbolic_kernel_object"] = symbolic
        payload["symbolic_kernel_weights"] = list(
            bundle.get("symbolic_kernel_weights", ()) or ()
        )
    return {str(bundle["component_path"]): payload}


def run_inner_refinement(
    cfg: LearnableConvComponentSearchConfig,
    *,
    structure_bundle: Mapping[str, Any],
    output_dir: str | Path,
    label_prefix: str,
    seed: int,
    case_runtime: Any,
) -> dict[str, Any]:
    """Invoke the complete refinement Solver Case through the shared substrate."""

    if case_runtime is None:
        raise RuntimeError(
            "learnable_conv_component_search requires an injected Case runtime; "
            "run it through its standard Project entry"
        )
    child = case_runtime.invoke(
        CaseRunRequest(
            project_name="learnable_conv_component_search",
            stage_name="coefficient_refinement",
            case_name="learnable_conv_coefficient_refinement",
            case_kind="solver",
            resource_request={
                "workers": 1,
                "threads": max(1, int(cfg.inner_threads)),
                "gpus": 0,
                "backend": "local",
                "compute_backend": str(cfg.inner_compute_backend),
                "device": str(cfg.inner_device),
            },
            component_overrides={
                "config": asdict(cfg),
                "structure_bundle": dict(structure_bundle),
                "output_dir": str(Path(output_dir).expanduser().resolve()),
                "label_prefix": str(label_prefix),
                "seed": int(seed),
            },
            metadata={"semantic_role": "coefficient_refinement"},
        )
    )
    child.raise_for_failure("coefficient refinement Case failed")
    payload = dict(child.output or {})
    if str(payload.get("protocol_type", "")) != "blackbase.solver_result":
        raise TypeError("coefficient refinement Case did not return SolverResult")
    refinement = dict(dict(payload.get("metadata", {}) or {}).get("refinement", {}) or {})
    if not refinement:
        raise RuntimeError("coefficient refinement SolverResult omitted refinement metadata")
    refinement["case_run"] = child.request.identity.as_dict()
    return refinement


__all__ = [
    "build_component_overrides",
    "build_full_bundle",
    "normalize_kernel",
    "run_inner_refinement",
]
