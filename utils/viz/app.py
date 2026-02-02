import argparse
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

from .ui.catalog_view import CatalogView
from .ui.contrib_view import ContributionView
from .ui.run_view import RunView


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class WireItem:
    label: str
    enabled: bool
    on_toggle: Callable[[bool], None]
    detail: str
    kind: str


class VisualizerApp(tk.Tk):
    def __init__(self, builder: Callable[[], Any], entry: str) -> None:
        super().__init__()
        self.title("NSGABlack Run Inspector")
        self.geometry("980x720")
        self.builder = builder
        self.entry = entry

        self._catalog_obj = None
        self.catalog: Dict[str, Dict[str, Any]] = {}

        self.solver = None
        self.items: List[Tuple[str, List[WireItem]]] = []
        self._pipeline_cache: Dict[str, Any] = {}
        self._missing_rows: List[Tuple[tk.Frame, WireItem]] = []
        self._missing_index = 0
        self._canvas = None
        self._history: List[str] = []
        self._history_details: List[str] = []
        self._last_run_id: Optional[str] = None
        self._last_artifacts: Dict[str, Any] = {}
        self._bias_row_map: Dict[str, tk.Frame] = {}
        self._bias_detail_map: Dict[str, Dict[str, Any]] = {}
        self._run_choices: List[str] = []
        self._delta_keys: set[str] = set()
        self._hash_index: Dict[str, str] = {}

        self.run_view: Optional[RunView] = None
        self.contrib_view: Optional[ContributionView] = None
        self.catalog_view: Optional[CatalogView] = None

        self._build_ui()
        self._rebuild_solver()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=8)

        ttk.Label(top, text="Run Inspector", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(top, text=f"Entry: {self.entry}", foreground="#666").pack(anchor="w")

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=8)

        # Left: scrollable sections
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        canvas = tk.Canvas(left, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        self._canvas = canvas

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Middle: run history
        mid = ttk.Frame(main, width=260)
        mid.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(mid, text="History", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        history_box = ttk.Frame(mid)
        history_box.pack(fill="both", expand=True, pady=(6, 0))
        self.history_list = tk.Listbox(history_box, height=12, width=60)
        hist_scroll = ttk.Scrollbar(history_box, orient="vertical", command=self.history_list.yview)
        hist_xscroll = ttk.Scrollbar(mid, orient="horizontal", command=self.history_list.xview)
        self.history_list.configure(yscrollcommand=hist_scroll.set, xscrollcommand=hist_xscroll.set)
        self.history_list.pack(side="left", fill="both", expand=True)
        hist_scroll.pack(side="right", fill="y")
        hist_xscroll.pack(fill="x", pady=(2, 0))
        self.history_list.bind("<<ListboxSelect>>", self._on_history_select)

        # Right: detail panel
        right = ttk.Frame(main, width=220)
        right.pack(side="right", fill="y", padx=(12, 0))
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        self._notebook = notebook

        details_tab = ttk.Frame(notebook)
        run_tab = ttk.Frame(notebook)
        contrib_tab = ttk.Frame(notebook)
        traj_tab = ttk.Frame(notebook)
        catalog_tab = ttk.Frame(notebook)
        self._tab_details = details_tab
        self._tab_run = run_tab
        self._tab_contrib = contrib_tab
        self._tab_traj = traj_tab
        self._tab_catalog = catalog_tab

        notebook.add(details_tab, text="Details")
        notebook.add(run_tab, text="Run")
        notebook.add(contrib_tab, text="Contribution")
        notebook.add(traj_tab, text="Trajectory")
        notebook.add(catalog_tab, text="Catalog")

        # Details tab
        ttk.Label(details_tab, text="Details", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.detail_title = ttk.Label(details_tab, text="", font=("Segoe UI", 10, "bold"))
        self.detail_title.pack(anchor="w", pady=(8, 2))
        self.detail_kind = ttk.Label(details_tab, text="", foreground="#666")
        self.detail_kind.pack(anchor="w")
        self.detail_health = tk.Label(details_tab, text="", fg="#666", anchor="w")
        self.detail_health.pack(anchor="w", pady=(2, 0))
        self.detail_summary = tk.Text(
            details_tab,
            height=12,
            wrap="word",
            borderwidth=1,
            relief="solid",
        )
        self.detail_summary.pack(fill="x", pady=(6, 10))
        self.detail_summary.insert("1.0", "")
        self.detail_summary.config(state="disabled")
        ttk.Button(details_tab, text="Next Missing", command=self._jump_to_missing).pack(fill="x", pady=(4, 0))

        # Views
        self.run_view = RunView(self, run_tab)
        self.contrib_view = ContributionView(self, contrib_tab, traj_tab)
        self.catalog_view = CatalogView(self, catalog_tab)
        self.catalog = self.catalog_view.load_catalog()

    def _rebuild_solver(self) -> None:
        try:
            self.solver = self.builder()
        except Exception as exc:
            if self.run_view:
                self.run_view.status_label.config(text=f"Build failed: {exc}")
            return
        self._pipeline_cache = {}
        self.items = self._collect_items(self.solver)
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self._render_items()
        if self.run_view:
            self.run_view.update_sensitivity_button()
        if self.contrib_view:
            self.contrib_view.reload_run_choices()
        if self.run_view:
            self.run_view.status_label.config(text="Ready")

    def _refresh_sections(self) -> None:
        if self.solver is not None:
            self.items = self._collect_items(self.solver)
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self._render_items()
        if self.run_view:
            self.run_view.update_sensitivity_button()

    def _render_items(self) -> None:
        self._missing_rows = []
        self._missing_index = 0
        self._bias_row_map = {}
        try:
            base_bg = self.scroll_frame.cget("background")
        except tk.TclError:
            base_bg = self.cget("bg")
        for section_title, items in self.items:
            frame = ttk.LabelFrame(self.scroll_frame, text=section_title)
            frame.pack(fill="x", pady=6, padx=4)
            for item in items:
                var = tk.BooleanVar(value=bool(item.enabled))
                missing = getattr(item, "_missing", None)
                delta_key = getattr(item, "_delta_key", None)

                row = tk.Frame(frame, bg=base_bg)
                row.pack(fill="x", padx=6, pady=3)
                if missing:
                    self._missing_rows.append((row, item))
                if delta_key and delta_key in self._delta_keys:
                    row.configure(bg="#eaf2ff")
                raw_name = getattr(item, "_raw_name", None)
                if raw_name:
                    self._bias_row_map[str(raw_name)] = row

                def _make_toggle(cb_item: WireItem, cb_var: tk.BooleanVar):
                    def _cb():
                        cb_item.enabled = bool(cb_var.get())
                        cb_item.on_toggle(cb_item.enabled)
                        self._refresh_sections()
                    return _cb

                label_text = f"[{item.kind}] {item.label}" if item.kind else item.label

                chk = ttk.Checkbutton(
                    row,
                    text=label_text,
                    variable=var,
                    command=_make_toggle(item, var),
                )
                if item.kind == "adapter" and item.detail.endswith("(fixed)"):
                    chk.state(["disabled"])
                chk.pack(side="left", anchor="w")

                def _make_info(cb_item: WireItem):
                    def _info():
                        self.detail_title.config(text=cb_item.label)
                        self.detail_kind.config(text=cb_item.kind)
                        self._update_health(cb_item.detail)
                        self.detail_summary.config(state="normal")
                        self.detail_summary.delete("1.0", "end")
                        self.detail_summary.insert("1.0", cb_item.detail)
                        self.detail_summary.config(state="disabled")
                    return _info

                info = ttk.Button(row, text="i", width=2, command=_make_info(item))
                info.pack(side="right")
    def _jump_to_missing(self) -> None:
        if not self._missing_rows:
            if self.run_view:
                self.run_view.status_label.config(text="No missing companion components")
            return
        row, item = self._missing_rows[self._missing_index % len(self._missing_rows)]
        self._missing_index = (self._missing_index + 1) % len(self._missing_rows)
        self.update_idletasks()
        total_h = max(self.scroll_frame.winfo_height(), 1)
        y = row.winfo_y()
        frac = min(max(y / total_h, 0.0), 1.0)
        if self._canvas is not None:
            self._canvas.yview_moveto(frac)

        # brief highlight
        original = row.cget("bg")
        row.configure(bg="#fff2cc")
        self.after(300, lambda: row.configure(bg=original))
        if self.run_view:
            self.run_view.status_label.config(text=f"Missing companions near: {item.label}")

    def _on_history_select(self, _event: Any) -> None:
        sel = self.history_list.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._history_details):
            return
        detail = self._history_details[idx]
        self.detail_title.config(text="History")
        self.detail_kind.config(text="run")
        self.detail_health.config(text="", fg="#666")
        self.detail_summary.config(state="normal")
        self.detail_summary.delete("1.0", "end")
        self.detail_summary.insert("1.0", detail)
        self.detail_summary.config(state="disabled")

    def append_history(self, msg: str, detail: str) -> None:
        self._history.append(msg)
        self.history_list.insert("end", msg)
        self._history_details.append(detail)

    def _update_health(self, detail: str) -> None:
        health = ""
        for line in detail.splitlines():
            if line.lower().startswith("health:"):
                health = line.split(":", 1)[-1].strip().upper()
                break
        if not health:
            self.detail_health.config(text="", fg="#666")
            return
        if health == "OK":
            color = "#22863a"
        elif health == "WARN":
            color = "#b26a00"
        else:
            color = "#b00020"
        self.detail_health.config(text=f"Health: {health}", fg=color)

    def _collect_items(self, solver: Any) -> List[Tuple[str, List[WireItem]]]:
        sections: List[Tuple[str, List[WireItem]]] = []
        enabled_plugin_keys = set()
        enabled_bias_keys = set()

        # Solver section
        solver_items: List[WireItem] = []
        if hasattr(solver, "enable_bias"):
            def _toggle_bias_module(flag: bool):
                setattr(solver, "enable_bias", bool(flag))
            solver_items.append(
                WireItem(
                    label="BiasModule enabled",
                    enabled=bool(getattr(solver, "enable_bias", False)),
                    on_toggle=_toggle_bias_module,
                    detail="Enable/disable bias module for objective adjustments.",
                    kind="solver",
                )
            )
            setattr(solver_items[-1], "_delta_key", "solver.bias_module.enabled")
        sections.append(("Solver", solver_items))

        # Adapter section
        adapter_items: List[WireItem] = []
        adapter = getattr(solver, "adapter", None)
        if adapter is not None:
            adapter_items.append(
                WireItem(
                    label=adapter.__class__.__name__,
                    enabled=True,
                    on_toggle=lambda _flag: None,
                    detail=f"Adapter: {adapter.__class__.__name__} (fixed)",
                    kind="adapter",
                )
            )
            setattr(adapter_items[-1], "_delta_key", "adapter.class")
            # Multi-strategy children
            if hasattr(adapter, "strategies"):
                for spec in getattr(adapter, "strategies", []):
                    name = getattr(spec, "name", getattr(spec.adapter, "name", "strategy"))
                    def _make_toggle(s: Any):
                        def _t(flag: bool):
                            s.enabled = bool(flag)
                            # sync unit flags if present
                            units = getattr(adapter, "units", None)
                            if units:
                                for unit in units:
                                    if getattr(unit, "role", None) == s.name:
                                        unit.enabled = bool(flag)
                        return _t
                    adapter_items.append(
                        WireItem(
                            label=f"strategy: {name}",
                            enabled=bool(getattr(spec, "enabled", True)),
                            on_toggle=_make_toggle(spec),
                            detail=f"Strategy adapter: {spec.adapter.__class__.__name__}",
                            kind="adapter",
                        )
                    )
                    setattr(adapter_items[-1], "_delta_key", f"strategy.{name}.enabled")
            # Role-based multi-strategy (RoleSpec/units)
            if hasattr(adapter, "roles"):
                for role in getattr(adapter, "roles", []):
                    name = getattr(role, "name", "role")

                    def _make_role_toggle(r: Any):
                        def _t(flag: bool):
                            r.enabled = bool(flag)
                            units = getattr(adapter, "units", None)
                            if units:
                                for unit in units:
                                    if getattr(unit, "role", None) == r.name:
                                        unit.enabled = bool(flag)
                        return _t

                    adapter_items.append(
                        WireItem(
                            label=f"role: {name}",
                            enabled=bool(getattr(role, "enabled", True)),
                            on_toggle=_make_role_toggle(role),
                            detail=f"Role adapter: {getattr(role, 'adapter', None).__class__.__name__}",
                            kind="adapter",
                        )
                    )
                    setattr(adapter_items[-1], "_delta_key", f"role.{name}.enabled")
            elif hasattr(adapter, "units"):
                role_names = []
                for unit in getattr(adapter, "units", []):
                    rname = getattr(unit, "role", None)
                    if rname and rname not in role_names:
                        role_names.append(rname)
                for name in role_names:
                    def _make_unit_toggle(role_name: str):
                        def _t(flag: bool):
                            for unit in getattr(adapter, "units", []):
                                if getattr(unit, "role", None) == role_name:
                                    unit.enabled = bool(flag)
                        return _t

                    adapter_items.append(
                        WireItem(
                            label=f"role: {name}",
                            enabled=bool(
                                any(
                                    getattr(u, "enabled", True)
                                    for u in getattr(adapter, "units", [])
                                    if getattr(u, "role", None) == name
                                )
                            ),
                            on_toggle=_make_unit_toggle(name),
                            detail=f"Role units: {name}",
                            kind="adapter",
                        )
                    )
                    setattr(adapter_items[-1], "_delta_key", f"role.{name}.enabled")
        sections.append(("Adapter", adapter_items))

        # Pipeline section
        pipeline_items: List[WireItem] = []
        pipeline = getattr(solver, "representation_pipeline", None)
        if pipeline is not None:
            for attr in ("initializer", "mutator", "repair", "codec"):
                comp = getattr(pipeline, attr, None)
                enabled = comp is not None
                if comp is None and attr in self._pipeline_cache:
                    comp = self._pipeline_cache.get(attr)
                if comp is None:
                    continue
                if attr not in self._pipeline_cache:
                    self._pipeline_cache[attr] = comp

                def _make_toggle(a: str):
                    def _t(flag: bool):
                        if flag:
                            setattr(pipeline, a, self._pipeline_cache.get(a))
                        else:
                            setattr(pipeline, a, None)
                    return _t

                pipeline_items.append(
                    WireItem(
                        label=f"{attr}: {comp.__class__.__name__}",
                        enabled=bool(enabled),
                        on_toggle=_make_toggle(attr),
                        detail=f"Pipeline {attr}: {comp.__class__.__name__}",
                        kind="pipeline",
                    )
                )
                setattr(pipeline_items[-1], "_delta_key", f"pipeline.{attr}")
        sections.append(("Pipeline", pipeline_items))

        # Bias section
        bias_items: List[WireItem] = []
        bias_module = getattr(solver, "bias_module", None)
        if bias_module is not None:
            manager = getattr(bias_module, "_manager", None)
            if manager is not None:
                algo_mgr = getattr(manager, "algorithmic_manager", None)
                dom_mgr = getattr(manager, "domain_manager", None)
                for group_name, mgr in (("algorithmic", algo_mgr), ("domain", dom_mgr)):
                    if mgr is None:
                        continue
                    for bias in getattr(mgr, "biases", {}).values():
                        def _make_toggle(b: Any):
                            def _t(flag: bool):
                                b.enabled = bool(flag)
                            return _t
                        label = f"{bias.name} ({group_name})"
                        bias_items.append(
                            WireItem(
                                label=label,
                                enabled=bool(getattr(bias, "enabled", True)),
                                on_toggle=_make_toggle(bias),
                                detail=f"Bias: {bias.__class__.__name__}",
                                kind="bias",
                            )
                        )
                        setattr(bias_items[-1], "_delta_key", f"bias.{bias.name}.enabled")
                        if self.catalog_view:
                            bias_key = self.catalog_view.key_for_bias(bias.name)
                            if bias_key:
                                enabled_bias_keys.add(bias_key)
                                setattr(bias_items[-1], "_raw_name", bias.name)
        sections.append(("Biases", bias_items))

        # Plugin section
        plugin_items: List[WireItem] = []
        plugin_mgr = getattr(solver, "plugin_manager", None)
        if plugin_mgr is not None:
            for plugin in plugin_mgr.list_plugins(enabled_only=False):
                def _make_toggle(p: Any):
                    def _t(flag: bool):
                        p.enabled = bool(flag)
                    return _t
                plugin_items.append(
                    WireItem(
                        label=f"{plugin.name} ({plugin.__class__.__name__})",
                        enabled=bool(getattr(plugin, "enabled", True)),
                        on_toggle=_make_toggle(plugin),
                        detail=f"Plugin: {plugin.__class__.__name__}",
                        kind="plugin",
                    )
                )
                setattr(plugin_items[-1], "_delta_key", f"plugin.{plugin.name}.enabled")
                if self.catalog_view:
                    plugin_key = self.catalog_view.key_for_plugin(plugin.name)
                    if plugin_key:
                        enabled_plugin_keys.add(plugin_key)
        sections.append(("Plugins", plugin_items))

        # companions/missing hints
        if self.catalog_view and (enabled_plugin_keys or enabled_bias_keys):
            def _with_companion_hint(items: List[WireItem]) -> List[WireItem]:
                out: List[WireItem] = []
                for it in items:
                    companions = []
                    if it.kind == "plugin":
                        key = self.catalog_view.key_for_plugin(it.label.split(" ")[0])
                        if key and key in self.catalog:
                            companions = self.catalog[key].get("companions") or []
                    if it.kind == "bias":
                        name = it.label.split(" ")[0]
                        key = self.catalog_view.key_for_bias(name)
                        if key and key in self.catalog:
                            companions = self.catalog[key].get("companions") or []
                    missing = []
                    for c in companions:
                        if c.startswith("suite."):
                            continue
                        if c in enabled_plugin_keys or c in enabled_bias_keys:
                            continue
                        missing.append(c)
                    if missing:
                        setattr(it, "_missing", missing)
                        it.detail = f"{it.detail}\nhealth: WARN\ncompanions: {companions}\nmissing: {missing}"
                    else:
                        it.detail = f"{it.detail}\nhealth: OK"
                    out.append(it)
                return out
            sections = [(name, _with_companion_hint(items)) for (name, items) in sections]
        return sections


def _load_entry(entry: str) -> Callable[[], Any]:
    import sys

    if ":" in entry:
        path_str, func_name = entry.split(":", 1)
    else:
        path_str, func_name = entry, "build_solver"

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Entry not found: {path}")

    module_name = f"nsgablack_entry_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[call-arg]

    func = getattr(module, func_name, None)
    if func is None or not callable(func):
        raise AttributeError(f"Function not found or not callable: {func_name}")

    def _builder():
        return func()
    return _builder
def launch_from_builder(builder: Callable[[], Any], *, entry_label: str = "<in-code>") -> int:
    """Launch UI directly from a build_solver() callable."""
    app = VisualizerApp(builder, entry=entry_label)
    app.mainloop()
    return 0


def launch_from_entry(entry: str) -> int:
    """Launch UI from a 'path.py:build_solver' entry string."""
    builder = _load_entry(entry)
    app = VisualizerApp(builder, entry=entry)
    app.mainloop()
    return 0


def maybe_launch_ui(
    builder: Callable[[], Any],
    *,
    entry_label: str = "<in-code>",
    env_var: str = "NSGABLACK_UI",
) -> bool:
    """Launch UI if env_var is truthy; return True if UI launched."""
    import os

    if os.environ.get(env_var, "0").strip().lower() in {"1", "true", "yes", "on"}:
        launch_from_builder(builder, entry_label=entry_label)
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry", required=True, help="path/to/script.py:build_solver")
    args = parser.parse_args()

    builder = _load_entry(args.entry)
    app = VisualizerApp(builder, entry=args.entry)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
