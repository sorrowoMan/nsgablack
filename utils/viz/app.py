import argparse
import hashlib
import importlib.util
import re
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..context.context_contracts import get_component_contract
from .ui.catalog_view import CatalogView
from .ui.context_view import ContextView
from .ui.contrib_view import ContributionView
from .ui.doctor_view import DoctorView
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
    # View profiles are intentionally non-cumulative.
    # Each profile serves a different task focus with reduced noise.
    _MODE_TABS = {
        "Build": ("details", "catalog", "register", "context"),
        "Run": ("run", "contribution", "trajectory", "catalog", "register"),
        "Audit": ("details", "context", "doctor", "contribution", "register"),
    }

    def __init__(
        self,
        builder: Optional[Callable[[], Any]],
        entry: str,
        *,
        workspace: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self.title("NSGABlack Run Inspector")
        self.geometry("980x720")
        self.builder = builder
        self.entry = entry
        self.workspace = Path(workspace).resolve() if workspace is not None else None

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
        self._is_running: bool = False

        self.run_view: Optional[RunView] = None
        self.contrib_view: Optional[ContributionView] = None
        self.catalog_view: Optional[CatalogView] = None
        self.context_view: Optional[ContextView] = None
        self.doctor_view: Optional[DoctorView] = None
        self._entry_path_var = tk.StringVar(value="")
        self._entry_func_var = tk.StringVar(value="build_solver")
        self._entry_label_var = tk.StringVar(value="")
        self._ui_mode_var = tk.StringVar(value="Build")
        self._ui_tab_specs: List[Tuple[str, str, ttk.Frame]] = []

        self._build_ui()
        self.report_callback_exception = self._on_tk_callback_exception
        self._apply_entry_to_controls()
        self._update_entry_label()
        self._rebuild_solver()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=8)

        ttk.Label(top, text="Run Inspector", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(top, textvariable=self._entry_label_var, foreground="#666").pack(anchor="w")
        load_row = ttk.Frame(top)
        load_row.pack(fill="x", pady=(6, 0))
        ttk.Label(load_row, text="File").pack(side="left")
        ttk.Entry(load_row, textvariable=self._entry_path_var).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(load_row, text="Browse", command=self._browse_entry_file).pack(side="left")
        ttk.Label(load_row, text="Func").pack(side="left", padx=(8, 0))
        ttk.Entry(load_row, textvariable=self._entry_func_var, width=20).pack(side="left", padx=(4, 6))
        ttk.Button(load_row, text="Load", command=self._load_selected_entry).pack(side="left")
        ttk.Button(load_row, text="Refresh", command=self._refresh_current_entry).pack(side="left", padx=(6, 0))
        ttk.Label(load_row, text="View").pack(side="left", padx=(10, 0))
        mode_group = ttk.Frame(load_row)
        mode_group.pack(side="left", padx=(4, 0))
        for mode, text in (
            ("Build", "Build(装配)"),
            ("Run", "Run(实验)"),
            ("Audit", "Audit(审计)"),
        ):
            ttk.Radiobutton(
                mode_group,
                text=text,
                value=mode,
                variable=self._ui_mode_var,
                command=self._on_ui_mode_change,
            ).pack(side="left", padx=(0, 4))

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
        register_tab = ttk.Frame(notebook)
        context_tab = ttk.Frame(notebook)
        doctor_tab = ttk.Frame(notebook)
        self._tab_details = details_tab
        self._tab_run = run_tab
        self._tab_contrib = contrib_tab
        self._tab_traj = traj_tab
        self._tab_catalog = catalog_tab
        self._tab_register = register_tab
        self._tab_context = context_tab
        self._tab_doctor = doctor_tab
        self._ui_tab_specs = [
            ("details", "Details", details_tab),
            ("run", "Run", run_tab),
            ("contribution", "Contribution", contrib_tab),
            ("trajectory", "Trajectory", traj_tab),
            ("catalog", "Catalog", catalog_tab),
            ("register", "Register", register_tab),
            ("context", "Context", context_tab),
            ("doctor", "Doctor", doctor_tab),
        ]

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
        self._build_register_tab(register_tab)
        self.context_view = ContextView(self, context_tab)
        self.doctor_view = DoctorView(self, doctor_tab)
        self.catalog = self.catalog_view.load_catalog()
        self._apply_ui_mode(force=True)

    def _build_register_tab(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="Component Registration", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text="Register marked components and edit catalog metadata with source sync.",
            foreground="#666",
        ).pack(anchor="w", pady=(0, 8))
        card = ttk.LabelFrame(tab, text="Catalog Entry")
        card.pack(fill="x")
        action_row = ttk.Frame(card)
        action_row.pack(fill="x", padx=8, pady=(8, 4))

        def _open_register() -> None:
            if self.catalog_view is None:
                return
            self.catalog_view.open_register_dialog()

        ttk.Button(action_row, text="Add Entry", command=_open_register).pack(side="left")

        row = ttk.Frame(card)
        row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(
            row,
            text="Open Add/Update dialog to scan marked classes, edit metadata, and write catalog entries.",
            foreground="#666",
        ).pack(side="left", fill="x", expand=True)

    def _apply_ui_mode(self, *, force: bool = False) -> None:
        notebook = getattr(self, "_notebook", None)
        if notebook is None:
            return
        mode = str(self._ui_mode_var.get() or "Build").strip().title()
        if mode not in self._MODE_TABS:
            mode = "Build"
            self._ui_mode_var.set(mode)

        allowed_keys = set(self._MODE_TABS.get(mode, ()))
        visible_now = set(notebook.tabs())
        target_frames = {
            str(frame): (key, label, frame)
            for (key, label, frame) in self._ui_tab_specs
            if key in allowed_keys
        }

        # Remove hidden tabs first.
        for tab_id in list(visible_now):
            if tab_id not in target_frames:
                notebook.forget(tab_id)

        # Re-add in canonical order to keep predictable tab positions.
        for key, label, frame in self._ui_tab_specs:
            if key not in allowed_keys:
                continue
            tab_id = str(frame)
            if tab_id not in notebook.tabs():
                notebook.add(frame, text=label)
            else:
                notebook.tab(frame, text=label)

        # Ensure current tab is valid.
        tabs = notebook.tabs()
        if tabs:
            try:
                current = notebook.select()
            except Exception:
                current = ""
            if force or current not in tabs:
                notebook.select(tabs[0])

    def _on_ui_mode_change(self) -> None:
        self._apply_ui_mode()
        self._set_status(f"UI view: {self._ui_mode_var.get().strip().title()}")

    def _apply_entry_to_controls(self) -> None:
        if not self.entry:
            return
        if ":" in self.entry:
            path_str, func = self.entry.rsplit(":", 1)
        else:
            path_str, func = self.entry, "build_solver"
        self._entry_path_var.set(path_str)
        self._entry_func_var.set(func or "build_solver")

    def _update_entry_label(self) -> None:
        entry_text = self.entry if self.entry else "(empty start)"
        workspace_text = str(self.workspace) if self.workspace else str(Path.cwd())
        self._entry_label_var.set(f"Entry: {entry_text} | Workspace: {workspace_text}")

    def _set_status(self, text: str) -> None:
        if self.run_view:
            self.run_view.status_label.config(text=text)

    def _on_tk_callback_exception(self, exc: type[BaseException], value: BaseException, tb) -> None:  # type: ignore[override]
        msg = f"{exc.__name__}: {value}"
        self._set_status(f"UI callback error: {msg}")
        trace = "".join(traceback.format_exception(exc, value, tb))
        try:
            messagebox.showerror(
                "Run Inspector Error",
                f"{msg}\n\nPlease check current wiring/context and retry.\n\n{trace[-1200:]}",
            )
        except Exception:
            pass

    def search_catalog_for_context_key(self, context_key: str, *, role: str = "all") -> None:
        key = str(context_key or "").strip()
        if not key or self.catalog_view is None:
            return

        mode = str(self._ui_mode_var.get() or "Build").strip().title()
        if "catalog" not in set(self._MODE_TABS.get(mode, ())):
            self._ui_mode_var.set("Build")
            self._apply_ui_mode()

        self.catalog_view.search_context_key(key, role=role)
        if getattr(self, "_notebook", None) is not None:
            try:
                self._notebook.select(self._tab_catalog)
            except Exception:
                pass
        self._set_status(f"Catalog context search: key={key} role={role}")

    def search_catalog_for_component(self, component_name: str) -> None:
        key = str(component_name or "").strip()
        if not key or self.catalog_view is None:
            return
        mode = str(self._ui_mode_var.get() or "Build").strip().title()
        if "catalog" not in set(self._MODE_TABS.get(mode, ())):
            self._ui_mode_var.set("Build")
            self._apply_ui_mode()
        self.catalog_view.catalog_match_var.set("name")
        self.catalog_view.catalog_query_var.set(key)
        self.catalog_view.search()
        if getattr(self, "_notebook", None) is not None:
            try:
                self._notebook.select(self._tab_catalog)
            except Exception:
                pass
        self._set_status(f"Catalog component search: {key}")

    def show_component_detail(self, component_name: str) -> bool:
        target = str(component_name or "").strip()
        if not target:
            return False
        tokens = [t for t in re.split(r"[\s\.:#>/_,-]+", target.lower()) if len(t) >= 2]
        best_item: Optional[WireItem] = None
        best_score = -1
        for _section, items in self.items:
            for item in items:
                comp = getattr(item, "_component", None)
                class_name = comp.__class__.__name__.lower() if comp is not None else ""
                candidate = " ".join([item.label.lower(), item.kind.lower(), class_name])
                score = 0
                if target.lower() in candidate:
                    score += 8
                for tok in tokens:
                    if tok in candidate:
                        score += 2
                if class_name and class_name in target.lower():
                    score += 6
                if score > best_score:
                    best_score = score
                    best_item = item
        if best_item is None or best_score <= 0:
            self._set_status(f"Component detail not found: {target}")
            return False
        self._show_wire_item_detail(best_item)
        self._set_status(f"Opened component detail: {target}")
        return True

    def _resolve_entry_file(self, raw_path: str) -> Path:
        text = str(raw_path).strip()
        if not text:
            raise ValueError("Entry file is empty")
        p = Path(text)
        if not p.is_absolute():
            base = self.workspace or Path.cwd()
            p = (base / p).resolve()
        else:
            p = p.resolve()
        return p

    def _browse_entry_file(self) -> None:
        start_dir = str(self.workspace or Path.cwd())
        chosen = filedialog.askopenfilename(
            title="Select solver entry file",
            initialdir=start_dir,
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        if chosen:
            self._entry_path_var.set(chosen)

    def _load_selected_entry(self) -> None:
        if self._is_running:
            self._set_status("Run is in progress; skip loading a new entry")
            return
        try:
            path = self._resolve_entry_file(self._entry_path_var.get())
            func = self._entry_func_var.get().strip() or "build_solver"
            entry = f"{path}:{func}"
            self.builder = _load_entry(entry)
            self.entry = entry
            self.workspace = path.parent
            self._update_entry_label()
            self._refresh_catalog()
            if self.doctor_view:
                self.doctor_view.use_default_path()
                self.doctor_view.refresh_state()
            self._set_status(f"Loaded entry: {entry}")
            self._rebuild_solver()
        except Exception as exc:
            self._set_status(f"Load failed: {exc}")
            if self.doctor_view:
                self.doctor_view.refresh_state()

    def _refresh_current_entry(self) -> None:
        if self._is_running:
            self._set_status("Run is in progress; skip entry reload")
            return
        if not self.entry:
            self._set_status("No entry loaded; use Browse/Load first")
            self._refresh_catalog()
            if self.doctor_view:
                self.doctor_view.refresh_state()
            return
        try:
            self.builder = _load_entry(self.entry)
            self._refresh_catalog()
            self._set_status("Entry reloaded")
            self._rebuild_solver()
            if self.doctor_view:
                self.doctor_view.refresh_state()
        except Exception as exc:
            self.solver = None
            self.items = []
            for child in self.scroll_frame.winfo_children():
                child.destroy()
            self._set_status(f"Refresh failed: {exc}")
            if self.run_view:
                self.run_view.update_sensitivity_button()
            if self.context_view:
                self.context_view.refresh()
            if self.doctor_view:
                self.doctor_view.refresh_state()

    def _refresh_catalog(self) -> None:
        if self.catalog_view:
            self.catalog = self.catalog_view.load_catalog()

    def _rebuild_solver(self) -> None:
        if self.builder is None:
            self.solver = None
            self.items = []
            for child in self.scroll_frame.winfo_children():
                child.destroy()
            self._set_status("Empty mode: load an entry file to inspect wiring")
            if self.run_view:
                self.run_view.update_sensitivity_button()
            if self.context_view:
                self.context_view.refresh()
            if self.doctor_view:
                self.doctor_view.refresh_state()
            return
        try:
            self.solver = self.builder()
        except Exception as exc:
            self.solver = None
            self.items = []
            for child in self.scroll_frame.winfo_children():
                child.destroy()
            self._set_status(f"Build failed: {exc}")
            if self.run_view:
                self.run_view.update_sensitivity_button()
            if self.doctor_view:
                self.doctor_view.refresh_state()
            return
        self._pipeline_cache = {}
        self.items = self._collect_items(self.solver)
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self._render_items()
        if self.run_view:
            self.run_view.update_sensitivity_button()
        if self.context_view:
            self.context_view.refresh()
        if self.contrib_view:
            self.contrib_view.reload_run_choices()
        if self.run_view:
            self.run_view.status_label.config(text="Ready")
        if self.doctor_view:
            self.doctor_view.refresh_state()

    def _refresh_sections(self) -> None:
        if self.solver is not None:
            self.items = self._collect_items(self.solver)
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self._render_items()
        if self.run_view:
            self.run_view.update_sensitivity_button()
        if self.context_view:
            self.context_view.refresh()

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
                        self._show_wire_item_detail(cb_item)
                    return _info

                info = ttk.Button(row, text="i", width=2, command=_make_info(item))
                info.pack(side="right")

    def _show_wire_item_detail(self, item: WireItem) -> None:
        self.detail_title.config(text=item.label)
        self.detail_kind.config(text=item.kind)
        self._update_health(item.detail)
        self.detail_summary.config(state="normal")
        self.detail_summary.delete("1.0", "end")
        self.detail_summary.insert("1.0", item.detail)
        self.detail_summary.config(state="disabled")
        if getattr(self, "_notebook", None) is not None:
            try:
                self._notebook.select(self._tab_details)
            except Exception:
                pass
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

    def _aggregate_health(self, statuses: List[str]) -> str:
        normalized = [str(s or "").upper() for s in statuses if str(s or "").strip()]
        if not normalized:
            return "INFO"
        if any(s == "WARN" for s in normalized):
            return "WARN"
        if all(s == "OK" for s in normalized):
            return "OK"
        return "INFO"

    def _pipeline_component_health(self, attr: str, comp: Any, solver: Any) -> Tuple[str, str]:
        if comp is None:
            return "WARN", f"Pipeline {attr} is missing."

        if attr == "initializer":
            return ("OK", "Initializer is attached and callable.") if callable(getattr(comp, "initialize", None)) else (
                "WARN",
                "Initializer exists but has no initialize() method.",
            )
        if attr == "mutator":
            if not callable(getattr(comp, "mutate", None)):
                return "WARN", "Mutator exists but has no mutate() method."
            adapter = getattr(solver, "adapter", None)
            if adapter is not None and adapter.__class__.__name__ == "VNSAdapter":
                consumes_context = any(hasattr(comp, k) for k in ("sigma_key", "k_key", "context_key", "key"))
                if not consumes_context:
                    return "WARN", "VNS is active; mutator may not consume VNS context keys."
            return "OK", "Mutator is attached and callable."
        if attr == "repair":
            return ("OK", "Repair is attached and callable.") if callable(getattr(comp, "repair", None)) else (
                "WARN",
                "Repair exists but has no repair() method.",
            )
        if attr == "codec":
            has_encode = callable(getattr(comp, "encode", None))
            has_decode = callable(getattr(comp, "decode", None))
            if has_encode and has_decode:
                return "OK", "Codec has both encode()/decode()."
            if has_encode or has_decode:
                return "WARN", "Codec is partial; missing encode() or decode()."
            return "WARN", "Codec exists but encode()/decode() are missing."
        return "INFO", "No built-in runtime rule for this pipeline component."

    def _adapter_runtime_health(
        self,
        solver: Any,
        adapter_obj: Any,
        _visited: Optional[set[int]] = None,
    ) -> Tuple[str, str]:
        """Best-effort runtime health check for adapter+pipeline/plugin wiring."""
        if adapter_obj is None:
            return "INFO", "No adapter instance available for runtime checks."
        if _visited is None:
            _visited = set()
        marker = id(adapter_obj)
        if marker in _visited:
            return "INFO", "Adapter health recursion detected; skip nested re-evaluation."
        _visited.add(marker)
        name = adapter_obj.__class__.__name__
        pipeline = getattr(solver, "representation_pipeline", None)
        mutator = getattr(pipeline, "mutator", None) if pipeline is not None else None

        if name == "VNSAdapter":
            if mutator is None:
                return "WARN", "VNS requires a mutator; current pipeline.mutator is None."
            consumes_context = any(hasattr(mutator, k) for k in ("sigma_key", "k_key", "context_key", "key"))
            if not consumes_context:
                return "WARN", "Mutator may not consume VNS context keys; neighborhood control can degrade."
            return "OK", "Mutator appears context-aware for VNS sigma/k."

        if name == "MOEADAdapter":
            pm = getattr(solver, "plugin_manager", None)
            plugins = pm.list_plugins(enabled_only=False) if pm is not None and hasattr(pm, "list_plugins") else []
            has_archive = any("archive" in str(getattr(p, "name", "")).lower() for p in plugins)
            if not has_archive:
                return "WARN", "MOEA/D typically needs an archive plugin to expose Pareto outputs."
            return "OK", "Archive plugin detected for MOEA/D output tracking."

        if name == "MultiStrategyControllerAdapter":
            child_status: List[str] = []
            child_notes: List[str] = []
            seen_children: set[int] = set()

            if hasattr(adapter_obj, "strategies"):
                for spec in getattr(adapter_obj, "strategies", []) or []:
                    child = getattr(spec, "adapter", None)
                    if child is None or id(child) in seen_children:
                        continue
                    seen_children.add(id(child))
                    st, note = self._adapter_runtime_health(solver, child, _visited=_visited)
                    child_status.append(st)
                    child_notes.append(f"strategy:{getattr(spec, 'name', 'strategy')}={st}")
                    if note:
                        child_notes.append(f"  - {note}")

            if hasattr(adapter_obj, "units"):
                for unit in getattr(adapter_obj, "units", []) or []:
                    child = getattr(unit, "adapter", None)
                    if child is None or id(child) in seen_children:
                        continue
                    seen_children.add(id(child))
                    st, note = self._adapter_runtime_health(solver, child, _visited=_visited)
                    child_status.append(st)
                    child_notes.append(
                        f"role:{getattr(unit, 'role', 'role')}#{getattr(unit, 'unit_id', '?')}={st}"
                    )
                    if note:
                        child_notes.append(f"  - {note}")

            if hasattr(adapter_obj, "roles"):
                infer_fn = getattr(adapter_obj, "_instantiate_role_adapter", None)
                for role in getattr(adapter_obj, "roles", []) or []:
                    child = getattr(role, "adapter", None)
                    if callable(child) and callable(infer_fn):
                        try:
                            child = infer_fn(child, 0)
                        except Exception:
                            child = None
                    if child is None or id(child) in seen_children:
                        continue
                    seen_children.add(id(child))
                    st, note = self._adapter_runtime_health(solver, child, _visited=_visited)
                    child_status.append(st)
                    child_notes.append(f"role:{getattr(role, 'name', 'role')}={st}")
                    if note:
                        child_notes.append(f"  - {note}")

            if not child_status:
                return "INFO", "Controller has no resolvable child adapters to evaluate."
            overall = self._aggregate_health(child_status)
            return overall, " | ".join(child_notes)

        return "INFO", "No built-in runtime rule for this adapter."

    def _contract_block(self, component: Any) -> str:
        if component is None:
            return ""
        try:
            contract = get_component_contract(component)
        except Exception:
            contract = None
        if contract is None:
            return ""

        def _fmt(values: Any) -> str:
            vals = list(values or [])
            return ", ".join(str(v) for v in vals) if vals else "(none)"

        notes = str(contract.notes).strip() if contract.notes else "(none)"
        lines = [
            "",
            "Context Contract",
            f"context_requires: {_fmt(contract.requires)}",
            f"context_provides: {_fmt(contract.provides)}",
            f"context_mutates: {_fmt(contract.mutates)}",
            f"context_cache: {_fmt(contract.cache)}",
            f"context_notes: {notes}",
        ]
        return "\n".join(lines)

    def _detail_with_contract(self, detail: str, component: Any) -> str:
        block = self._contract_block(component)
        if not block:
            return detail
        return f"{detail}{block}"

    def _append_health(self, detail: str, health: str, note: str) -> str:
        text = str(detail or "")
        if "health:" in text.lower():
            return text
        extra = f"health: {str(health).upper()}"
        if note:
            extra = f"{extra}\n{note}"
        if text and not text.endswith("\n"):
            text = f"{text}\n"
        return f"{text}{extra}"

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
            adapter_health, adapter_note = self._adapter_runtime_health(solver, adapter)
            adapter_items.append(
                WireItem(
                    label=adapter.__class__.__name__,
                    enabled=True,
                    on_toggle=lambda _flag: None,
                    detail=self._detail_with_contract(
                        self._append_health(
                            f"Adapter: {adapter.__class__.__name__} (fixed)",
                            adapter_health,
                            adapter_note,
                        ),
                        adapter,
                    ),
                    kind="adapter",
                )
            )
            setattr(adapter_items[-1], "_component", adapter)
            setattr(adapter_items[-1], "_delta_key", "adapter.class")
            # Multi-strategy children
            if hasattr(adapter, "strategies"):
                for spec in getattr(adapter, "strategies", []):
                    name = getattr(spec, "name", getattr(spec.adapter, "name", "strategy"))
                    adapter_name = spec.adapter.__class__.__name__
                    health, note = self._adapter_runtime_health(solver, spec.adapter)
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
                            label=f"strategy: {name} -> {adapter_name}",
                            enabled=bool(getattr(spec, "enabled", True)),
                            on_toggle=_make_toggle(spec),
                            detail=self._detail_with_contract(
                                f"Strategy adapter: {adapter_name}\nhealth: {health}\n{note}",
                                spec.adapter,
                            ),
                            kind="adapter",
                        )
                    )
                    setattr(adapter_items[-1], "_component", spec.adapter)
                    setattr(adapter_items[-1], "_delta_key", f"strategy.{name}.enabled")
            # Role-based multi-strategy (RoleSpec/units)
            if hasattr(adapter, "roles"):
                for role in getattr(adapter, "roles", []):
                    name = getattr(role, "name", "role")
                    role_adapter_obj = None
                    role_units = [
                        u for u in getattr(adapter, "units", [])
                        if getattr(u, "role", None) == name and getattr(u, "adapter", None) is not None
                    ]
                    role_adapter_names = sorted({u.adapter.__class__.__name__ for u in role_units})
                    if role_adapter_names:
                        role_adapter_name = ", ".join(role_adapter_names)
                        role_adapter_obj = role_units[0].adapter
                    else:
                        role_adapter = getattr(role, "adapter", None)
                        role_adapter_name = role_adapter.__class__.__name__ if role_adapter is not None else "(none)"
                        # roles often hold a factory callable before setup(); infer target adapter class best-effort.
                        if callable(role_adapter):
                            try:
                                infer_fn = getattr(adapter, "_instantiate_role_adapter", None)
                                if callable(infer_fn):
                                    inferred = infer_fn(role_adapter, 0)
                                    role_adapter_name = inferred.__class__.__name__
                                    role_adapter_obj = inferred
                                else:
                                    role_adapter_name = "factory"
                            except Exception:
                                role_adapter_name = "factory"
                        else:
                            role_adapter_obj = role_adapter

                    health, note = self._adapter_runtime_health(solver, role_adapter_obj)

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
                            label=f"role: {name} -> {role_adapter_name}",
                            enabled=bool(getattr(role, "enabled", True)),
                            on_toggle=_make_role_toggle(role),
                            detail=self._detail_with_contract(
                                f"Role adapter: {role_adapter_name}\nhealth: {health}\n{note}",
                                role_adapter_obj,
                            ),
                            kind="adapter",
                        )
                    )
                    setattr(adapter_items[-1], "_component", role_adapter_obj)
                    setattr(adapter_items[-1], "_delta_key", f"role.{name}.enabled")
            elif hasattr(adapter, "units"):
                role_names = []
                for unit in getattr(adapter, "units", []):
                    rname = getattr(unit, "role", None)
                    if rname and rname not in role_names:
                        role_names.append(rname)
                for name in role_names:
                    role_units = [
                        u for u in getattr(adapter, "units", [])
                        if getattr(u, "role", None) == name
                    ]
                    role_adapter_names = sorted(
                        {
                            u.adapter.__class__.__name__
                            for u in role_units
                            if getattr(u, "adapter", None) is not None
                        }
                    )
                    role_adapter_text = ", ".join(role_adapter_names) if role_adapter_names else "(unknown)"
                    role_adapter_obj = None
                    for u in role_units:
                        if getattr(u, "adapter", None) is not None:
                            role_adapter_obj = u.adapter
                            break
                    health, note = self._adapter_runtime_health(solver, role_adapter_obj)

                    def _make_unit_toggle(role_name: str):
                        def _t(flag: bool):
                            for unit in getattr(adapter, "units", []):
                                if getattr(unit, "role", None) == role_name:
                                    unit.enabled = bool(flag)
                        return _t

                    adapter_items.append(
                        WireItem(
                            label=f"role: {name} -> {role_adapter_text}",
                            enabled=bool(
                                any(
                                    getattr(u, "enabled", True)
                                    for u in getattr(adapter, "units", [])
                                    if getattr(u, "role", None) == name
                                )
                            ),
                            on_toggle=_make_unit_toggle(name),
                            detail=self._detail_with_contract(
                                f"Role units: {name}\nRole adapters: {role_adapter_text}\nhealth: {health}\n{note}",
                                role_adapter_obj,
                            ),
                            kind="adapter",
                        )
                    )
                    setattr(adapter_items[-1], "_component", role_adapter_obj)
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
                        detail=self._detail_with_contract(
                            self._append_health(
                                f"Pipeline {attr}: {comp.__class__.__name__}",
                                *self._pipeline_component_health(attr, comp, solver),
                            ),
                            comp,
                        ),
                        kind="pipeline",
                    )
                )
                setattr(pipeline_items[-1], "_component", comp)
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
                                detail=self._detail_with_contract(
                                    f"Bias: {bias.__class__.__name__}",
                                    bias,
                                ),
                                kind="bias",
                            )
                        )
                        setattr(bias_items[-1], "_component", bias)
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
                        detail=self._detail_with_contract(
                            f"Plugin: {plugin.__class__.__name__}",
                            plugin,
                        ),
                        kind="plugin",
                    )
                )
                setattr(plugin_items[-1], "_component", plugin)
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
                    if it.kind not in {"plugin", "bias"}:
                        if "health:" not in it.detail.lower():
                            comp = getattr(it, "_component", None)
                            if it.kind == "adapter":
                                h, note = self._adapter_runtime_health(solver, comp)
                            elif it.kind == "pipeline":
                                label_prefix = str(it.label).split(":", 1)[0].strip().lower()
                                h, note = self._pipeline_component_health(label_prefix, comp, solver)
                            elif it.kind == "solver":
                                h, note = "OK", "Core solver item is active."
                            else:
                                h, note = "INFO", "No built-in runtime rule for this component."
                            it.detail = self._append_health(it.detail, h, note)
                        out.append(it)
                        continue
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
                        if "health:" in it.detail.lower():
                            it.detail = f"{it.detail}\ncompanions: {companions}\nmissing: {missing}"
                        else:
                            it.detail = f"{it.detail}\nhealth: WARN\ncompanions: {companions}\nmissing: {missing}"
                    else:
                        if "health:" not in it.detail.lower():
                            it.detail = f"{it.detail}\nhealth: OK"
                    out.append(it)
                return out
            sections = [(name, _with_companion_hint(items)) for (name, items) in sections]
        return sections


