"""
Module report plugin.

Goal: make "what modules were enabled" and "which biases contributed" auditable.

This plugin is intentionally read-only with respect to solver behavior.
It only inspects solver state and writes JSON/Markdown artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import json
import time

from ..base import Plugin
from ...utils.engineering.file_io import atomic_write_json, atomic_write_text
from ...utils.engineering.schema_version import stamp_schema


@dataclass
class ModuleReportConfig:
    output_dir: str = "runs"
    run_id: str = "run"
    write_bias_markdown: bool = True


class ModuleReportPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Builds module/bias reports from solver state and writes JSON/Markdown artifacts."
    )
    """
    Write module inventory + bias contribution report at solver finish.

    Files:
    - {output_dir}/{run_id}.modules.json
    - {output_dir}/{run_id}.bias.json
    - {output_dir}/{run_id}.bias.md (optional)

    Also injects `result["artifacts"]` so other plugins (e.g. BenchmarkHarness)
    can include report paths in their summaries.
    """

    def __init__(
        self,
        name: str = "module_report",
        *,
        config: Optional[ModuleReportConfig] = None,
        priority: int = -5,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or ModuleReportConfig()
        self._out_dir: Optional[Path] = None

    def on_solver_init(self, solver: Any):
        out_dir = Path(str(self.cfg.output_dir)).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        self._out_dir = out_dir
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        solver = self.solver
        if solver is None:
            return None

        out_dir = self._out_dir or Path(str(self.cfg.output_dir)).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        modules_path = out_dir / f"{self.cfg.run_id}.modules.json"
        bias_json_path = out_dir / f"{self.cfg.run_id}.bias.json"
        bias_md_path = out_dir / f"{self.cfg.run_id}.bias.md"

        modules_payload = self._collect_modules(solver)
        ui_snapshot = getattr(solver, "_ui_snapshot", None)
        ui_snapshot_path = getattr(solver, "_ui_snapshot_path", None)
        if ui_snapshot is not None or ui_snapshot_path is not None:
            modules_payload["ui_snapshot"] = {
                "path": ui_snapshot_path,
                "inline": ui_snapshot if isinstance(ui_snapshot, dict) else None,
            }
        modules_payload["metadata"] = {
            "run_id": str(self.cfg.run_id),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        modules_payload = stamp_schema(modules_payload, "module_report")
        atomic_write_json(modules_path, modules_payload, ensure_ascii=False, indent=2, encoding="utf-8")

        bias_payload = self._collect_bias_contributions(solver)
        bias_payload["metadata"] = {
            "run_id": str(self.cfg.run_id),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        bias_payload = stamp_schema(bias_payload, "bias_report")
        atomic_write_json(bias_json_path, bias_payload, ensure_ascii=False, indent=2, encoding="utf-8")

        if bool(self.cfg.write_bias_markdown):
            atomic_write_text(bias_md_path, self._render_bias_markdown(bias_payload), encoding="utf-8")

        artifacts = result.setdefault("artifacts", {})
        if isinstance(artifacts, dict):
            artifacts["modules_report_json"] = str(modules_path)
            artifacts["bias_report_json"] = str(bias_json_path)
            if bool(self.cfg.write_bias_markdown):
                artifacts["bias_report_md"] = str(bias_md_path)
        return None

    def _collect_modules(self, solver: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "solver": {"class": solver.__class__.__name__},
            "adapter": {"class": getattr(getattr(solver, "adapter", None), "__class__", type(None)).__name__},
            "adapter_state": {},
            "pipeline": None,
            "bias_module": None,
            "plugins": [],
            "parallel": {},
        }
        runtime_timing = getattr(solver, "_runtime_timing", None)
        runtime_timing_calls = getattr(solver, "_runtime_timing_calls", None)
        if isinstance(runtime_timing, dict):
            payload["solver"]["runtime_timing_s"] = {
                str(k): float(v or 0.0) for k, v in runtime_timing.items()
            }
        if isinstance(runtime_timing_calls, dict):
            payload["solver"]["runtime_timing_calls"] = {
                str(k): int(v or 0) for k, v in runtime_timing_calls.items()
            }

        pipe = getattr(solver, "representation_pipeline", None)
        if pipe is not None:
            pipeline_payload: Dict[str, Any] = {"class": pipe.__class__.__name__}
            for attr in ("initializer", "mutator", "repair", "crossover", "encoder"):
                comp = getattr(pipe, attr, None)
                if comp is None:
                    continue
                comp_info: Dict[str, Any] = {"class": comp.__class__.__name__}
                if comp.__class__.__name__ == "ParallelRepair":
                    comp_info["parallel"] = {
                        "backend": getattr(comp, "backend", None),
                        "max_workers": getattr(comp, "max_workers", None),
                        "min_batch_size": getattr(comp, "min_batch_size", None),
                    }
                    inner = getattr(comp, "inner", None)
                    if inner is not None:
                        comp_info["inner_class"] = inner.__class__.__name__
                pipeline_payload[attr] = comp_info
            payload["pipeline"] = pipeline_payload

        bias = getattr(solver, "bias_module", None)
        if bias is not None:
            payload["bias_module"] = {"class": bias.__class__.__name__}

        adapter = getattr(solver, "adapter", None)
        if adapter is not None:
            state: Dict[str, Any] = {"class": adapter.__class__.__name__}
            strategies = []
            if hasattr(adapter, "strategies"):
                for spec in getattr(adapter, "strategies", []):
                    strategies.append(
                        {
                            "name": getattr(spec, "name", "strategy"),
                            "enabled": bool(getattr(spec, "enabled", True)),
                            "weight": float(getattr(spec, "weight", 1.0)),
                            "class": getattr(spec.adapter, "__class__", type(None)).__name__,
                        }
                    )
            if strategies:
                state["strategies"] = strategies
            payload["adapter_state"] = state

        # dynamic switch events (if any)
        events = getattr(solver, "dynamic_switch_events", None)
        if isinstance(events, list) and events:
            payload["dynamic_switch_events"] = events

        pm = getattr(solver, "plugin_manager", None)
        if pm is not None and hasattr(pm, "list_plugins"):
            try:
                plugins = pm.list_plugins(enabled_only=False)
                payload["plugins"] = [
                    {
                        "name": getattr(p, "name", ""),
                        "class": p.__class__.__name__,
                        "enabled": bool(getattr(p, "enabled", True)),
                        "priority": int(getattr(p, "priority", 0) or 0),
                        "is_algorithmic": bool(getattr(p, "is_algorithmic", False)),
                        "time_total_s": float(getattr(getattr(p, "_profile", {}), "get", lambda _k, _d=None: _d)("total_s", 0.0) or 0.0)
                        if isinstance(getattr(p, "_profile", None), dict)
                        else 0.0,
                        "time_events_s": dict(getattr(p, "_profile", {}).get("events", {}))
                        if isinstance(getattr(p, "_profile", None), dict)
                        else {},
                    }
                    for p in plugins
                ]
                for item, p in zip(payload["plugins"], plugins):
                    if not bool(item.get("is_algorithmic")):
                        continue
                    report = None
                    try:
                        if hasattr(p, "get_report") and callable(getattr(p, "get_report")):
                            report = p.get_report()
                    except Exception:
                        report = None
                    if isinstance(report, dict) and report:
                        item["report"] = report
            except Exception:
                payload["plugins"] = []

        for key in (
            "enable_parallel",
            "parallel_backend",
            "parallel_max_workers",
            "parallel_chunk_size",
        ):
            if hasattr(solver, key):
                payload["parallel"][key] = getattr(solver, key)

        return payload

    def _collect_bias_contributions(self, solver: Any) -> Dict[str, Any]:
        bias_module = getattr(solver, "bias_module", None)
        if bias_module is None:
            return {"enabled": False, "message": "no bias_module"}

        if getattr(bias_module, "enable", True) is False:
            return {"enabled": False, "message": "bias_module disabled"}

        if not hasattr(bias_module, "list_biases") or not hasattr(bias_module, "get_bias"):
            return {"enabled": True, "message": "bias_module does not support statistics API"}

        names = []
        try:
            names = list(bias_module.list_biases())
        except Exception:
            names = []

        stats = []
        for name in names:
            try:
                b = bias_module.get_bias(name)
                if b is None:
                    continue
                s = b.get_statistics() if hasattr(b, "get_statistics") else {"name": str(name)}
                stats.append(s)
            except Exception:
                continue

        def _contrib(s: Dict[str, Any]) -> float:
            try:
                return float(s.get("total_contribution", 0.0) or 0.0)
            except Exception:
                return 0.0

        stats.sort(key=_contrib, reverse=True)
        total = sum(_contrib(s) for s in stats)
        return {
            "enabled": True,
            "total_contribution": total,
            "biases": stats,
        }

    def _render_bias_markdown(self, payload: Dict[str, Any]) -> str:
        if not payload.get("enabled"):
            return "# Bias Contribution Report\n\n(no bias enabled)\n"

        biases = payload.get("biases") or []
        total = float(payload.get("total_contribution", 0.0) or 0.0)
        lines = []
        lines.append("# Bias Contribution Report")
        lines.append("")
        lines.append(f"- total_contribution: {total:.6g}")
        lines.append("")
        if not biases:
            lines.append("(no bias stats)")
            lines.append("")
            return "\n".join(lines)

        lines.append("| rank | name | total_contribution | usage_count | weight | % |")
        lines.append("| ---: | --- | ---: | ---: | ---: | ---: |")
        for i, s in enumerate(biases, start=1):
            name = str(s.get("name", ""))
            contrib = float(s.get("total_contribution", 0.0) or 0.0)
            usage = int(s.get("usage_count", 0) or 0)
            weight = s.get("weight", "")
            try:
                weight = float(weight)
                weight_str = f"{weight:.6g}"
            except Exception:
                weight_str = str(weight)
            pct = (contrib / total * 100.0) if total > 1e-12 else 0.0
            lines.append(f"| {i} | {name} | {contrib:.6g} | {usage} | {weight_str} | {pct:.1f}% |")
        lines.append("")
        return "\n".join(lines)



