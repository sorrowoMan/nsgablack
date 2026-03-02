from __future__ import annotations

import re
import time
import weakref
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

from ...context.context_contracts import collect_solver_contracts
from ...context.context_schema import get_context_lifecycle, is_replayable_context, strip_context_for_replay

_BUILTIN_DECLARED_WRITERS: Dict[str, List[str]] = {
    "problem": ["solver.core"],
    "bounds": ["solver.core"],
    "constraints": ["solver.core"],
    "constraint_violation": ["solver.core"],
    "individual_id": ["solver.core"],
    "individual": ["solver.core"],
    "generation": ["solver.core"],
    "step": ["solver.core"],
    "phase_id": ["solver.core"],
    "dynamic": ["solver.core"],
    "snapshot_key": ["solver.core"],
    "snapshot_backend": ["solver.core"],
    "snapshot_schema": ["solver.core"],
    "snapshot_meta": ["solver.core"],
    "population_ref": ["solver.core"],
    "objectives_ref": ["solver.core"],
    "constraint_violations_ref": ["solver.core"],
    "evaluation_count": ["solver.core"],
    "pareto_solutions_ref": ["plugin.pareto_archive"],
    "pareto_objectives_ref": ["plugin.pareto_archive"],
    "history_ref": ["solver.core"],
    "decision_trace_ref": ["plugin.decision_trace"],
    "sequence_graph_ref": ["plugin.sequence_graph"],
    "context_events": ["plugin.async_event_hub"],
}
_BUILTIN_DECLARED_READERS: Dict[str, List[str]] = {
    "generation": ["adapter.*", "plugin.*", "bias_module"],
    "step": ["adapter.*", "plugin.*"],
    "dynamic": ["adapter.*", "plugin.dynamic_switch"],
    "snapshot_key": ["adapter.*", "plugin.*", "bias_module"],
    "population_ref": ["adapter.*", "plugin.*", "bias_module"],
    "objectives_ref": ["adapter.*", "plugin.*", "bias_module"],
    "constraint_violations_ref": ["adapter.*", "plugin.*", "bias_module"],
    "constraints": ["adapter.*", "bias_module"],
    "constraint_violation": ["adapter.*", "bias_module"],
    "evaluation_count": ["plugin.profiler", "plugin.benchmark_harness", "plugin.module_report"],
}


