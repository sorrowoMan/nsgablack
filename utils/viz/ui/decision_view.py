from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk

from ...runtime.decision_trace import DecisionReplayEngine


class DecisionView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._events: List[Dict[str, Any]] = []
        self._row_event_map: Dict[str, Dict[str, Any]] = {}
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Decision Replay", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            self.tab,
            text="Replay deterministic decision path (why/when).",
            foreground="#666",
        ).pack(anchor="w", pady=(2, 8))

        top = ttk.Frame(self.tab)
        top.pack(fill="x")
        self.path_var = tk.StringVar(value="trace: (none)")
        ttk.Label(top, textvariable=self.path_var, foreground="#666").pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="Load Last", command=self.load_last_run).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))

        flt = ttk.Frame(self.tab)
        flt.pack(fill="x", pady=(8, 6))
        self.type_var = tk.StringVar(value="all")
        self.comp_var = tk.StringVar(value="all")
        self.gen_var = tk.StringVar(value="")
        ttk.Label(flt, text="Type").pack(side="left")
        self.type_combo = ttk.Combobox(flt, textvariable=self.type_var, values=("all",), width=18, state="readonly")
        self.type_combo.pack(side="left", padx=(4, 8))
        self.type_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())
        ttk.Label(flt, text="Component").pack(side="left")
        self.comp_combo = ttk.Combobox(flt, textvariable=self.comp_var, values=("all",), width=24, state="readonly")
        self.comp_combo.pack(side="left", padx=(4, 8))
        self.comp_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())
        ttk.Label(flt, text="Gen").pack(side="left")
        gen_entry = ttk.Entry(flt, textvariable=self.gen_var, width=8)
        gen_entry.pack(side="left", padx=(4, 0))
        gen_entry.bind("<Return>", lambda _e: self._apply_filter())
        ttk.Button(flt, text="Apply", command=self._apply_filter).pack(side="left", padx=(6, 0))
        self.group_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            flt,
            text="Group by generation/step",
            variable=self.group_var,
            command=self._apply_filter,
        ).pack(side="left", padx=(10, 0))

        table_wrap = ttk.Frame(self.tab)
        table_wrap.pack(fill="both", expand=True)
        cols = ("seq", "generation", "event_type", "component", "decision", "reason_code")
        self.table = ttk.Treeview(table_wrap, columns=cols, show="tree headings", height=10)
        self.table.heading("#0", text="timeline")
        self.table.column("#0", width=240, anchor="w")
        for c, w in (("seq", 70), ("generation", 80), ("event_type", 140), ("component", 180), ("decision", 140), ("reason_code", 180)):
            self.table.heading(c, text=c)
            self.table.column(c, width=w, anchor="w")
        ybar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=ybar.set)
        self.table.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")
        self.table.bind("<<TreeviewSelect>>", self._on_select_row)

        self.summary_var = tk.StringVar(value="events: 0")
        ttk.Label(self.tab, textvariable=self.summary_var, foreground="#666").pack(anchor="w", pady=(6, 4))

        self.detail = tk.Text(self.tab, height=10, wrap="word", borderwidth=1, relief="solid")
        self.detail.pack(fill="x")
        self.detail.insert("1.0", "Select one event to view full detail.")
        self.detail.config(state="disabled")

    def load_last_run(self) -> None:
        run_id = getattr(self.app, "_last_run_id", None)
        artifacts = getattr(self.app, "_last_artifacts", {}) or {}
        if not run_id:
            self.path_var.set("trace: (no run yet)")
            return
        self.load_from_run(run_id=str(run_id), artifacts=artifacts)

    def load_from_history_index(self, idx: int) -> None:
        meta_list = getattr(self.app, "_history_meta", None) or []
        if idx < 0 or idx >= len(meta_list):
            return
        meta = meta_list[idx] if isinstance(meta_list[idx], dict) else {}
        run_id = str(meta.get("run_id", "") or "")
        artifacts = meta.get("artifacts", {}) if isinstance(meta.get("artifacts"), dict) else {}
        if run_id:
            self.load_from_run(run_id=run_id, artifacts=artifacts)

    def _trace_path_for_run(self, run_id: str, artifacts: Dict[str, Any]) -> Path:
        p = artifacts.get("decision_trace_jsonl") if isinstance(artifacts, dict) else None
        if p:
            return Path(str(p)).expanduser().resolve()
        return (Path("runs") / f"{run_id}.decision_trace.jsonl").resolve()

    def load_from_run(self, *, run_id: str, artifacts: Dict[str, Any]) -> None:
        path = self._trace_path_for_run(run_id, artifacts)
        self.path_var.set(f"trace: {path}")
        if not path.is_file():
            self._events = []
            self._render([])
            self.summary_var.set(f"events: 0 (trace not found for run_id={run_id})")
            return
        engine = DecisionReplayEngine.from_jsonl(path)
        self._events = list(engine.events)
        self._rebuild_filters()
        self._apply_filter()

    def refresh(self) -> None:
        run_id = getattr(self.app, "_last_run_id", None)
        if not run_id:
            return
        self.load_from_run(run_id=str(run_id), artifacts=getattr(self.app, "_last_artifacts", {}) or {})

    def _rebuild_filters(self) -> None:
        types = sorted({str(e.get("event_type", "")) for e in self._events if str(e.get("event_type", "")).strip()})
        comps = sorted({str(e.get("component", "")) for e in self._events if str(e.get("component", "")).strip()})
        self.type_combo["values"] = tuple(["all"] + types)
        self.comp_combo["values"] = tuple(["all"] + comps)
        if self.type_var.get() not in self.type_combo["values"]:
            self.type_var.set("all")
        if self.comp_var.get() not in self.comp_combo["values"]:
            self.comp_var.set("all")

    def _apply_filter(self) -> None:
        et = str(self.type_var.get() or "all")
        comp = str(self.comp_var.get() or "all")
        gen_text = str(self.gen_var.get() or "").strip()
        gen = None
        if gen_text:
            try:
                gen = int(gen_text)
            except Exception:
                gen = None
        rows: List[Dict[str, Any]] = []
        for e in self._events:
            if et != "all" and str(e.get("event_type", "")) != et:
                continue
            if comp != "all" and str(e.get("component", "")) != comp:
                continue
            if gen is not None and int(e.get("generation") or -1) != gen:
                continue
            rows.append(e)
        self._render(rows)

    def _render(self, rows: List[Dict[str, Any]]) -> None:
        self._row_event_map = {}
        nodes: Dict[str, Dict[str, Any]] = {}
        order: List[tuple[str, str]] = []

        def _upsert_node(iid: str, parent: str, text: str, values: tuple[Any, ...], *, event: Optional[Dict[str, Any]] = None) -> None:
            nodes[iid] = {"parent": parent, "text": text, "values": values}
            order.append((parent, iid))
            if isinstance(event, dict):
                self._row_event_map[iid] = event

        if bool(self.group_var.get()):
            groups: Dict[int, Dict[int, List[Dict[str, Any]]]] = {}
            for e in rows:
                g = int(e.get("generation") or -1)
                s = int(e.get("step") or -1)
                groups.setdefault(g, {}).setdefault(s, []).append(e)
            for g in sorted(groups.keys()):
                g_events = sum(len(v) for v in groups[g].values())
                gid = f"g_{g}"
                _upsert_node(gid, "", f"generation={g}  events={g_events}", ("", "", "", "", "", ""))
                for s in sorted(groups[g].keys()):
                    sid = f"{gid}_s_{s}"
                    _upsert_node(sid, gid, f"step={s}  events={len(groups[g][s])}", ("", "", "", "", "", ""))
                    for idx, e in enumerate(sorted(groups[g][s], key=lambda x: int(x.get('seq', 0)))):
                        seq = int(e.get("seq", idx) or idx)
                        row_id = f"e_{seq}"
                        vals = (
                            e.get("seq"),
                            e.get("generation"),
                            e.get("event_type"),
                            e.get("component"),
                            e.get("decision"),
                            e.get("reason_code"),
                        )
                        _upsert_node(row_id, sid, str(e.get("event_type", "")), vals, event=e)
        else:
            for idx, e in enumerate(rows):
                seq = int(e.get("seq", idx) or idx)
                row_id = f"e_{seq}"
                vals = (
                    e.get("seq"),
                    e.get("generation"),
                    e.get("event_type"),
                    e.get("component"),
                    e.get("decision"),
                    e.get("reason_code"),
                )
                _upsert_node(row_id, "", str(e.get("event_type", "")), vals, event=e)
        self._reconcile_tree(nodes, order)
        self.summary_var.set(f"events: {len(rows)} / total: {len(self._events)}")
        self._set_detail("Select one event to view full detail.")

    def _iter_tree_nodes(self, parent: str = "") -> List[str]:
        out: List[str] = []
        for iid in self.table.get_children(parent):
            out.append(str(iid))
            out.extend(self._iter_tree_nodes(str(iid)))
        return out

    def _reconcile_tree(self, nodes: Dict[str, Dict[str, Any]], order: List[tuple[str, str]]) -> None:
        existing = set(self._iter_tree_nodes(""))
        expected = set(nodes.keys())
        for iid in sorted(existing - expected):
            self.table.delete(iid)
        for parent, iid in order:
            spec = nodes[iid]
            text = spec["text"]
            values = spec["values"]
            if self.table.exists(iid):
                self.table.move(iid, parent, "end")
                cur_text = str(self.table.item(iid, "text"))
                cur_vals = tuple(self.table.item(iid).get("values") or ())
                if cur_text != text or cur_vals != values:
                    self.table.item(iid, text=text, values=values)
            else:
                self.table.insert(parent, "end", iid=iid, text=text, values=values, open=False)

    def _on_select_row(self, _event: Any) -> None:
        sel = self.table.selection()
        if not sel:
            return
        iid = sel[0]
        event = self._row_event_map.get(str(iid))
        if not isinstance(event, dict):
            # group row selected
            self._set_detail("Select one concrete event row to view full detail.")
            return
        self._set_detail(json.dumps(event, ensure_ascii=False, indent=2))

    def _set_detail(self, text: str) -> None:
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")
