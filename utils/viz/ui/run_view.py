import json
import hashlib
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk

from ...engineering.schema_version import stamp_schema
from ...context.context_keys import KEY_BEST_OBJECTIVE, KEY_BEST_X


ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "runs" / "visualizer"


class RunView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Run", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.app.run_id_var = tk.StringVar()
        ttk.Label(self.tab, text="Run ID (output file name)", foreground="#666").pack(anchor="w", pady=(4, 0))
        ttk.Entry(self.tab, textvariable=self.app.run_id_var).pack(fill="x", pady=(6, 6))
        btn_row = ttk.Frame(self.tab)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Refresh", command=self.on_refresh_ui).pack(
            side="left",
            expand=True,
            fill="x",
            padx=(0, 6),
        )
        ttk.Button(btn_row, text="Run", command=self.on_run).pack(side="left", expand=True, fill="x")
        self.app.sensitivity_btn = ttk.Button(self.tab, text="Run Sensitivity", command=self.on_sensitivity)
        self.app.sensitivity_btn.pack(fill="x", pady=(6, 0))
        self.app.close_on_finish_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.tab,
            text="Close on finish",
            variable=self.app.close_on_finish_var,
        ).pack(anchor="w", pady=(6, 0))
        self.app.result_var = tk.StringVar(value="Not run yet")
        ttk.Label(self.tab, text="Result", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 0))
        ttk.Label(self.tab, textvariable=self.app.result_var, wraplength=280, justify="left").pack(anchor="w", pady=(4, 0))
        self.status_label = ttk.Label(self.tab, text="", foreground="#666")
        self.status_label.pack(anchor="w", pady=(8, 0))
        self.app.status_label = self.status_label

    def update_sensitivity_button(self) -> None:
        if self.get_plugin("sensitivity_analysis") is None:
            self.app.sensitivity_btn.state(["disabled"])
        else:
            self.app.sensitivity_btn.state(["!disabled"])

    def get_plugin(self, name: str) -> Optional[Any]:
        if self.app.solver is None:
            return None
        pm = getattr(self.app.solver, "plugin_manager", None)
        if pm is None or not hasattr(pm, "get"):
            return None
        try:
            return pm.get(name)
        except Exception:
            return None

    def sync_run_id_plugins(self, run_id: str) -> None:
        if self.app.solver is None:
            return
        pm = getattr(self.app.solver, "plugin_manager", None)
        if pm is None or not hasattr(pm, "list_plugins"):
            return
        for plugin in pm.list_plugins(enabled_only=False):
            cfg = getattr(plugin, "cfg", None)
            if cfg is None:
                continue
            if hasattr(cfg, "run_id"):
                try:
                    cfg.run_id = str(run_id)
                except Exception:
                    pass

    def _read_best_from_context(self) -> tuple[Any, Any]:
        solver = self.app.solver
        if solver is None:
            return None, None
        getter = getattr(solver, "get_context", None)
        if callable(getter):
            try:
                ctx = getter()
            except Exception:
                ctx = None
            if isinstance(ctx, dict):
                return ctx.get(KEY_BEST_OBJECTIVE), ctx.get(KEY_BEST_X)
        return getattr(solver, "best_objective", None), getattr(solver, "best_x", None)

    def snapshot(self, run_id: str) -> dict:
        solver = self.app.solver
        adapter = getattr(solver, "adapter", None)
        pipeline = getattr(solver, "representation_pipeline", None)
        bias_module = getattr(solver, "bias_module", None)
        plugin_mgr = getattr(solver, "plugin_manager", None)

        snap = {
            "entry": self.app.entry,
            "run_id": run_id,
            "timestamp": time.time(),
            "solver": solver.__class__.__name__ if solver else None,
            "adapter": adapter.__class__.__name__ if adapter else None,
            "strategies": [],
            "pipeline": {
                "initializer": getattr(getattr(pipeline, "initializer", None), "__class__", type(None)).__name__,
                "mutator": getattr(getattr(pipeline, "mutator", None), "__class__", type(None)).__name__,
                "repair": getattr(getattr(pipeline, "repair", None), "__class__", type(None)).__name__,
                "codec": getattr(getattr(pipeline, "codec", None), "__class__", type(None)).__name__,
            },
            "biases": [],
            "plugins": [],
        }

        if bias_module is not None:
            manager = getattr(bias_module, "_manager", None)
            if manager is not None:
                algo_mgr = getattr(manager, "algorithmic_manager", None)
                dom_mgr = getattr(manager, "domain_manager", None)
                for group_name, mgr in (("algorithmic", algo_mgr), ("domain", dom_mgr)):
                    if mgr is None:
                        continue
                    for bias in getattr(mgr, "biases", {}).values():
                        snap["biases"].append(
                            {
                                "name": bias.name,
                                "type": group_name,
                                "enabled": bool(getattr(bias, "enabled", True)),
                                "class": bias.__class__.__name__,
                            }
                        )

        if plugin_mgr is not None:
            for plugin in plugin_mgr.list_plugins(enabled_only=False):
                snap["plugins"].append(
                    {
                        "name": plugin.name,
                        "enabled": bool(getattr(plugin, "enabled", True)),
                        "class": plugin.__class__.__name__,
                    }
                )
        # adapter strategies/roles (if any)
        if adapter is not None:
            if hasattr(adapter, "strategies"):
                for spec in getattr(adapter, "strategies", []):
                    snap["strategies"].append(
                        {
                            "name": getattr(spec, "name", "strategy"),
                            "enabled": bool(getattr(spec, "enabled", True)),
                            "weight": float(getattr(spec, "weight", 1.0)),
                            "class": spec.adapter.__class__.__name__,
                        }
                    )
            elif hasattr(adapter, "roles"):
                for role in getattr(adapter, "roles", []):
                    role_name = getattr(role, "name", "role")
                    role_units = [
                        u for u in getattr(adapter, "units", [])
                        if getattr(u, "role", None) == role_name and getattr(u, "adapter", None) is not None
                    ]
                    role_adapter_names = sorted({u.adapter.__class__.__name__ for u in role_units})
                    role_class = ", ".join(role_adapter_names) if role_adapter_names else None
                    if role_class is None:
                        role_adapter = getattr(role, "adapter", None)
                        if callable(role_adapter):
                            try:
                                infer_fn = getattr(adapter, "_instantiate_role_adapter", None)
                                if callable(infer_fn):
                                    inferred = infer_fn(role_adapter, 0)
                                    role_class = inferred.__class__.__name__
                                else:
                                    role_class = "factory"
                            except Exception:
                                role_class = "factory"
                        else:
                            role_class = getattr(role_adapter, "__class__", type(None)).__name__
                    snap["strategies"].append(
                        {
                            "name": role_name,
                            "enabled": bool(getattr(role, "enabled", True)),
                            "weight": float(getattr(role, "weight", 1.0)),
                            "class": role_class,
                        }
                    )
        snap["structure_hash"] = self._structure_hash(snap)
        snap["structure_hash_short"] = snap["structure_hash"][:8]
        return stamp_schema(snap, "run_inspector_snapshot")

    def _structure_hash(self, snap: Dict[str, Any]) -> str:
        def sort_items(items, keys):
            out = []
            for item in items or []:
                out.append({k: item.get(k) for k in keys})
            return sorted(out, key=lambda x: str(x.get("name", "")))

        data = {
            "adapter": snap.get("adapter"),
            "pipeline": snap.get("pipeline"),
            "strategies": sort_items(snap.get("strategies", []), ["name", "enabled", "weight"]),
            "biases": sort_items(snap.get("biases", []), ["name", "enabled"]),
            "plugins": sort_items(snap.get("plugins", []), ["name", "enabled"]),
        }
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _refresh_hash_index(self) -> None:
        if self.app._hash_index:
            return
        if not RUNS_DIR.exists():
            return
        for path in RUNS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            h = data.get("structure_hash")
            rid = data.get("run_id")
            if h and rid:
                self.app._hash_index[str(h)] = str(rid)

    def on_run(self) -> None:
        if getattr(self.app, "_is_running", False):
            self.status_label.config(text="Run already in progress")
            return
        if self.app.solver is None:
            self.status_label.config(text="No solver")
            return
        run_id = self.app.run_id_var.get().strip() or time.strftime("%Y%m%d_%H%M%S")
        self.app.run_id_var.set(run_id)
        self.sync_run_id_plugins(run_id)
        self.status_label.config(text=f"Running... {run_id}")
        self.app._is_running = True

        def _worker():
            enabled_strategies: List[str] = []
            enabled_plugins: List[str] = []
            snapshot_path = str(RUNS_DIR / f"{run_id}.json")
            status = "failed"
            steps = None
            best_obj = None
            best_x = None
            artifacts: Dict[str, Any] = {}
            try:
                RUNS_DIR.mkdir(parents=True, exist_ok=True)
                snap = self.snapshot(run_id)
                self._refresh_hash_index()
                structure_hash = snap.get("structure_hash", "")
                equiv_run = self.app._hash_index.get(structure_hash)
                if equiv_run and equiv_run == run_id:
                    equiv_run = None
                if not equiv_run:
                    self.app._hash_index[str(structure_hash)] = str(run_id)
                enabled_strategies = [
                    s["name"] for s in snap.get("strategies", []) if s.get("enabled")
                ]
                enabled_plugins = [
                    p["name"] for p in snap.get("plugins", []) if p.get("enabled")
                ]
                if snap.get("adapter"):
                    print(f"[ui] adapter={snap['adapter']}")
                if enabled_plugins:
                    print(f"[ui] plugins(enabled)={enabled_plugins}")
                if enabled_strategies:
                    print(f"[ui] strategies(enabled)={enabled_strategies}")
                from ...engineering.file_io import atomic_write_text
                atomic_write_text(
                    RUNS_DIR / f"{run_id}.json",
                    json.dumps(snap, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                try:
                    self.app.solver._ui_snapshot = snap
                    self.app.solver._ui_snapshot_path = snapshot_path
                except Exception:
                    pass
                result = self.app.solver.run()
                status = result.get("status") if isinstance(result, dict) else "done"
                if isinstance(result, dict):
                    steps = result.get("steps")
                    artifacts = result.get("artifacts", {}) if isinstance(result.get("artifacts", {}), dict) else {}
                best_obj, best_x = self._read_best_from_context()
                msg = f"Done: {run_id} ({status})"
                if steps is not None:
                    msg = f"{msg} steps={steps}"
                if best_obj is not None:
                    msg = f"{msg} best={best_obj:.6f}"
                print(f"[ui] {msg}")
                if best_x is not None:
                    print(f"[ui] best_x={best_x}")
            except Exception as exc:
                msg = f"Failed: {exc}"
            def _finish():
                self.app._is_running = False
                self.app.result_var.set(msg)
                self.status_label.config(text=msg)
                self.app._last_run_id = run_id
                self.app._last_artifacts = artifacts
                hist = msg
                if equiv_run:
                    hist = f"{hist} ~= {equiv_run}"
                if enabled_strategies:
                    hist = f"{hist} strategies={','.join(enabled_strategies)}"
                detail_lines = [
                    f"run_id: {run_id}",
                    f"status: {status}",
                    f"steps: {steps}",
                    f"best: {best_obj}",
                    f"strategies: {', '.join(enabled_strategies) if enabled_strategies else 'none'}",
                    f"plugins: {', '.join(enabled_plugins) if enabled_plugins else 'none'}",
                    f"snapshot: {snapshot_path}",
                    f"structure_hash: {structure_hash}",
                    f"structure_hash_short: {structure_hash[:8] if structure_hash else ''}",
                    f"equivalent_to: {equiv_run if equiv_run else 'none'}",
                ]
                if artifacts:
                    detail_lines.append(f"artifacts: {artifacts}")
                if best_x is not None:
                    detail_lines.append(f"best_x: {best_x}")
                self.app.append_history(hist, "\n".join(detail_lines))
                if self.app.contrib_view:
                    self.app.contrib_view.add_run_choice(run_id)
                    self.app.contrib_view.refresh_contribution()
                if getattr(self.app, "context_view", None):
                    self.app.context_view.refresh()
                if self.app.close_on_finish_var.get():
                    self.app.destroy()
            self.app.after(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()

    def on_refresh_ui(self) -> None:
        """Refresh UI state from current solver without reloading entry/building a new solver."""
        if self.app.solver is None:
            self.status_label.config(text="No solver loaded")
            return
        self.app._refresh_sections()
        if self.app.contrib_view:
            self.app.contrib_view.refresh_contribution()
        if getattr(self.app, "context_view", None):
            self.app.context_view.refresh()
        self.status_label.config(text="UI refreshed")

    def on_sensitivity(self) -> None:
        plugin = self.get_plugin("sensitivity_analysis")
        if plugin is None:
            self.status_label.config(text="No sensitivity_analysis plugin")
            return
        self.status_label.config(text="Running sensitivity...")

        def _worker():
            try:
                result = plugin.run_study(self.app.builder)
                msg = f"Sensitivity done: {result.get('run_id')}"
                out_path = result.get("output_path")
                if out_path:
                    msg = f"{msg} -> {out_path}"
            except Exception as exc:
                msg = f"Sensitivity failed: {exc}"

            self.app.after(0, lambda: self.status_label.config(text=msg))

        threading.Thread(target=_worker, daemon=True).start()