class ContextView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._declared_writers: Dict[str, List[str]] = {}
        self._declared_readers: Dict[str, List[str]] = {}
        self._runtime_writers: Dict[str, str] = {}
        self._component_contracts: Dict[str, Dict[str, List[str]]] = {}
        self._missing_requires_by_component: Dict[str, List[str]] = {}
        self._selected_key = ""
        self._field_selected_component = ""
        self._field_window: Optional[tk.Toplevel] = None
        self._field_summary_var: Optional[tk.StringVar] = None
        self._field_providers_tree: Optional[ttk.Treeview] = None
        self._field_consumers_tree: Optional[ttk.Treeview] = None
        self._field_component_text: Optional[tk.Text] = None
        self._field_notes_text: Optional[tk.Text] = None
        self._declared_cache_solver_ref: Optional[weakref.ReferenceType[Any]] = None
        self._declared_cache_data: Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, Dict[str, List[str]]]] = ({}, {}, {})
        self._catalog_intro_cache: Dict[str, str] = {}
        self._catalog_intro_cache_size: int = -1
        self._refresh_pending_id: Optional[str] = None
        self._refresh_min_interval_sec: float = 0.18
        self._last_refresh_ts: float = 0.0
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Context", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(self.tab, text="Context lifecycle and attribution view.", foreground="#666").pack(anchor="w", pady=(2, 8))
        info = ttk.Frame(self.tab)
        info.pack(fill="x")
        self.replayable_var = tk.StringVar(value="Replayable: unknown")
        self.counts_var = tk.StringVar(value="Field counts: -")
        self.alignment_var = tk.StringVar(value="Contract alignment: unknown")
        self.error_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.replayable_var).pack(anchor="w")
        ttk.Label(info, textvariable=self.counts_var).pack(anchor="w")
        ttk.Label(info, textvariable=self.alignment_var).pack(anchor="w")
        ttk.Label(info, textvariable=self.error_var, foreground="#b00020").pack(anchor="w")

        ctrl = ttk.Frame(self.tab)
        ctrl.pack(fill="x", pady=(6, 4))
        ttk.Button(ctrl, text="Refresh", command=self.request_refresh).pack(side="left")
        ttk.Button(ctrl, text="Replay Keys", command=self.show_replay_keys).pack(side="left", padx=(6, 0))
        self.only_replayable_var = tk.BooleanVar(value=False)
        self.show_declared_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="Replayable", variable=self.only_replayable_var, command=self.request_refresh).pack(side="left", padx=(10, 0))
        ttk.Checkbutton(ctrl, text="Declared Keys", variable=self.show_declared_var, command=self.request_refresh).pack(side="left", padx=(10, 0))

        actions = ttk.Frame(self.tab)
        actions.pack(fill="x", pady=(0, 6))
        self.provider_btn = ttk.Button(actions, text="Providers", command=lambda: self._open_field_window("providers"), state="disabled")
        self.consumer_btn = ttk.Button(actions, text="Consumers", command=lambda: self._open_field_window("consumers"), state="disabled")
        self.field_window_btn = ttk.Button(actions, text="Window", command=lambda: self._open_field_window(""), state="disabled")
        self.provider_btn.pack(side="left")
        self.consumer_btn.pack(side="left", padx=(6, 0))
        self.field_window_btn.pack(side="left", padx=(6, 0))

        table = ttk.Frame(self.tab)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("key", "category", "replayable", "declared_by", "last_writer"), show="headings", height=12)
        for col in ("key", "category", "replayable", "declared_by", "last_writer"):
            self.tree.heading(col, text=col if col != "category" else "lifecycle")
        self.tree.column("key", width=150, stretch=False)
        self.tree.column("category", width=90, anchor="center", stretch=False)
        self.tree.column("replayable", width=90, anchor="center", stretch=False)
        self.tree.column("declared_by", width=180, stretch=False)
        self.tree.column("last_writer", width=170, stretch=False)
        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(self.tab, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(fill="x", pady=(2, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._detail = tk.Text(self.tab, height=7, wrap="word", borderwidth=1, relief="solid")
        self._detail.pack(fill="x", pady=(6, 0))
        self._set_text(self._detail, "Select one context key to view details.")

    def request_refresh(self) -> None:
        self.refresh(force=False)

    def refresh(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force:
            elapsed = now - self._last_refresh_ts
            if elapsed < self._refresh_min_interval_sec:
                wait_ms = max(1, int((self._refresh_min_interval_sec - elapsed) * 1000))
                if self._refresh_pending_id is None:
                    self._refresh_pending_id = self.tab.after(wait_ms, self._on_scheduled_refresh)
                return
        self._cancel_scheduled_refresh()
        self._last_refresh_ts = now
        solver = getattr(self.app, "solver", None)
        if solver is None or not hasattr(solver, "get_context"):
            self._clear_table()
            self._set_error("No active solver context. Load/build an entry first.")
            return
        try:
            ctx = solver.get_context()
        except Exception as exc:
            self._clear_table()
            self._set_error(f"Context read failed: {exc}")
            return
        try:
            declared_writers, declared_readers, contracts = self._collect_declared_io(solver)
            runtime_writers = self._collect_runtime_writers(solver, ctx)
        except Exception as exc:
            self._set_error(f"Context analysis failed: {exc}")
            return
        self._declared_writers, self._declared_readers = declared_writers, declared_readers
        self._runtime_writers, self._component_contracts = runtime_writers, contracts
        self._missing_requires_by_component = self._collect_missing_requires(solver, ctx)

        lifecycle = get_context_lifecycle(ctx)
        keys = set(str(k) for k in ctx.keys())
        if self.show_declared_var.get():
            keys.update(declared_writers.keys())
            keys.update(declared_readers.keys())
        row_payloads: Dict[str, Tuple[str, str, str, str, str]] = {}
        for key in sorted(keys):
            in_ctx = key in ctx
            category = lifecycle.get(key, "custom") if in_ctx else "declared"
            replayable = "-" if category == "declared" else ("no" if category == "cache" else "yes")
            if self.only_replayable_var.get() and replayable != "yes":
                continue
            iid = f"key::{key}"
            row_payloads[iid] = (
                key,
                category,
                replayable,
                self._fmt_list(declared_writers.get(key, [])),
                runtime_writers.get(key, "(none)" if in_ctx else "(not in current context)"),
            )
        self._reconcile_key_rows(row_payloads)

        self.replayable_var.set(f"Replayable: {'yes' if is_replayable_context(ctx) else 'no'}")
        counts: Dict[str, int] = {}
        for key in ctx.keys():
            cat = lifecycle.get(key, "custom")
            counts[cat] = counts.get(cat, 0) + 1
        self.counts_var.set("Field counts: " + " / ".join(f"{k}:{v}" for k, v in counts.items()))
        miss_comp = len(self._missing_requires_by_component)
        miss_fields = sum(len(v) for v in self._missing_requires_by_component.values())
        self.alignment_var.set("Contract alignment: OK" if miss_comp == 0 else f"Contract alignment: MISSING ({miss_comp} components / {miss_fields} fields)")
        self._set_error("")
        self._set_selected_key(self._selected_key)

    def _reconcile_key_rows(self, row_payloads: Dict[str, Tuple[str, str, str, str, str]]) -> None:
        existing = set(self.tree.get_children(""))
        expected = set(row_payloads.keys())
        for iid in sorted(existing - expected):
            self.tree.delete(iid)
        for iid, values in row_payloads.items():
            if self.tree.exists(iid):
                current = tuple(self.tree.item(iid).get("values") or ())
                if current != values:
                    self.tree.item(iid, values=values)
                self.tree.move(iid, "", "end")
            else:
                self.tree.insert("", "end", iid=iid, values=values)

    def show_replay_keys(self) -> None:
        solver = getattr(self.app, "solver", None)
        if solver is None or not hasattr(solver, "get_context"):
            return
        try:
            ctx = solver.get_context()
        except Exception:
            return
        keys = ", ".join(sorted(strip_context_for_replay(ctx).keys(), key=str))
        self._set_text(self._detail, f"Replayable keys:\n{keys}")

    def _on_select(self, _event: Any) -> None:
        sel = self.tree.selection()
        if not sel:
            self._set_selected_key("")
            return
        values = self.tree.item(sel[0]).get("values") or []
        self._set_selected_key(str(values[0]) if values else "")

    def _set_selected_key(self, key: str) -> None:
        self._selected_key = str(key or "").strip()
        state = "normal" if self._selected_key else "disabled"
        self.provider_btn.configure(state=state)
        self.consumer_btn.configure(state=state)
        self.field_window_btn.configure(state=state)
        if not self._selected_key:
            self._set_text(self._detail, "Select one context key to view details.")
            return
        readers = self._declared_readers.get(self._selected_key, [])
        writers = self._declared_writers.get(self._selected_key, [])
        detail = (
            f"key: {self._selected_key}\n"
            f"declared_by: {self._fmt_list(writers)}\n"
            f"read_by: {self._fmt_list(readers)}\n"
            f"last_writer: {self._runtime_writers.get(self._selected_key, '(none)')}\n"
        )
        self._set_text(self._detail, detail)
        self._refresh_field_window()

    def _open_field_window(self, focus: str) -> None:
        if not self._selected_key:
            return
        try:
            if self._field_window is None or not self._field_window.winfo_exists():
                self._build_field_window()
            self._refresh_field_window()
            self._focus_field_window_section(focus)
            self._field_window.deiconify()
            self._field_window.lift()
        except Exception as exc:
            self._set_error(f"Open context window failed: {exc}")

    def _build_field_window(self) -> None:
        win = tk.Toplevel(self.tab)
        win.title("Context Field Window")
        win.geometry("980x620")
        self._field_window = win
        self._field_summary_var = tk.StringVar(value="")
        ttk.Label(win, textvariable=self._field_summary_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(
            win,
            text="Tip: select a component to view Contract + Catalog intro (summary / usage).",
            foreground="#666",
        ).pack(anchor="w", padx=10, pady=(0, 6))
        panel = ttk.Frame(win)
        panel.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        for col in range(3):
            panel.columnconfigure(col, weight=1)
        panel.rowconfigure(0, weight=1)
        self._field_providers_tree = self._make_role_tree(panel, "Providers (provides + mutates)", 0)
        self._field_consumers_tree = self._make_role_tree(panel, "Consumers (requires)", 1)
        box = ttk.LabelFrame(panel, text="Component Contract")
        box.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self._field_component_text = tk.Text(box, wrap="word", borderwidth=1, relief="solid")
        self._field_component_text.pack(fill="both", expand=True, padx=6, pady=6)
        notes = ttk.LabelFrame(win, text="Field Detail")
        notes.pack(fill="x", padx=10, pady=(0, 8))
        self._field_notes_text = tk.Text(notes, height=7, wrap="word", borderwidth=1, relief="solid")
        self._field_notes_text.pack(fill="x", padx=6, pady=6)
        ttk.Label(
            win,
            text="Double-click one component row to open Details in main panel.",
            foreground="#666",
        ).pack(anchor="w", padx=10, pady=(0, 10))
        win.protocol("WM_DELETE_WINDOW", self._close_field_window)

    def _make_role_tree(self, panel: ttk.Frame, title: str, col: int) -> ttk.Treeview:
        box = ttk.LabelFrame(panel, text=title)
        box.grid(row=0, column=col, sticky="nsew", padx=(0, 6) if col == 0 else (6, 0))
        tree = ttk.Treeview(box, columns=("component", "relation"), show="headings", height=14)
        tree.heading("component", text="component")
        tree.heading("relation", text="relation")
        tree.column("component", width=220, anchor="w")
        tree.column("relation", width=100, anchor="center")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        tree.bind("<<TreeviewSelect>>", lambda _e, t=tree: self._on_field_component_select(t))
        tree.bind("<Double-1>", lambda _e: self._open_selected_component_detail())
        return tree

    def _close_field_window(self) -> None:
        if self._field_window is not None:
            self._field_window.destroy()
        self._field_window = None
        self._field_summary_var = None
        self._field_providers_tree = None
        self._field_consumers_tree = None
        self._field_component_text = None
        self._field_notes_text = None
        self._field_selected_component = ""

    def _refresh_field_window(self) -> None:
        if self._field_window is None or not self._field_window.winfo_exists():
            return
        key = self._selected_key
        if self._field_summary_var is not None:
            self._field_summary_var.set(f"key={key}")
        providers = self._field_relation_rows(key, "providers")
        consumers = self._field_relation_rows(key, "consumers")
        self._populate_role_tree(self._field_providers_tree, providers)
        self._populate_role_tree(self._field_consumers_tree, consumers)
        self._set_text(self._field_component_text, "Select one component from Providers/Consumers.")
        self._set_text(self._field_notes_text, f"declared_by: {self._fmt_list(self._declared_writers.get(key, []))}\nlast_writer: {self._runtime_writers.get(key, '(none)')}")
        self._field_selected_component = ""

    def _focus_field_window_section(self, focus: str) -> None:
        target = str(focus).lower().strip()
        tree = self._field_providers_tree if target == "providers" else self._field_consumers_tree if target in {"consumers", "requires"} else None
        if tree is not None:
            tree.focus_set()
            rows = tree.get_children()
            if rows:
                tree.selection_set(rows[0])

    def _field_relation_rows(self, key: str, role: str) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = []
        role = role.lower().strip()
        if role == "providers":
            for comp, c in self._component_contracts.items():
                if key in c.get("provides", []):
                    rows.append((comp, "provides"))
                if key in c.get("mutates", []):
                    rows.append((comp, "mutates"))
            for comp in self._declared_writers.get(key, []):
                if not any(comp == x[0] for x in rows):
                    rows.append((comp, "declared"))
        else:
            for comp, c in self._component_contracts.items():
                if key in c.get("requires", []):
                    rows.append((comp, "requires"))
            for comp in self._declared_readers.get(key, []):
                if comp.endswith(".*") and any((not row_comp.endswith(".*")) for row_comp, _ in rows):
                    continue
                if not any(comp == x[0] for x in rows):
                    rows.append((comp, "declared"))
        return rows

    def _populate_role_tree(self, tree: Optional[ttk.Treeview], rows: List[Tuple[str, str]]) -> None:
        if tree is None:
            return
        for child in tree.get_children():
            tree.delete(child)
        for comp, rel in rows:
            tree.insert("", "end", values=(comp, rel))

    def _on_field_component_select(self, tree: ttk.Treeview) -> None:
        try:
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0]).get("values") or []
            if not vals:
                return
            component = str(vals[0]).strip()
            relation = str(vals[1]).strip() if len(vals) > 1 else ""
            self._field_selected_component = component
            contract = self._component_contracts.get(component, {})
            intro = self._catalog_intro_for_component(component)
            if not contract:
                body = f"component: {component}\nrelation: {relation}\n\nNo explicit contract."
                if intro:
                    body = f"{body}\n\nCatalog Intro\n{intro}"
                self._set_text(self._field_component_text, body)
                return
            text = (
                f"component: {component}\nrelation: {relation}\n\n"
                f"context_requires: {', '.join(contract.get('requires', [])) or '(none)'}\n"
                f"context_provides: {', '.join(contract.get('provides', [])) or '(none)'}\n"
                f"context_mutates: {', '.join(contract.get('mutates', [])) or '(none)'}\n"
                f"context_cache: {', '.join(contract.get('cache', [])) or '(none)'}\n"
                f"context_notes: {' | '.join(contract.get('notes', [])) or '(none)'}"
            )
            if intro:
                text = f"{text}\n\nCatalog Intro\n{intro}"
            self._set_text(self._field_component_text, text)
        except Exception as exc:
            self._set_error(f"Component contract display failed: {exc}")

    def _catalog_intro_for_component(self, component: str) -> str:
        catalog = getattr(self.app, "catalog", {}) or {}
        if not catalog:
            return ""

        target = str(component or "").strip()
        if not target:
            return ""
        size = len(catalog)
        if size != self._catalog_intro_cache_size:
            self._catalog_intro_cache = {}
            self._catalog_intro_cache_size = size
        cache_key = target.lower()
        if cache_key in self._catalog_intro_cache:
            return self._catalog_intro_cache[cache_key]

        best_key = ""
        best_score = 0
        target_lower = target.lower()
        target_tokens = [t for t in re.split(r"[\s\.:#>/_,-]+", target_lower) if len(t) >= 2]
        for key, info in catalog.items():
            key_s = str(key).strip().lower()
            title_s = str(info.get("title", "")).strip().lower()
            kind_s = str(info.get("kind", "")).strip().lower()
            hay = " ".join([key_s, title_s, kind_s])

            score = 0
            if key_s in target_lower or target_lower in key_s:
                score += 10
            if title_s and (title_s in target_lower or target_lower in title_s):
                score += 8
            for tok in target_tokens:
                if tok in hay:
                    score += 2
            if score > best_score:
                best_score = score
                best_key = str(key)

        if best_score <= 0 or not best_key:
            self._catalog_intro_cache[cache_key] = ""
            return ""

        info = catalog.get(best_key, {})
        lines = [
            f"key: {best_key}",
            f"title: {str(info.get('title', '') or '(none)')}",
            f"kind: {str(info.get('kind', '') or '(none)')} | scope: {str(info.get('scope', '(unknown)'))}",
            "",
            str(info.get("summary", "") or "(no summary)"),
        ]
        use_when = [str(v).strip() for v in (info.get("use_when") or []) if str(v).strip()]
        minimal = [str(v).strip() for v in (info.get("minimal_wiring") or []) if str(v).strip()]
        if use_when:
            lines.append("")
            lines.append("use_when:")
            lines.extend(f"- {v}" for v in use_when[:3])
        if minimal:
            lines.append("")
            lines.append("minimal_wiring:")
            lines.extend(f"- {v}" for v in minimal[:3])
        intro = "\n".join(lines)
        self._catalog_intro_cache[cache_key] = intro
        return intro

    def _open_selected_component_detail(self) -> None:
        if not self._field_selected_component or not hasattr(self.app, "show_component_detail"):
            return
        try:
            self.app.show_component_detail(self._field_selected_component)
        except Exception as exc:
            self._set_error(f"Open component details failed: {exc}")

    def _collect_declared_io(self, solver: Any) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, Dict[str, List[str]]]]:
        cached_solver = self._declared_cache_solver_ref() if self._declared_cache_solver_ref is not None else None
        if cached_solver is solver:
            return self._clone_declared_cache()
        name_map = self._build_component_name_map(solver)
        contracts = self._collect_component_contracts(solver, name_map)
        writers: Dict[str, List[str]] = {}
        readers: Dict[str, List[str]] = {}
        for comp, c in contracts.items():
            for key in c["provides"] + c["mutates"]:
                writers.setdefault(key, [])
                if comp not in writers[key]:
                    writers[key].append(comp)
            for key in c["requires"]:
                readers.setdefault(key, [])
                if comp not in readers[key]:
                    readers[key].append(comp)
        for key, comps in _BUILTIN_DECLARED_WRITERS.items():
            writers.setdefault(key, [])
            for comp in comps:
                if comp not in writers[key]:
                    writers[key].append(comp)
        for key, comps in _BUILTIN_DECLARED_READERS.items():
            readers.setdefault(key, [])
            for comp in comps:
                if comp not in readers[key]:
                    readers[key].append(comp)
        try:
            self._declared_cache_solver_ref = weakref.ref(solver)
        except TypeError:
            self._declared_cache_solver_ref = None
        self._declared_cache_data = (writers, readers, contracts)
        return writers, readers, contracts

    def _collect_component_contracts(self, solver: Any, name_map: Dict[str, str]) -> Dict[str, Dict[str, List[str]]]:
        out: Dict[str, Dict[str, List[str]]] = {}
        for name, contract in collect_solver_contracts(solver):
            dn = name_map.get(name, name)
            row = out.setdefault(dn, {"requires": [], "provides": [], "mutates": [], "cache": [], "notes": []})
            for field, target in (
                ("requires", contract.requires),
                ("provides", contract.provides),
                ("mutates", contract.mutates),
                ("cache", contract.cache),
                ("notes", contract.notes),
            ):
                for value in self._iter_values(target):
                    text = str(value).strip()
                    if text and text not in row[field]:
                        row[field].append(text)
        return out

    def _iter_values(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [value]

    def _collect_missing_requires(self, solver: Any, ctx: Dict[str, Any]) -> Dict[str, List[str]]:
        present = set(str(k) for k in ctx.keys())
        name_map = self._build_component_name_map(solver)
        out: Dict[str, List[str]] = {}
        for name, contract in collect_solver_contracts(solver):
            dn = name_map.get(name, name)
            miss = sorted({str(k).strip() for k in contract.requires if str(k).strip() and str(k).strip() not in present})
            if miss:
                out[dn] = miss
        return out

    def _build_component_name_map(self, solver: Any) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        pipeline = getattr(solver, "representation_pipeline", None)
        if pipeline is not None:
            mapping["representation_pipeline"] = f"representation_pipeline.{pipeline.__class__.__name__}"
        bias_module = getattr(solver, "bias_module", None)
        if bias_module is not None:
            mapping["bias_module"] = f"bias_module.{bias_module.__class__.__name__}"
        adapter = getattr(solver, "adapter", None)
        if adapter is not None:
            mapping["adapter"] = f"adapter.{adapter.__class__.__name__}"
            for idx, spec in enumerate(getattr(adapter, "strategies", ()) or ()):
                name = str(getattr(spec, "name", f"strategy_{idx}"))
                sub = getattr(spec, "adapter", None)
                mapping[f"adapter.strategy.{name}"] = f"adapter.strategy.{name}:{sub.__class__.__name__ if sub is not None else '(none)'}"
            for unit in getattr(adapter, "units", ()) or ():
                rn = str(getattr(unit, "role", "role"))
                uid = int(getattr(unit, "unit_id", 0))
                sub = getattr(unit, "adapter", None)
                mapping[f"adapter.unit.{rn}#{uid}"] = f"adapter.unit.{rn}#{uid}:{sub.__class__.__name__ if sub is not None else '(none)'}"
        pm = getattr(solver, "plugin_manager", None)
        if pm is not None and hasattr(pm, "list_plugins"):
            try:
                plugins = pm.list_plugins(enabled_only=False)
            except Exception:
                plugins = []
            for p in plugins:
                pn = str(getattr(p, "name", p.__class__.__name__))
                mapping[f"plugin.{pn}"] = f"plugin.{pn}:{p.__class__.__name__}"
        return mapping

    def _collect_runtime_writers(self, solver: Any, ctx: Dict[str, Any]) -> Dict[str, str]:
        events: List[Dict[str, Any]] = []
        raw_ctx_events = ctx.get("context_events", [])
        if isinstance(raw_ctx_events, list):
            events.extend(x for x in raw_ctx_events if isinstance(x, dict))
        if hasattr(solver, "get_plugin"):
            try:
                hub = solver.get_plugin("async_event_hub")
            except Exception:
                hub = None
            if hub is not None:
                for name in ("committed_events", "pending_events"):
                    seq = getattr(hub, name, None)
                    if isinstance(seq, list):
                        events.extend(x for x in seq if isinstance(x, dict))
        out: Dict[str, str] = {}
        for event in events:
            source = str(event.get("source") or event.get("strategy") or event.get("kind") or "unknown")
            kind = str(event.get("kind", "")).strip().lower()
            key = event.get("key")
            value = event.get("value")
            keys: List[str] = []
            if isinstance(key, str) and key.strip():
                keys.append(key.strip())
            elif kind == "update" and isinstance(value, dict):
                keys.extend(str(k).strip() for k in value.keys() if str(k).strip())
            for k in keys:
                out[k] = source
        for key, source in getattr(solver, "_runtime_projection_writers", {}).items() if isinstance(getattr(solver, "_runtime_projection_writers", None), dict) else []:
            out.setdefault(str(key).strip(), str(source).strip())
        for key, source in getattr(solver, "_context_build_writers", {}).items() if isinstance(getattr(solver, "_context_build_writers", None), dict) else []:
            out.setdefault(str(key).strip(), str(source).strip())
        for key in ctx.keys():
            if key not in out and key in _BUILTIN_DECLARED_WRITERS:
                out[key] = f"{_BUILTIN_DECLARED_WRITERS[key][0]} (builtin)"
        return out

    def _clone_declared_cache(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, Dict[str, List[str]]]]:
        writers, readers, contracts = self._declared_cache_data
        return (
            {k: list(v) for k, v in writers.items()},
            {k: list(v) for k, v in readers.items()},
            {k: {field: list(items) for field, items in row.items()} for k, row in contracts.items()},
        )

    def _on_scheduled_refresh(self) -> None:
        self._refresh_pending_id = None
        self.refresh(force=True)

    def _cancel_scheduled_refresh(self) -> None:
        if self._refresh_pending_id is not None:
            try:
                self.tab.after_cancel(self._refresh_pending_id)
            except Exception:
                pass
            self._refresh_pending_id = None

    def _clear_table(self) -> None:
        for child in self.tree.get_children():
            self.tree.delete(child)
        self.replayable_var.set("Replayable: unknown")
        self.counts_var.set("Field counts: -")
        self.alignment_var.set("Contract alignment: unknown")
        self._set_selected_key("")

    def _set_error(self, message: str) -> None:
        text = str(message or "").strip()
        self.error_var.set(f"Error: {text}" if text else "")
        if text and hasattr(self.app, "_set_status"):
            try:
                self.app._set_status(f"Context: {text}")
            except Exception:
                pass

    def _set_text(self, widget: Optional[tk.Text], text: str) -> None:
        if widget is None:
            return
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _fmt_list(self, items: List[str]) -> str:
        if not items:
            return "(none)"
        if len(items) <= 2:
            return ", ".join(items)
        return f"{items[0]}, {items[1]}, +{len(items) - 2}"
