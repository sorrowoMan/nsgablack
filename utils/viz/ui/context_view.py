from __future__ import annotations

from typing import Any, Dict, List, Tuple

import tkinter as tk
from tkinter import ttk

from ...context.context_contracts import collect_solver_contracts
from ...context.context_schema import (
    get_context_lifecycle,
    is_replayable_context,
    strip_context_for_replay,
)

# Built-in attribution rules for solver core fields.
# These are fallback heuristics when explicit contracts/events are missing.
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
    "population": ["solver.core"],
    "objectives": ["solver.core"],
    "constraint_violations": ["solver.core"],
    "evaluation_count": ["solver.core"],
    "pareto_solutions": ["plugin.pareto_archive"],
    "pareto_objectives": ["plugin.pareto_archive"],
    "context_events": ["plugin.async_event_hub"],
}

_BUILTIN_DECLARED_READERS: Dict[str, List[str]] = {
    "generation": ["adapter.*", "plugin.*", "bias_module"],
    "step": ["adapter.*", "plugin.*"],
    "dynamic": ["adapter.*", "plugin.dynamic_switch"],
    "population": ["adapter.*", "plugin.*", "bias_module"],
    "objectives": ["adapter.*", "plugin.*", "bias_module"],
    "constraint_violations": ["adapter.*", "plugin.*", "bias_module"],
    "constraints": ["adapter.*", "bias_module"],
    "constraint_violation": ["adapter.*", "bias_module"],
    "evaluation_count": ["plugin.profiler", "plugin.benchmark_harness", "plugin.module_report"],
}


