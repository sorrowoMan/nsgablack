"""
Authority suite for Variable Neighborhood Search (VNS) adapter wiring.

This suite can optionally "upgrade" a continuous GaussianMutation into a
ContextGaussianMutation so VNS neighborhood scheduling works out-of-the-box.
"""

from __future__ import annotations

from typing import Optional

from ...adapters import VNSAdapter, VNSConfig
from ...representation.continuous import ContextGaussianMutation, GaussianMutation
from ...utils.context.context_keys import KEY_MUTATION_SIGMA


def attach_vns(
    solver,
    *,
    config: Optional[VNSConfig] = None,
    ensure_context_mutator: bool = True,
    **config_kwargs,
):
    """
    Attach VNS adapter to a ComposableSolver-like solver.

    If ensure_context_mutator=True and the solver's representation pipeline uses
    `GaussianMutation`, it will be replaced with `ContextGaussianMutation` to
    consume `context[mutation_sigma]`.
    """

    for meth in ("init_candidate", "mutate_candidate", "repair_candidate", "evaluate_population"):
        if not hasattr(solver, meth):
            raise ValueError(f"attach_vns: solver missing required method: {meth}")

    pipeline = getattr(solver, "representation_pipeline", None)
    if ensure_context_mutator and pipeline is not None:
        mut = getattr(pipeline, "mutator", None)
        if isinstance(mut, GaussianMutation):
            pipeline.mutator = ContextGaussianMutation(
                base_sigma=float(getattr(mut, "sigma", 0.1)),
                sigma_key=KEY_MUTATION_SIGMA,
                low=getattr(mut, "low", None),
                high=getattr(mut, "high", None),
            )

    cfg = config or VNSConfig(**config_kwargs)
    adapter = VNSAdapter(config=cfg)
    if not hasattr(solver, "set_adapter"):
        raise ValueError("attach_vns: solver missing set_adapter()")
    solver.set_adapter(adapter)
    return adapter
