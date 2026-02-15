"""
Benchmark harness plugin (unified experiment protocol).

This plugin is intentionally read-only with respect to solver behavior:
- It never changes solver control flow.
- It only reads public solver fields and writes external logs.

Goal:
Provide a stable, comparable output schema (CSV + summary JSON) so different
adapters/suites can be fairly compared under the same protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import csv
import json
import os
import random
import time

import numpy as np

from ..base import Plugin
from ...utils.engineering.file_io import atomic_write_json


@dataclass
class BenchmarkHarnessConfig:
    output_dir: str = "runs"
    run_id: str = "run"
    seed: Optional[int] = None

    # Write one CSV row every N generations/steps.
    log_every: int = 1

    # Flush file every N writes (0 disables explicit flush).
    flush_every: int = 10

    # If True, overwrite existing files for the same run_id.
    overwrite: bool = False


class BenchmarkHarnessPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Collects benchmark metrics and writes run artifacts; "
        "does not depend on fixed context keys."
    )
    """
    Unified experiment logger.

    Outputs:
    - {output_dir}/{run_id}.csv
    - {output_dir}/{run_id}.summary.json
    """

    provides_metrics = {"elapsed_s", "eval_count", "throughput_eval_s", "best_score"}

    def __init__(
        self,
        name: str = "benchmark_harness",
        *,
        config: Optional[BenchmarkHarnessConfig] = None,
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or BenchmarkHarnessConfig()

        self._t0: float = 0.0
        self._rows_written = 0
        self._csv_path: Optional[str] = None
        self._summary_path: Optional[str] = None
        self._fp = None
        self._writer: Optional[csv.DictWriter] = None

    # ------------------------------------------------------------------
    def on_solver_init(self, solver: Any):
        self._t0 = time.time()
        self._rows_written = 0

        if self.cfg.seed is not None:
            seed = int(self.cfg.seed)
            random.seed(seed)
            np.random.seed(seed)
            try:
                setattr(solver, "benchmark_seed", seed)
            except Exception:
                pass

        out_dir = os.path.abspath(str(self.cfg.output_dir))
        os.makedirs(out_dir, exist_ok=True)
        self._csv_path = os.path.join(out_dir, f"{self.cfg.run_id}.csv")
        self._summary_path = os.path.join(out_dir, f"{self.cfg.run_id}.summary.json")

        if (not self.cfg.overwrite) and os.path.exists(self._csv_path):
            raise FileExistsError(f"BenchmarkHarnessPlugin: file exists: {self._csv_path}")

        self._fp = open(self._csv_path, "w", newline="", encoding="utf-8")
        fieldnames = [
            "run_id",
            "step",
            "elapsed_s",
            "eval_count",
            "throughput_eval_s",
            "best_score",
            "phase",
            "pareto_archive_size",
        ]
        self._writer = csv.DictWriter(self._fp, fieldnames=fieldnames)
        self._writer.writeheader()
        self._fp.flush()
        return None

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None or self._writer is None:
            return None

        log_every = int(max(1, int(self.cfg.log_every)))
        if int(generation) % log_every != 0:
            return None

        elapsed = max(0.0, float(time.time() - float(self._t0)))
        eval_count = int(getattr(solver, "evaluation_count", 0) or 0)
        throughput = float(eval_count) / elapsed if elapsed > 1e-12 else 0.0

        best_score = self._read_best_score(solver)
        phase = self._read_phase(solver)
        pareto_size = self._read_pareto_size(solver)

        row = {
            "run_id": str(self.cfg.run_id),
            "step": int(generation),
            "elapsed_s": float(elapsed),
            "eval_count": int(eval_count),
            "throughput_eval_s": float(throughput),
            "best_score": None if best_score is None else float(best_score),
            "phase": "" if phase is None else str(phase),
            "pareto_archive_size": "" if pareto_size is None else int(pareto_size),
        }

        self._writer.writerow(row)
        self._rows_written += 1
        if self._fp is not None and int(self.cfg.flush_every) > 0:
            if (self._rows_written % int(self.cfg.flush_every)) == 0:
                self._fp.flush()
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        solver = self.solver
        elapsed = max(0.0, float(time.time() - float(self._t0)))
        eval_count = int(getattr(solver, "evaluation_count", 0) or 0) if solver is not None else 0
        throughput = float(eval_count) / elapsed if elapsed > 1e-12 else 0.0
        best_score = self._read_best_score(solver) if solver is not None else None
        phase = self._read_phase(solver) if solver is not None else None
        pareto_size = self._read_pareto_size(solver) if solver is not None else None

        summary = {
            "run_id": str(self.cfg.run_id),
            "status": str(result.get("status", "")),
            "steps": int(result.get("steps", 0) or 0),
            "elapsed_s": float(elapsed),
            "eval_count": int(eval_count),
            "throughput_eval_s": float(throughput),
            "best_score": None if best_score is None else float(best_score),
            "phase": "" if phase is None else str(phase),
            "pareto_archive_size": None if pareto_size is None else int(pareto_size),
            "seed": None if self.cfg.seed is None else int(self.cfg.seed),
        }
        artifacts = result.get("artifacts")
        if isinstance(artifacts, dict) and artifacts:
            # Optional: other plugins can inject report paths here.
            summary["artifacts"] = dict(artifacts)

        if self._summary_path is not None:
            atomic_write_json(self._summary_path, summary, ensure_ascii=True, indent=2, encoding="utf-8")

        if self._fp is not None:
            try:
                self._fp.flush()
                self._fp.close()
            finally:
                self._fp = None
        return None

    # ------------------------------------------------------------------
    def _read_best_score(self, solver: Any) -> Optional[float]:
        if solver is None:
            return None
        v = getattr(solver, "best_objective", None)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
        v = getattr(solver, "shared_best_score", None)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
        shared = getattr(solver, "shared_state", None)
        if isinstance(shared, dict) and shared.get("best_score") is not None:
            try:
                return float(shared["best_score"])
            except Exception:
                pass
        # last fallback: compute from current objectives (sum) if available
        obj = getattr(solver, "objectives", None)
        vio = getattr(solver, "constraint_violations", None)
        if obj is None:
            return None
        try:
            obj = np.asarray(obj, dtype=float)
            if obj.size == 0:
                return None
            if obj.ndim == 1:
                return float(np.min(obj))
            scores = np.sum(obj, axis=1)
            if vio is not None:
                v = np.asarray(vio, dtype=float).reshape(-1)
                scores = scores + v * 1e6
            return float(np.min(scores))
        except Exception:
            return None

    def _read_phase(self, solver: Any) -> Optional[str]:
        if solver is None:
            return None
        shared = getattr(solver, "shared_state", None)
        if isinstance(shared, dict):
            p = shared.get("phase")
            if p is not None:
                return str(p)
        return None

    def _read_pareto_size(self, solver: Any) -> Optional[int]:
        if solver is None:
            return None
        X = getattr(solver, "pareto_solutions", None)
        if X is None:
            return None
        try:
            X = np.asarray(X)
            if X.ndim == 1:
                return 1 if X.size > 0 else 0
            return int(X.shape[0])
        except Exception:
            return None



