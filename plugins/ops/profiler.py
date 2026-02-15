"""Runtime profiler plugin (structured, reproducible performance artifacts).

This plugin is intentionally low-overhead:
- It records wall-clock durations per generation/step.
- It summarizes evaluation throughput using solver.evaluation_count deltas.
- It writes a single JSON artifact for later aggregation.

It does not depend on cProfile/psutil; heavier profilers can be layered on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import time

from ..base import Plugin
from ...utils.engineering.file_io import atomic_write_text


@dataclass
class ProfilerConfig:
    output_dir: str = "runs"
    run_id: str = "run"
    overwrite: bool = False
    flush_every: int = 0  # 0 disables periodic flush (single JSON at end)


class ProfilerPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Profiles runtime/per-generation timings and writes profile artifact."
    )
    """Write a structured performance profile JSON at solver finish."""

    def __init__(
        self,
        name: str = "profiler",
        *,
        config: Optional[ProfilerConfig] = None,
        priority: int = 1,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or ProfilerConfig()
        self.is_algorithmic = False

        self._t0: float = 0.0
        self._gen_t0: Optional[float] = None
        self._eval0: int = 0
        self._records: List[Dict[str, Any]] = []
        self._out_dir: Optional[Path] = None
        self._path: Optional[Path] = None

    def on_solver_init(self, solver: Any):
        self._t0 = time.time()
        self._gen_t0 = None
        self._eval0 = int(getattr(solver, "evaluation_count", 0) or 0)
        self._records = []

        out_dir = Path(str(self.cfg.output_dir)).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        self._out_dir = out_dir
        self._path = out_dir / f"{self.cfg.run_id}.profile.json"
        if self._path.exists() and (not bool(self.cfg.overwrite)):
            raise FileExistsError(f"ProfilerPlugin: file exists: {self._path}")
        return None

    def on_generation_start(self, generation: int):
        self._gen_t0 = time.time()
        return None

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return None

        t1 = time.time()
        t0 = self._gen_t0 if self._gen_t0 is not None else t1
        dt = max(0.0, float(t1 - float(t0)))

        eval1 = int(getattr(solver, "evaluation_count", 0) or 0)
        de = int(eval1 - int(self._eval0))
        self._eval0 = eval1

        rec = {
            "generation": int(generation),
            "wall_s": float(dt),
            "eval_delta": int(de),
            "eval_per_s": float(de) / dt if dt > 1e-12 else 0.0,
            "phase": None,
        }
        shared = getattr(solver, "shared_state", None)
        if isinstance(shared, dict) and shared.get("phase") is not None:
            rec["phase"] = str(shared.get("phase"))
        self._records.append(rec)

        # Optional: periodic flush for long runs.
        if self._path is not None and int(self.cfg.flush_every) > 0:
            if (len(self._records) % int(self.cfg.flush_every)) == 0:
                atomic_write_text(
                    self._path,
                    json.dumps(self._build_payload(final=False), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        if self._path is None:
            return None
        payload = self._build_payload(final=True)
        atomic_write_text(
            self._path,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        artifacts = result.setdefault("artifacts", {})
        if isinstance(artifacts, dict):
            artifacts["profile_json"] = str(self._path)
        return None

    def _build_payload(self, *, final: bool) -> Dict[str, Any]:
        solver = self.solver
        elapsed = max(0.0, float(time.time() - float(self._t0)))
        eval_count = int(getattr(solver, "evaluation_count", 0) or 0) if solver is not None else 0

        pm = getattr(solver, "plugin_manager", None) if solver is not None else None
        plugin_profiles: List[Dict[str, Any]] = []
        try:
            if pm is not None and hasattr(pm, "plugins"):
                for p in list(getattr(pm, "plugins", []) or []):
                    prof = getattr(p, "_profile", None)
                    if isinstance(prof, dict):
                        plugin_profiles.append(
                            {
                                "name": getattr(p, "name", ""),
                                "class": p.__class__.__name__,
                                "enabled": bool(getattr(p, "enabled", True)),
                                "total_s": float(prof.get("total_s", 0.0) or 0.0),
                                "events_s": dict(prof.get("events", {}) or {}),
                            }
                        )
        except Exception:
            plugin_profiles = []

        wall_times = [float(r.get("wall_s", 0.0) or 0.0) for r in self._records]
        eval_rates = [float(r.get("eval_per_s", 0.0) or 0.0) for r in self._records]

        def _pct(xs: List[float], q: float) -> Optional[float]:
            if not xs:
                return None
            xs2 = sorted(xs)
            q = max(0.0, min(1.0, float(q)))
            i = int(round((len(xs2) - 1) * q))
            return float(xs2[i])

        summary = {
            "generations": int(len(self._records)),
            "wall_s_p50": _pct(wall_times, 0.50),
            "wall_s_p95": _pct(wall_times, 0.95),
            "eval_per_s_p50": _pct(eval_rates, 0.50),
            "eval_per_s_p95": _pct(eval_rates, 0.95),
        }

        return {
            "run_id": str(self.cfg.run_id),
            "final": bool(final),
            "elapsed_s": float(elapsed),
            "eval_count": int(eval_count),
            "throughput_eval_s": float(eval_count) / elapsed if elapsed > 1e-12 else 0.0,
            "summary": summary,
            "per_generation": list(self._records),
            "plugins_profile": plugin_profiles,
        }



