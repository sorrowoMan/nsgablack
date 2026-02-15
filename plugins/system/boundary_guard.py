from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..base import Plugin
from ...utils.context.context_schema import get_context_lifecycle, is_replayable_context
from ...utils.context.context_contracts import collect_solver_contracts, validate_context_contracts


@dataclass
class BoundaryGuardConfig:
    warn_on_cache_access: bool = True
    warn_on_unreplayable_context: bool = True
    warn_on_missing_requires: bool = True
    strict: bool = False
    report_key: str = "boundary_guard"


class BoundaryGuardPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Reads full solver context for replayability and contract checks; "
        "emits warnings or raises in strict mode."
    )
    """
    Semantic boundary guard.

    It does NOT modify solver behavior. It only inspects context and emits warnings.
    """

    def __init__(self, cfg: Optional[BoundaryGuardConfig] = None):
        super().__init__(name="boundary_guard")
        self.cfg = cfg or BoundaryGuardConfig()
        self.last_warnings: List[str] = []
        self.is_algorithmic = False

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None or not hasattr(solver, "get_context"):
            return None
        try:
            ctx = solver.get_context()
        except Exception:
            return None

        warnings = []
        if self.cfg.warn_on_unreplayable_context and not is_replayable_context(ctx):
            warnings.append("context contains non-replayable cache fields")

        if self.cfg.warn_on_cache_access:
            lifecycle = get_context_lifecycle(ctx)
            cache_keys = [k for k, v in lifecycle.items() if v == "cache"]
            if cache_keys:
                warnings.append(f"cache keys present: {', '.join(cache_keys)}")

        if self.cfg.warn_on_missing_requires:
            contracts = collect_solver_contracts(solver)
            missing = validate_context_contracts(contracts, ctx)
            warnings.extend(missing)

        self.last_warnings = warnings
        if warnings:
            msg = "[boundary_guard] " + "; ".join(warnings)
            if self.cfg.strict:
                raise RuntimeError(msg)
            print(msg)
        return None

    def get_report(self) -> Optional[Dict[str, Any]]:
        return {"warnings": list(self.last_warnings)}



