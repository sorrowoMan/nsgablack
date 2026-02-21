"""
Sensitivity analysis plugin (multi-run parameter sweep).

This plugin does not change solver behavior during a run.
It provides a helper to run multiple solver instances with
parameter variations and collect comparable metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional
import json
import os
import time

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import KEY_BEST_OBJECTIVE
from ...utils.engineering.file_io import atomic_write_json


def _set_attr_by_path(obj: Any, path: str, value: Any) -> None:
    """Set obj attribute by dotted path with optional [index] access."""
    cur = obj
    parts = str(path).split(".")
    for i, part in enumerate(parts):
        if "[" in part and part.endswith("]"):
            name, idx_str = part[:-1].split("[", 1)
            cur = getattr(cur, name)
            idx = int(idx_str)
            if i == len(parts) - 1:
                cur[idx] = value
                return
            cur = cur[idx]
        else:
            if i == len(parts) - 1:
                setattr(cur, part, value)
                return
            cur = getattr(cur, part)


def _default_metric(solver: Any, result: Any) -> Dict[str, Any]:
    best = None
    getter = getattr(solver, "get_context", None)
    if callable(getter):
        try:
            ctx = getter()
        except Exception:
            ctx = None
        if isinstance(ctx, dict):
            best = ctx.get(KEY_BEST_OBJECTIVE)
    if best is None:
        best = getattr(solver, "best_objective", None)
    steps = result.get("steps") if isinstance(result, dict) else None
    status = result.get("status") if isinstance(result, dict) else None
    return {"best": best, "steps": steps, "status": status}


@dataclass
class SensitivityParam:
    """One parameter sweep definition."""

    path: str
    values: List[Any]
    label: Optional[str] = None


@dataclass
class SensitivityAnalysisConfig:
    output_dir: str = "runs/sensitivity"
    run_id: str = "sensitivity"
    seed: Optional[int] = None
    params: List[SensitivityParam] = field(default_factory=list)
    patch_benchmark_run_id: bool = True
    overwrite_benchmark: bool = True
    metric_fn: Optional[Callable[[Any, Any], Dict[str, Any]]] = None


class SensitivityAnalysisPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Runs multi-run sensitivity studies and writes aggregated study artifacts."
    )
    """
    Helper to run multi-run parameter sensitivity sweeps.

    Use: attach plugin, then call plugin.run_study(build_solver).
    """

    def __init__(
        self,
        name: str = "sensitivity_analysis",
        *,
        config: Optional[SensitivityAnalysisConfig] = None,
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or SensitivityAnalysisConfig()

    def run_study(self, build_solver: Callable[[], Any]) -> Dict[str, Any]:
        if not self.cfg.params:
            raise ValueError("SensitivityAnalysisPlugin: no params configured")

        out_dir = os.path.abspath(str(self.cfg.output_dir))
        os.makedirs(out_dir, exist_ok=True)
        run_id = f"{self.cfg.run_id}_{time.strftime('%Y%m%d_%H%M%S')}"

        metric_fn = self.cfg.metric_fn or _default_metric
        results: List[Dict[str, Any]] = []

        run_rng = np.random.default_rng(None if self.cfg.seed is None else int(self.cfg.seed))
        if self.cfg.seed is not None:
            seed = int(self.cfg.seed)

        for param in self.cfg.params:
            label = param.label or param.path
            for value in list(param.values):
                solver = build_solver()
                setter = getattr(solver, "set_random_seed", None)
                if callable(setter):
                    try:
                        setter(int(run_rng.integers(0, 2**32 - 1)))
                    except Exception:
                        if self.cfg.seed is not None:
                            try:
                                setter(seed)
                            except Exception:
                                pass
                _set_attr_by_path(solver, param.path, value)

                # Patch BenchmarkHarness run_id to avoid overwriting.
                if self.cfg.patch_benchmark_run_id:
                    try:
                        pm = getattr(solver, "plugin_manager", None)
                        if pm is not None and hasattr(pm, "get"):
                            bench = pm.get("benchmark_harness")
                            if bench is not None and hasattr(bench, "cfg"):
                                bench.cfg.run_id = f"{run_id}_{label}_{value}".replace(" ", "_")
                                if self.cfg.overwrite_benchmark:
                                    setattr(bench.cfg, "overwrite", True)
                    except Exception:
                        pass

                result = solver.run()
                metrics = metric_fn(solver, result)
                results.append(
                    {
                        "param": label,
                        "path": param.path,
                        "value": value,
                        "metrics": metrics,
                    }
                )

        payload = {"run_id": run_id, "results": results}
        out_path = os.path.join(out_dir, f"{run_id}.json")
        atomic_write_json(out_path, payload, ensure_ascii=False, indent=2, encoding="utf-8")

        payload["output_path"] = out_path
        return payload