def _load_entry(entry: str) -> Callable[[], Any]:
    import sys

    if ":" in entry:
        path_str, func_name = entry.rsplit(":", 1)
    else:
        path_str, func_name = entry, "build_solver"

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Entry not found: {path}")

    resolved_path = str(path.resolve())
    module_tag = hashlib.sha1(resolved_path.encode("utf-8")).hexdigest()[:12]
    module_name = f"nsgablack_entry_{path.stem}_{module_tag}"
    importlib.invalidate_caches()
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[call-arg]
    except Exception:
        sys.modules.pop(module_name, None)
        raise

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


def launch_empty(*, workspace: Optional[str] = None) -> int:
    """Launch UI without preloaded solver entry."""
    ws = Path(workspace).resolve() if workspace else Path.cwd()
    app = VisualizerApp(None, entry="", workspace=ws)
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
    parser.add_argument("--entry", default="", help="path/to/script.py:build_solver")
    parser.add_argument("--workspace", default="", help="Workspace folder for empty mode/catalog")
    parser.add_argument("--empty", action="store_true", help="Start without loading an entry")
    args = parser.parse_args()

    if args.empty:
        ws = args.workspace or str(Path.cwd())
        return launch_empty(workspace=ws)
    if args.entry:
        return launch_from_entry(args.entry)
    ws = args.workspace or str(Path.cwd())
    return launch_empty(workspace=ws)


if __name__ == "__main__":
    raise SystemExit(main())
