from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from blackbase.project import CaseRunRequest

from ..config import SymbolicKernelDigitsOuterSearchConfig


def run_inner_refinement(
    cfg: SymbolicKernelDigitsOuterSearchConfig,
    *,
    structure_bundle: Mapping[str, Any],
    output_dir: str | Path,
    label_prefix: str,
    seed: int,
    case_runtime: Any,
) -> dict[str, Any]:
    if case_runtime is None:
        raise RuntimeError(
            "symbolic_kernel_digits_outer_search requires an injected Case runtime; "
            "run it through its standard Project entry"
        )
    child = case_runtime.invoke(
        CaseRunRequest(
            project_name="symbolic_kernel_digits_outer_search",
            stage_name="coefficient_refinement",
            case_name="symbolic_kernel_digits_refinement",
            case_kind="solver",
            resource_request={
                "workers": 1,
                "threads": max(1, int(cfg.inner_threads)),
                "gpus": 0,
                "backend": "local",
                "compute_backend": "numpy",
                "device": "cpu",
            },
            component_overrides={
                "config": asdict(cfg),
                "structure_bundle": dict(structure_bundle),
                "output_dir": str(Path(output_dir).expanduser().resolve()),
                "label_prefix": str(label_prefix),
                "seed": int(seed),
            },
            metadata={"semantic_role": "symbolic_kernel_refinement"},
        )
    )
    child.raise_for_failure("symbolic kernel refinement Case failed")
    payload = dict(child.output or {})
    if str(payload.get("protocol_type", "")) != "blackbase.solver_result":
        raise TypeError("symbolic kernel refinement Case did not return SolverResult")
    refinement = dict(dict(payload.get("metadata", {}) or {}).get("refinement", {}) or {})
    if not refinement:
        raise RuntimeError("symbolic kernel refinement result omitted refinement metadata")
    refinement["case_run"] = child.request.identity.as_dict()
    return refinement


__all__ = ["run_inner_refinement"]
