from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk


class SequenceView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._payload: Dict[str, Any] = {}
        self._records: List[Dict[str, Any]] = []
        self._trace_events: List[Dict[str, Any]] = []
        self._row_map: Dict[str, Dict[str, Any]] = {}
        self._trie_row_map: Dict[str, Dict[str, Any]] = {}
        self._trace_row_map: Dict[str, Dict[str, Any]] = {}
        self._trace_group_map: Dict[str, Dict[str, Any]] = {}
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Sequence Graph", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            self.tab,
            text="Unique interaction order graph (values ignored).",
            foreground="#666",
        ).pack(anchor="w", pady=(2, 8))

        top = ttk.Frame(self.tab)
        top.pack(fill="x")
        self.path_var = tk.StringVar(value="sequence: (none)")
        ttk.Label(top, textvariable=self.path_var, foreground="#666").pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="Load Last", command=self.load_last_run).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))

        notebook = ttk.Notebook(self.tab)
        notebook.pack(fill="both", expand=True)
        list_tab = ttk.Frame(notebook)
        trie_tab = ttk.Frame(notebook)
        trace_tab = ttk.Frame(notebook)
        notebook.add(list_tab, text="List")
        notebook.add(trie_tab, text="Trie")
        notebook.add(trace_tab, text="Trace")

        flt = ttk.Frame(self.tab)
        flt.pack(fill="x", pady=(8, 6))
        ttk.Label(flt, text="Contains").pack(side="left")
        self.search_var = tk.StringVar(value="")
        search_entry = ttk.Entry(flt, textvariable=self.search_var, width=24)
        search_entry.pack(side="left", padx=(4, 8))
        search_entry.bind("<Return>", lambda _e: self._apply_filter())
        ttk.Label(flt, text="Min Count").pack(side="left")
        self.min_count_var = tk.StringVar(value="1")
        min_entry = ttk.Entry(flt, textvariable=self.min_count_var, width=6)
        min_entry.pack(side="left", padx=(4, 6))
        min_entry.bind("<Return>", lambda _e: self._apply_filter())
        ttk.Button(flt, text="Apply", command=self._apply_filter).pack(side="left")

        table_wrap = ttk.Frame(list_tab)
        table_wrap.pack(fill="both", expand=True)
        cols = ("signature", "count", "length", "first_gen", "last_gen", "truncated")
        self.table = ttk.Treeview(table_wrap, columns=cols, show="headings", height=10)
        for c, w in (
            ("signature", 160),
            ("count", 80),
            ("length", 80),
            ("first_gen", 90),
            ("last_gen", 90),
            ("truncated", 80),
        ):
            self.table.heading(c, text=c)
            self.table.column(c, width=w, anchor="w")
        ybar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=ybar.set)
        self.table.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")
        self.table.bind("<<TreeviewSelect>>", self._on_select_row)

        self.summary_var = tk.StringVar(value="sequences: 0")
        ttk.Label(list_tab, textvariable=self.summary_var, foreground="#666").pack(anchor="w", pady=(6, 4))

        self.detail = tk.Text(list_tab, height=10, wrap="word", borderwidth=1, relief="solid")
        self.detail.pack(fill="x")
        self.detail.insert("1.0", "Select one sequence to view detail.")
        self.detail.config(state="disabled")

        trie_wrap = ttk.Frame(trie_tab)
        trie_wrap.pack(fill="both", expand=True)
        trie_cols = ("count", "leafs")
        self.trie_tree = ttk.Treeview(trie_wrap, columns=trie_cols, show="tree headings", height=12)
        self.trie_tree.heading("#0", text="event")
        self.trie_tree.column("#0", width=300, anchor="w")
        self.trie_tree.heading("count", text="count")
        self.trie_tree.column("count", width=90, anchor="w")
        self.trie_tree.heading("leafs", text="leafs")
        self.trie_tree.column("leafs", width=90, anchor="w")
        trie_ybar = ttk.Scrollbar(trie_wrap, orient="vertical", command=self.trie_tree.yview)
        self.trie_tree.configure(yscrollcommand=trie_ybar.set)
        self.trie_tree.pack(side="left", fill="both", expand=True)
        trie_ybar.pack(side="right", fill="y")
        self.trie_tree.bind("<<TreeviewSelect>>", self._on_select_trie_node)

        self.trie_summary_var = tk.StringVar(value="nodes: 0")
        ttk.Label(trie_tab, textvariable=self.trie_summary_var, foreground="#666").pack(anchor="w", pady=(6, 4))

        self.trie_detail = tk.Text(trie_tab, height=8, wrap="word", borderwidth=1, relief="solid")
        self.trie_detail.pack(fill="x")
        self.trie_detail.insert("1.0", "Select one node to view path detail.")
        self.trie_detail.config(state="disabled")

        trace_notebook = ttk.Notebook(trace_tab)
        trace_notebook.pack(fill="both", expand=True)
        trace_events_tab = ttk.Frame(trace_notebook)
        trace_group_tab = ttk.Frame(trace_notebook)
        trace_notebook.add(trace_events_tab, text="Events")
        trace_notebook.add(trace_group_tab, text="By Thread/Task")

        trace_wrap = ttk.Frame(trace_events_tab)
        trace_wrap.pack(fill="both", expand=True)
        trace_cols = ("start_ns", "duration_us", "token", "thread_id", "task_id", "span_id", "parent", "status")
        self.trace_table = ttk.Treeview(trace_wrap, columns=trace_cols, show="headings", height=12)
        for c, w in (
            ("start_ns", 140),
            ("duration_us", 95),
            ("token", 260),
            ("thread_id", 90),
            ("task_id", 120),
            ("span_id", 80),
            ("parent", 90),
            ("status", 80),
        ):
            self.trace_table.heading(c, text=c)
            self.trace_table.column(c, width=w, anchor="w")
        trace_ybar = ttk.Scrollbar(trace_wrap, orient="vertical", command=self.trace_table.yview)
        self.trace_table.configure(yscrollcommand=trace_ybar.set)
        self.trace_table.pack(side="left", fill="both", expand=True)
        trace_ybar.pack(side="right", fill="y")
        self.trace_table.bind("<<TreeviewSelect>>", self._on_select_trace_row)

        self.trace_summary_var = tk.StringVar(value="trace: 0 events")
        ttk.Label(trace_events_tab, textvariable=self.trace_summary_var, foreground="#666").pack(anchor="w", pady=(6, 4))

        self.trace_detail = tk.Text(trace_events_tab, height=8, wrap="word", borderwidth=1, relief="solid")
        self.trace_detail.pack(fill="x")
        self.trace_detail.insert("1.0", "Select one trace event to view detail.")
        self.trace_detail.config(state="disabled")

        group_wrap = ttk.Frame(trace_group_tab)
        group_wrap.pack(fill="both", expand=True)
        group_cols = ("thread_id", "task_id", "events", "spans", "errors", "total_ms", "avg_us", "max_ms")
        self.trace_group_table = ttk.Treeview(group_wrap, columns=group_cols, show="headings", height=12)
        for c, w in (
            ("thread_id", 100),
            ("task_id", 140),
            ("events", 80),
            ("spans", 80),
            ("errors", 80),
            ("total_ms", 95),
            ("avg_us", 95),
            ("max_ms", 95),
        ):
            self.trace_group_table.heading(c, text=c)
            self.trace_group_table.column(c, width=w, anchor="w")
        trace_group_ybar = ttk.Scrollbar(group_wrap, orient="vertical", command=self.trace_group_table.yview)
        self.trace_group_table.configure(yscrollcommand=trace_group_ybar.set)
        self.trace_group_table.pack(side="left", fill="both", expand=True)
        trace_group_ybar.pack(side="right", fill="y")
        self.trace_group_table.bind("<<TreeviewSelect>>", self._on_select_trace_group)

        self.trace_group_summary_var = tk.StringVar(value="groups: 0")
        ttk.Label(trace_group_tab, textvariable=self.trace_group_summary_var, foreground="#666").pack(anchor="w", pady=(6, 4))

        self.trace_group_detail = tk.Text(trace_group_tab, height=8, wrap="word", borderwidth=1, relief="solid")
        self.trace_group_detail.pack(fill="x")
        self.trace_group_detail.insert("1.0", "Select one thread/task group to view detail.")
        self.trace_group_detail.config(state="disabled")

    def load_last_run(self) -> None:
        run_id = getattr(self.app, "_last_run_id", None)
        artifacts = getattr(self.app, "_last_artifacts", {}) or {}
        if not run_id:
            self.path_var.set("sequence: (no run yet)")
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

    def _sequence_path_for_run(self, run_id: str, artifacts: Dict[str, Any]) -> Path:
        p = artifacts.get("sequence_graph_json") if isinstance(artifacts, dict) else None
        if p:
            return Path(str(p)).expanduser().resolve()
        return (Path("runs") / f"{run_id}.sequence_graph.json").resolve()

    def load_from_run(self, *, run_id: str, artifacts: Dict[str, Any]) -> None:
        path = self._sequence_path_for_run(run_id, artifacts)
        self.path_var.set(f"sequence: {path}")
        if not path.is_file():
            self._payload = {}
            self._records = []
            self._trace_events = []
            self._render([])
            self._render_trie([])
            self._render_trace([])
            self.summary_var.set(f"sequences: 0 (file not found for run_id={run_id})")
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        self._payload = payload
        self._records = list(payload.get("sequence_records", []) or [])
        self._trace_events = list(payload.get("trace_events", []) or [])
        self._apply_filter()

    def refresh(self) -> None:
        run_id = getattr(self.app, "_last_run_id", None)
        if not run_id:
            return
        self.load_from_run(run_id=str(run_id), artifacts=getattr(self.app, "_last_artifacts", {}) or {})

    def _apply_filter(self) -> None:
        term = str(self.search_var.get() or "").strip().lower()
        min_count = 1
        try:
            min_count = int(self.min_count_var.get() or 1)
        except Exception:
            min_count = 1
        rows: List[Dict[str, Any]] = []
        for rec in self._records:
            count = int(rec.get("count", 0) or 0)
            if count < min_count:
                continue
            if term:
                hay = " ".join(str(x) for x in (rec.get("events") or []))
                if term not in hay.lower() and term not in str(rec.get("signature", "")).lower():
                    continue
            rows.append(rec)
        self._render(rows)
        self._render_trie(rows)
        trace_rows = self._filter_trace_rows(term=term)
        self._render_trace(trace_rows)

    def _filter_trace_rows(self, *, term: str) -> List[Dict[str, Any]]:
        if not term:
            return list(self._trace_events)
        out: List[Dict[str, Any]] = []
        for event in self._trace_events:
            token = str(event.get("token", "") or "").lower()
            status = str(event.get("status", "") or "").lower()
            task_id = str(event.get("task_id", "") or "").lower()
            thread_id = str(event.get("thread_id", "") or "").lower()
            if term in token or term in status or term in task_id or term in thread_id:
                out.append(event)
        return out

    def _render(self, rows: List[Dict[str, Any]]) -> None:
        self._row_map = {}
        self.table.delete(*self.table.get_children())
        for rec in rows:
            signature = str(rec.get("signature", ""))
            sig_short = signature
            if ":" in signature:
                sig_short = signature.split(":", 1)[-1]
            if len(sig_short) > 12:
                sig_short = sig_short[:12]
            values = (
                sig_short,
                rec.get("count"),
                rec.get("length"),
                rec.get("first_generation"),
                rec.get("last_generation"),
                rec.get("truncated"),
            )
            self.table.insert("", "end", iid=signature or None, values=values)
            self._row_map[signature] = rec

        cycle_count = int(self._payload.get("cycle_count", 0) or 0)
        total_events = int(self._payload.get("total_events", 0) or 0)
        self.summary_var.set(f"sequences: {len(rows)} / cycles: {cycle_count} / events: {total_events}")
        self._set_detail("Select one sequence to view detail.")

    def _build_trie(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        root = {"count": 0, "leafs": 0, "children": {}}
        for rec in rows:
            events = rec.get("events") or []
            weight = int(rec.get("count", 0) or 0)
            if not events:
                continue
            node = root
            node["count"] += weight
            for evt in events:
                child = node["children"].setdefault(str(evt), {"count": 0, "leafs": 0, "children": {}})
                child["count"] += weight
                node = child
            node["leafs"] += weight
        return root

    def _render_trie(self, rows: List[Dict[str, Any]]) -> None:
        self._trie_row_map = {}
        self.trie_tree.delete(*self.trie_tree.get_children())
        root = self._build_trie(rows)
        node_count = 0

        def _insert(parent: str, label: str, node: Dict[str, Any], path: List[str]) -> None:
            nonlocal node_count
            iid = f"n{node_count}"
            node_count += 1
            values = (node.get("count", 0), node.get("leafs", 0))
            self.trie_tree.insert(parent, "end", iid=iid, text=label, values=values)
            self._trie_row_map[iid] = {"path": list(path), "node": dict(node)}
            children = node.get("children", {})
            for key in sorted(children.keys(), key=lambda x: str(x)):
                _insert(iid, str(key), children[key], path + [str(key)])

        for key in sorted(root["children"].keys(), key=lambda x: str(x)):
            _insert("", str(key), root["children"][key], [str(key)])

        self.trie_summary_var.set(f"nodes: {node_count} / sequences: {len(rows)}")
        self._set_trie_detail("Select one node to view path detail.")

    def _render_trace(self, rows: List[Dict[str, Any]]) -> None:
        self._trace_row_map = {}
        self.trace_table.delete(*self.trace_table.get_children())
        for idx, event in enumerate(rows):
            iid = f"t{idx}"
            start_ns = int(event.get("start_ns", 0) or 0)
            duration_ns = int(event.get("duration_ns", 0) or 0)
            duration_us = duration_ns / 1000.0
            values = (
                start_ns,
                f"{duration_us:.3f}",
                event.get("token", ""),
                event.get("thread_id", ""),
                event.get("task_id", ""),
                event.get("span_id", ""),
                event.get("parent_span_id", ""),
                event.get("status", ""),
            )
            self.trace_table.insert("", "end", iid=iid, values=values)
            self._trace_row_map[iid] = event
        mode = str(self._payload.get("trace_mode", "off") or "off")
        dropped = int(self._payload.get("trace_dropped_events", 0) or 0)
        self.trace_summary_var.set(f"trace: {len(rows)} events / mode={mode} / dropped={dropped}")
        self._set_trace_detail("Select one trace event to view detail.")
        self._render_trace_groups(rows)

    def _build_trace_groups(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        for event in rows:
            thread_id = str(event.get("thread_id", "") or "")
            task_id = str(event.get("task_id", "") or "")
            group_id = f"{thread_id}|{task_id}"
            group = groups.get(group_id)
            if group is None:
                group = {
                    "thread_id": thread_id,
                    "task_id": task_id,
                    "events": 0,
                    "spans_set": set(),
                    "errors": 0,
                    "duration_ns_sum": 0,
                    "duration_ns_max": 0,
                    "start_ns_min": None,
                    "end_ns_max": None,
                    "token_counts": {},
                    "status_counts": {},
                }
                groups[group_id] = group

            duration_ns = int(event.get("duration_ns", 0) or 0)
            start_ns = int(event.get("start_ns", 0) or 0)
            end_ns = int(event.get("end_ns", start_ns) or start_ns)
            span_id = str(event.get("span_id", "") or "")
            token = str(event.get("token", "") or "")
            status = str(event.get("status", "") or "ok")

            group["events"] = int(group["events"]) + 1
            group["duration_ns_sum"] = int(group["duration_ns_sum"]) + duration_ns
            if duration_ns > int(group["duration_ns_max"]):
                group["duration_ns_max"] = duration_ns
            if span_id:
                group["spans_set"].add(span_id)
            if status.lower() == "error":
                group["errors"] = int(group["errors"]) + 1
            if group["start_ns_min"] is None or start_ns < int(group["start_ns_min"]):
                group["start_ns_min"] = start_ns
            if group["end_ns_max"] is None or end_ns > int(group["end_ns_max"]):
                group["end_ns_max"] = end_ns

            token_counts = group["token_counts"]
            status_counts = group["status_counts"]
            token_counts[token] = int(token_counts.get(token, 0)) + 1
            status_counts[status] = int(status_counts.get(status, 0)) + 1

        out: List[Dict[str, Any]] = []
        for group in groups.values():
            events = int(group["events"])
            duration_sum = int(group["duration_ns_sum"])
            duration_max = int(group["duration_ns_max"])
            avg_us = (duration_sum / 1000.0 / events) if events > 0 else 0.0
            total_ms = duration_sum / 1_000_000.0
            max_ms = duration_max / 1_000_000.0

            token_counts = group["token_counts"]
            status_counts = group["status_counts"]
            top_token = ""
            top_token_count = 0
            if token_counts:
                top_token, top_token_count = max(token_counts.items(), key=lambda kv: (int(kv[1]), str(kv[0])))
            top_status = ""
            top_status_count = 0
            if status_counts:
                top_status, top_status_count = max(status_counts.items(), key=lambda kv: (int(kv[1]), str(kv[0])))

            out.append(
                {
                    "thread_id": group["thread_id"],
                    "task_id": group["task_id"],
                    "events": events,
                    "spans": len(group["spans_set"]),
                    "errors": int(group["errors"]),
                    "duration_ns_sum": duration_sum,
                    "duration_ns_max": duration_max,
                    "total_ms": total_ms,
                    "avg_us": avg_us,
                    "max_ms": max_ms,
                    "start_ns_min": group["start_ns_min"],
                    "end_ns_max": group["end_ns_max"],
                    "top_token": top_token,
                    "top_token_count": int(top_token_count),
                    "top_status": top_status,
                    "top_status_count": int(top_status_count),
                }
            )

        out.sort(
            key=lambda g: (
                -int(g.get("events", 0)),
                -float(g.get("total_ms", 0.0)),
                str(g.get("thread_id", "")),
                str(g.get("task_id", "")),
            )
        )
        return out

    def _render_trace_groups(self, rows: List[Dict[str, Any]]) -> None:
        self._trace_group_map = {}
        self.trace_group_table.delete(*self.trace_group_table.get_children())
        groups = self._build_trace_groups(rows)
        for idx, group in enumerate(groups):
            iid = f"g{idx}"
            values = (
                group.get("thread_id", ""),
                group.get("task_id", ""),
                group.get("events", 0),
                group.get("spans", 0),
                group.get("errors", 0),
                f"{float(group.get('total_ms', 0.0)):.3f}",
                f"{float(group.get('avg_us', 0.0)):.3f}",
                f"{float(group.get('max_ms', 0.0)):.3f}",
            )
            self.trace_group_table.insert("", "end", iid=iid, values=values)
            self._trace_group_map[iid] = group
        error_groups = sum(1 for g in groups if int(g.get("errors", 0) or 0) > 0)
        self.trace_group_summary_var.set(f"groups: {len(groups)} / error_groups: {error_groups}")
        self._set_trace_group_detail("Select one thread/task group to view detail.")

    def _on_select_row(self, _event: Any) -> None:
        sel = self.table.selection()
        if not sel:
            return
        sig = str(sel[0])
        rec = self._row_map.get(sig)
        if not isinstance(rec, dict):
            self._set_detail("Select one sequence to view detail.")
            return
        self._set_detail(self._format_record(rec))

    def _on_select_trie_node(self, _event: Any) -> None:
        sel = self.trie_tree.selection()
        if not sel:
            return
        iid = str(sel[0])
        data = self._trie_row_map.get(iid)
        if not isinstance(data, dict):
            self._set_trie_detail("Select one node to view path detail.")
            return
        path = data.get("path", [])
        node = data.get("node", {})
        lines = []
        lines.append("path:")
        for idx, evt in enumerate(path, start=1):
            lines.append(f"{idx:>3}. {evt}")
        lines.append("")
        lines.append(f"count: {node.get('count', 0)}")
        lines.append(f"leafs: {node.get('leafs', 0)}")
        self._set_trie_detail("\n".join(lines))

    def _on_select_trace_row(self, _event: Any) -> None:
        sel = self.trace_table.selection()
        if not sel:
            return
        iid = str(sel[0])
        event = self._trace_row_map.get(iid)
        if not isinstance(event, dict):
            self._set_trace_detail("Select one trace event to view detail.")
            return
        self._set_trace_detail(self._format_trace_event(event))

    def _on_select_trace_group(self, _event: Any) -> None:
        sel = self.trace_group_table.selection()
        if not sel:
            return
        iid = str(sel[0])
        group = self._trace_group_map.get(iid)
        if not isinstance(group, dict):
            self._set_trace_group_detail("Select one thread/task group to view detail.")
            return
        self._set_trace_group_detail(self._format_trace_group(group))

    def _format_record(self, rec: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"signature: {rec.get('signature')}")
        lines.append(f"count: {rec.get('count')}")
        lines.append(f"length: {rec.get('length')}")
        lines.append(f"truncated: {rec.get('truncated')}")
        lines.append(f"first_generation: {rec.get('first_generation')}")
        lines.append(f"last_generation: {rec.get('last_generation')}")
        lines.append("")
        events = rec.get("events") or []
        if not events:
            lines.append("(no events)")
        else:
            lines.append("events:")
            for idx, evt in enumerate(events, start=1):
                lines.append(f"{idx:>3}. {evt}")
        return "\n".join(lines)

    def _format_trace_event(self, event: Dict[str, Any]) -> str:
        lines = []
        for key in (
            "token",
            "status",
            "error_type",
            "generation",
            "step",
            "start_ns",
            "end_ns",
            "duration_ns",
            "thread_id",
            "task_id",
            "span_id",
            "parent_span_id",
            "trace_type",
        ):
            if key in event:
                lines.append(f"{key}: {event.get(key)}")
        extras = [k for k in event.keys() if k not in {
            "token",
            "status",
            "error_type",
            "generation",
            "step",
            "start_ns",
            "end_ns",
            "duration_ns",
            "thread_id",
            "task_id",
            "span_id",
            "parent_span_id",
            "trace_type",
        }]
        if extras:
            lines.append("")
            lines.append("extra:")
            for key in sorted(extras):
                lines.append(f"{key}: {event.get(key)}")
        return "\n".join(lines)

    def _format_trace_group(self, group: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"thread_id: {group.get('thread_id')}")
        lines.append(f"task_id: {group.get('task_id')}")
        lines.append(f"events: {group.get('events')}")
        lines.append(f"spans: {group.get('spans')}")
        lines.append(f"errors: {group.get('errors')}")
        lines.append(f"total_ms: {float(group.get('total_ms', 0.0)):.6f}")
        lines.append(f"avg_us: {float(group.get('avg_us', 0.0)):.6f}")
        lines.append(f"max_ms: {float(group.get('max_ms', 0.0)):.6f}")
        lines.append(f"start_ns_min: {group.get('start_ns_min')}")
        lines.append(f"end_ns_max: {group.get('end_ns_max')}")
        lines.append(f"top_token: {group.get('top_token')} ({group.get('top_token_count')})")
        lines.append(f"top_status: {group.get('top_status')} ({group.get('top_status_count')})")
        return "\n".join(lines)

    def _set_detail(self, text: str) -> None:
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")

    def _set_trie_detail(self, text: str) -> None:
        self.trie_detail.config(state="normal")
        self.trie_detail.delete("1.0", "end")
        self.trie_detail.insert("1.0", text)
        self.trie_detail.config(state="disabled")

    def _set_trace_detail(self, text: str) -> None:
        self.trace_detail.config(state="normal")
        self.trace_detail.delete("1.0", "end")
        self.trace_detail.insert("1.0", text)
        self.trace_detail.config(state="disabled")

    def _set_trace_group_detail(self, text: str) -> None:
        self.trace_group_detail.config(state="normal")
        self.trace_group_detail.delete("1.0", "end")
        self.trace_group_detail.insert("1.0", text)
        self.trace_group_detail.config(state="disabled")