class ContextView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Context", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(self.tab, text="上下文字段生命周期与可重放性", foreground="#666").pack(anchor="w", pady=(2, 8))

        info_row = ttk.Frame(self.tab)
        info_row.pack(fill="x")
        self.replayable_var = tk.StringVar(value="可重放: 未知")
        self.counts_var = tk.StringVar(value="字段统计: -")
        ttk.Label(info_row, textvariable=self.replayable_var).pack(anchor="w")
        ttk.Label(info_row, textvariable=self.counts_var).pack(anchor="w")

        btn_row = ttk.Frame(self.tab)
        btn_row.pack(fill="x", pady=(6, 6))
        ttk.Button(btn_row, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(btn_row, text="Show Replay Keys", command=self.show_replay_keys).pack(side="left", padx=(6, 0))
        self.only_replayable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            btn_row,
            text="Only replayable",
            variable=self.only_replayable_var,
            command=self.refresh,
        ).pack(side="left", padx=(10, 0))

        table = ttk.Frame(self.tab)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table,
            columns=("key", "category", "replayable", "declared_by", "last_writer"),
            show="headings",
            height=12,
        )
        self.tree.heading("key", text="key")
        self.tree.heading("category", text="lifecycle")
        self.tree.heading("replayable", text="replayable")
        self.tree.heading("declared_by", text="declared_by")
        self.tree.heading("last_writer", text="last_writer")
        self.tree.column("key", width=150, stretch=False)
        self.tree.column("category", width=80, anchor="center", stretch=False)
        self.tree.column("replayable", width=80, anchor="center", stretch=False)
        self.tree.column("declared_by", width=170, stretch=False)
        self.tree.column("last_writer", width=130, stretch=False)
        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(self.tab, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(fill="x", pady=(2, 0))
        self.tree.tag_configure("cache", background="#fff5cc")
        self.tree.tag_configure("multi_writer", background="#ffe7e7")

        self._detail = tk.Text(self.tab, height=6, wrap="word", borderwidth=1, relief="solid")
        self._detail.pack(fill="x", pady=(6, 0))
        self._detail.insert("1.0", "选择字段可查看说明与建议。")
        self._detail.config(state="disabled")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self._declared_writers: Dict[str, List[str]] = {}
        self._declared_readers: Dict[str, List[str]] = {}
        self._runtime_writers: Dict[str, str] = {}

    def _build_rows(
        self,
        ctx: Dict[str, Any],
        declared_writers: Dict[str, List[str]],
        runtime_writers: Dict[str, str],
    ) -> List[Tuple[str, str, str, str, str]]:
        lifecycle = get_context_lifecycle(ctx)
        rows: List[Tuple[str, str, str, str, str]] = []
        for key in sorted(ctx.keys(), key=str):
            category = lifecycle.get(key, "custom")
            replayable = "yes"
            if category == "cache":
                replayable = "no"
            k = str(key)
            declared = self._fmt_component_list(declared_writers.get(k, []))
            last_writer = runtime_writers.get(k, "(none)")
            rows.append((k, category, replayable, declared, last_writer))
        return rows

    def refresh(self) -> None:
        solver = getattr(self.app, "solver", None)
        if solver is None or not hasattr(solver, "get_context"):
            return
        try:
            ctx = solver.get_context()
        except Exception:
            return

        for child in self.tree.get_children():
            self.tree.delete(child)
        declared_writers, declared_readers = self._collect_declared_io(solver)
        runtime_writers = self._collect_runtime_writers(solver, ctx)
        self._declared_writers = declared_writers
        self._declared_readers = declared_readers
        self._runtime_writers = runtime_writers

        rows = self._build_rows(ctx, declared_writers, runtime_writers)
        only_replayable = bool(self.only_replayable_var.get())
        for row in rows:
            key, category, replayable, _declared, _last_writer = row
            if only_replayable and replayable != "yes":
                continue
            tags = []
            if category == "cache":
                tags.append("cache")
            if len(declared_writers.get(key, [])) > 1:
                tags.append("multi_writer")
            self.tree.insert("", "end", values=row, tags=tags)

        replayable = is_replayable_context(ctx)
        self.replayable_var.set(f"可重放: {'是' if replayable else '否'}")
        counts = self._count_by_category(ctx)
        counts_str = " / ".join(f"{k}:{v}" for k, v in counts.items())
        self.counts_var.set(f"字段统计: {counts_str}")

    def show_replay_keys(self) -> None:
        solver = getattr(self.app, "solver", None)
        if solver is None or not hasattr(solver, "get_context"):
            return
        try:
            ctx = solver.get_context()
        except Exception:
            return
        replay_ctx = strip_context_for_replay(ctx)
        keys = ", ".join(sorted(replay_ctx.keys(), key=str))
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", f"可重放字段:\n{keys}")
        self._detail.config(state="disabled")

    def _count_by_category(self, ctx: Dict[str, Any]) -> Dict[str, int]:
        lifecycle = get_context_lifecycle(ctx)
        counts: Dict[str, int] = {}
        for key in ctx.keys():
            cat = lifecycle.get(key, "custom")
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _on_select(self, _event: Any) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0]).get("values") or []
        if not values:
            return
        key, category, replayable, declared_by, last_writer = values
        readers = self._declared_readers.get(str(key), [])
        readers_text = self._fmt_component_list(readers)
        writer_list = self._declared_writers.get(str(key), [])
        note = (
            f"key: {key}\n"
            f"lifecycle: {category}\n"
            f"replayable: {replayable}\n"
            f"declared_by: {declared_by}\n"
            f"read_by: {readers_text}\n"
            f"last_writer: {last_writer}\n"
        )
        if len(writer_list) > 1:
            note += "\n提示：该字段有多个声明写入者，建议检查职责边界和写入顺序。"
        if category == "cache":
            note += "\n提示：cache 字段是性能缓存，不保证可重放。"
        elif category == "runtime":
            note += "\n提示：runtime 字段反映运行期状态，可能随步数变化。"
        elif category == "input":
            note += "\n提示：input 字段来自问题/实验输入，通常稳定可复用。"
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", note)
        self._detail.config(state="disabled")

    def _collect_declared_io(self, solver: Any) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        writers: Dict[str, List[str]] = {}
        readers: Dict[str, List[str]] = {}
        for name, contract in collect_solver_contracts(solver):
            for key in list(contract.provides) + list(contract.mutates):
                k = str(key).strip()
                if not k:
                    continue
                writers.setdefault(k, [])
                if name not in writers[k]:
                    writers[k].append(name)
            for key in contract.requires:
                k = str(key).strip()
                if not k:
                    continue
                readers.setdefault(k, [])
                if name not in readers[k]:
                    readers[k].append(name)

        for key, components in _BUILTIN_DECLARED_WRITERS.items():
            writers.setdefault(key, [])
            for comp in components:
                if comp not in writers[key]:
                    writers[key].append(comp)
        for key, components in _BUILTIN_DECLARED_READERS.items():
            readers.setdefault(key, [])
            for comp in components:
                if comp not in readers[key]:
                    readers[key].append(comp)
        return writers, readers

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

        raw_solver_events = getattr(solver, "event_history", None)
        if isinstance(raw_solver_events, list):
            events.extend(x for x in raw_solver_events if isinstance(x, dict))

        last_writers: Dict[str, str] = {}
        for event in events:
            source = str(event.get("source") or event.get("strategy") or event.get("kind") or "unknown")
            kind = str(event.get("kind", "")).strip().lower()
            key = event.get("key")
            value = event.get("value")

            affected: List[str] = []
            if isinstance(key, str) and key.strip():
                affected.append(key.strip())
            elif kind == "update" and isinstance(value, dict):
                for k in value.keys():
                    ks = str(k).strip()
                    if ks:
                        affected.append(ks)

            for k in affected:
                last_writers[k] = source

        # Built-in fallback attribution for core fields when no runtime event exists.
        for key in ctx.keys():
            k = str(key)
            if k in last_writers:
                continue
            fallback = _BUILTIN_DECLARED_WRITERS.get(k)
            if fallback:
                last_writers[k] = f"{fallback[0]} (builtin)"
        return last_writers

    def _fmt_component_list(self, items: List[str]) -> str:
        if not items:
            return "(none)"
        if len(items) <= 2:
            return ", ".join(items)
        return f"{items[0]}, {items[1]}, +{len(items) - 2}"
