from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import tkinter as tk
from tkinter import filedialog, ttk


@dataclass(frozen=True)
class DoctorVisualHint:
    code: str
    level: str  # error / warn / info
    count: int
    title: str
    category: str
    suggestion: str
    sample: str


_LEVEL_ORDER = {"error": 0, "warn": 1, "info": 2}
_HINT_RULES: Dict[str, tuple[str, str, str]] = {
    "solver-mirror-write": (
        "Direct solver mirror write",
        "Runtime",
        "Replace direct writes with solver control-plane projection APIs.",
    ),
    "runtime-bypass-write": (
        "Runtime state bypass write",
        "Runtime",
        "Write through runtime APIs or snapshot projection helpers only.",
    ),
    "runtime-private-call": (
        "Private runtime call",
        "Runtime",
        "Do not call solver.runtime._* methods directly; use public solver control-plane APIs.",
    ),
    "state-roundtrip-asymmetric": (
        "Asymmetric state roundtrip",
        "Checkpoint",
        "Define symmetric get_state()/set_state() to support checkpoint restore.",
    ),
    "state-recovery-level-missing": (
        "Missing recovery level",
        "Checkpoint",
        "Declare state_recovery_level using L0/L1/L2 on stateful components.",
    ),
    "state-recovery-level-invalid": (
        "Invalid recovery level",
        "Checkpoint",
        "Use one of: L0 / L1 / L2.",
    ),
    "plugin-direct-solver-state-access": (
        "Plugin direct solver state access",
        "Plugin",
        "Use resolve_population_snapshot()/commit_population_snapshot() instead.",
    ),
    "class-contract-missing": (
        "Missing context contract",
        "Contract",
        "Add explicit context_requires/provides/mutates/cache on the component class.",
    ),
    "class-contract-core-missing": (
        "Core contract keys missing",
        "Contract",
        "Declare at least context_requires/context_provides/context_mutates.",
    ),
    "contract-key-unknown": (
        "Unknown contract key",
        "Contract",
        "Use canonical keys from context_keys.py, or metrics.* namespace.",
    ),
    "contract-impl-mismatch": (
        "Contract vs implementation mismatch",
        "Contract",
        "Align context reads/writes with declared requires/provides/mutates/cache.",
    ),
    "context-large-object-write": (
        "Large object written to context",
        "Snapshot",
        "Move large payloads to SnapshotStore and keep only refs in context.",
    ),
    "snapshot-ref-empty": (
        "Snapshot ref empty",
        "Snapshot",
        "Ensure snapshot refs and snapshot_key are non-empty when present.",
    ),
    "snapshot-ref-missing": (
        "Snapshot key missing",
        "Snapshot",
        "Write snapshot before exposing population/objectives/violations context.",
    ),
    "snapshot-ref-consistency": (
        "Snapshot ref inconsistency",
        "Snapshot",
        "Keep snapshot_key and *_ref coherent; validate read_snapshot for each ref.",
    ),
    "snapshot-read-failed": (
        "Snapshot read failed",
        "Snapshot",
        "Check snapshot backend connectivity and reader exceptions.",
    ),
    "snapshot-missing": (
        "Snapshot payload missing",
        "Snapshot",
        "Ensure snapshot backend persistence and TTL policy are valid.",
    ),
    "snapshot-payload-integrity": (
        "Snapshot payload integrity issue",
        "Snapshot",
        "Fix payload keys/shapes for population/objectives/violations.",
    ),
    "broad-except-swallow-core": (
        "Broad exception swallow in core",
        "Reliability",
        "Replace silent `except Exception` with report_soft_error/logging or strict raise.",
    ),
    "broad-except-swallow": (
        "Broad exception swallow",
        "Reliability",
        "Avoid `except Exception: pass/return`; keep observability with structured error logging.",
    ),
    "snapshot-redis-pickle-unsafe": (
        "Unsafe Redis snapshot serializer",
        "Security",
        "Use snapshot serializer='safe' (recommended) or pickle_signed + HMAC.",
    ),
    "snapshot-redis-pickle-signed-missing-key": (
        "Signed serializer missing key",
        "Security",
        "Set snapshot_store_hmac_env_var and provide key in environment.",
    ),
    "snapshot-redis-serializer-unknown": (
        "Unknown snapshot serializer",
        "Security",
        "Use one of: safe / pickle_signed / pickle_unsafe.",
    ),
    "redis-key-prefix-missing": (
        "Redis key prefix missing",
        "Store",
        "Set a non-empty context_store_key_prefix.",
    ),
    "redis-key-prefix-too-short": (
        "Redis key prefix too short",
        "Store",
        "Use a longer prefix to avoid collisions across projects.",
    ),
    "redis-key-prefix-missing-project-name": (
        "Redis key prefix missing project token",
        "Store",
        "Include project name token in Redis key prefix.",
    ),
    "redis-ttl-policy-implicit": (
        "Redis TTL policy implicit",
        "Store",
        "Set explicit context_store_ttl_seconds (or 0 for no-expire).",
    ),
    "redis-ttl-invalid": (
        "Redis TTL invalid",
        "Store",
        "Use numeric ttl value or None.",
    ),
    "metrics-provider-missing": (
        "Metrics provider missing",
        "Metrics",
        "Provide required metrics.* keys or declare fallback policy.",
    ),
    "algorithm-as-bias": (
        "Process-level algorithm attached as bias",
        "Architecture",
        "Move process-level algorithm classes to adapter/strategy layer.",
    ),
    "framework-component-not-in-catalog": (
        "Framework component not in catalog",
        "Catalog",
        "Register framework component entry in catalog.",
    ),
    "project-component-unregistered": (
        "Project component unregistered",
        "Catalog",
        "Register project component in local project_registry.py.",
    ),
}


def count_doctor_guard_issues(report: Any) -> tuple[int, int]:
    """Return (solver_mirror_write_count, plugin_direct_state_access_count)."""
    diagnostics = list(getattr(report, "diagnostics", ()) or ())
    mirror_count = sum(1 for d in diagnostics if getattr(d, "code", "") == "solver-mirror-write")
    plugin_state_count = sum(
        1 for d in diagnostics if getattr(d, "code", "") == "plugin-direct-solver-state-access"
    )
    return int(mirror_count), int(plugin_state_count)


def _normalize_level(level: Any) -> str:
    text = str(level or "").strip().lower()
    if text in _LEVEL_ORDER:
        return text
    return "info"


def _effective_level(level: Any, *, strict: bool) -> str:
    norm = _normalize_level(level)
    if strict and norm == "warn":
        return "error"
    return norm


def build_doctor_visual_hints(report: Any, *, strict: bool = False) -> List[DoctorVisualHint]:
    diagnostics = list(getattr(report, "diagnostics", ()) or ())
    grouped: Dict[str, List[Any]] = {}
    for diag in diagnostics:
        code = str(getattr(diag, "code", "") or "").strip()
        if not code:
            continue
        grouped.setdefault(code, []).append(diag)

    hints: List[DoctorVisualHint] = []
    for code, rows in grouped.items():
        if not rows:
            continue
        levels = [_effective_level(getattr(row, "level", "info"), strict=strict) for row in rows]
        level = min(levels, key=lambda x: _LEVEL_ORDER.get(x, 9))
        title, category, suggestion = _HINT_RULES.get(
            code,
            (
                "Doctor diagnostic",
                "General",
                "Read diagnostic detail and align component contract/runtime behavior.",
            ),
        )
        sample = ""
        for row in rows:
            msg = str(getattr(row, "message", "") or "").strip()
            if msg:
                sample = msg
                break
        hints.append(
            DoctorVisualHint(
                code=code,
                level=level,
                count=len(rows),
                title=title,
                category=category,
                suggestion=suggestion,
                sample=sample,
            )
        )

    hints.sort(key=lambda h: (_LEVEL_ORDER.get(h.level, 9), -int(h.count), h.code))
    return hints


class DoctorView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self.path_var = tk.StringVar(value=str(self._default_path()))
        self.build_var = tk.BooleanVar(value=True)
        self.strict_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")
        self.guard_var = tk.StringVar(value="Strict guards: mirror=-, plugin-state=-")
        self.hint_summary_var = tk.StringVar(value="Hints: blockers=-, warnings=-, infos=-")
        self._run_btn: ttk.Button | None = None
        self._hint_row_map: Dict[str, DoctorVisualHint] = {}
        self._build()
        self.refresh_state()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Project Doctor", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            self.tab,
            text="Run project structure/contracts diagnostics from the UI.",
            foreground="#666",
        ).pack(anchor="w")

        row = ttk.Frame(self.tab)
        row.pack(fill="x", pady=(8, 4))
        ttk.Label(row, text="Path").pack(side="left")
        ttk.Entry(row, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(row, text="Browse", command=self._browse_path).pack(side="left")

        opts = ttk.Frame(self.tab)
        opts.pack(fill="x", pady=(2, 4))
        ttk.Checkbutton(opts, text="Build solver", variable=self.build_var).pack(side="left")
        ttk.Checkbutton(opts, text="Strict", variable=self.strict_var).pack(side="left", padx=(12, 0))

        actions = ttk.Frame(self.tab)
        actions.pack(fill="x", pady=(2, 6))
        self._run_btn = ttk.Button(actions, text="Run Doctor", command=self.run_doctor)
        self._run_btn.pack(side="left")
        ttk.Button(actions, text="Use Workspace", command=self.use_default_path).pack(side="left", padx=(6, 0))

        ttk.Label(self.tab, textvariable=self.status_var, foreground="#666").pack(anchor="w", pady=(2, 4))
        ttk.Label(self.tab, textvariable=self.guard_var, foreground="#666").pack(anchor="w", pady=(0, 4))
        ttk.Label(self.tab, textvariable=self.hint_summary_var, foreground="#666").pack(anchor="w", pady=(0, 4))

        notebook = ttk.Notebook(self.tab)
        notebook.pack(fill="both", expand=True)

        hints_tab = ttk.Frame(notebook)
        raw_tab = ttk.Frame(notebook)
        notebook.add(hints_tab, text="Hints")
        notebook.add(raw_tab, text="Raw Report")

        table_wrap = ttk.Frame(hints_tab)
        table_wrap.pack(fill="both", expand=True)
        cols = ("level", "category", "code", "count", "title")
        self.hint_table = ttk.Treeview(table_wrap, columns=cols, show="headings", height=8)
        for col, width in (
            ("level", 80),
            ("category", 100),
            ("code", 190),
            ("count", 70),
            ("title", 260),
        ):
            self.hint_table.heading(col, text=col)
            self.hint_table.column(col, width=width, anchor="w")
        ybar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.hint_table.yview)
        self.hint_table.configure(yscrollcommand=ybar.set)
        self.hint_table.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")
        self.hint_table.bind("<<TreeviewSelect>>", self._on_hint_select)
        self.hint_table.tag_configure("error", foreground="#b71c1c")
        self.hint_table.tag_configure("warn", foreground="#e65100")
        self.hint_table.tag_configure("info", foreground="#1b5e20")

        self.hint_detail = tk.Text(hints_tab, height=7, wrap="word", borderwidth=1, relief="solid")
        self.hint_detail.pack(fill="x", pady=(6, 0))
        self.hint_detail.insert("1.0", "Run doctor to generate visual hints.")
        self.hint_detail.config(state="disabled")

        self.output = tk.Text(raw_tab, height=16, wrap="word", borderwidth=1, relief="solid")
        self.output.pack(fill="both", expand=True)
        self._set_output("Click 'Run Doctor' to inspect project structure and contracts.")

    def refresh_state(self) -> None:
        """Enable doctor only after an entry is loaded (non-empty start)."""
        has_entry = bool(str(getattr(self.app, "entry", "") or "").strip())
        if self._run_btn is not None:
            if has_entry:
                self._run_btn.state(["!disabled"])
            else:
                self._run_btn.state(["disabled"])
        if not has_entry:
            self.status_var.set("Load an entry file first (empty mode disabled).")
            self.guard_var.set("Strict guards: mirror=-, plugin-state=-")
            self._set_hint_summary([])
            self._set_hint_detail("Doctor is available after loading an entry file.")
            self._set_output("Doctor is available after loading an entry file.")
        elif self.status_var.get().startswith("Load an entry file first"):
            self.status_var.set("Ready")

    def _default_path(self) -> Path:
        if self.app.workspace is not None:
            return Path(self.app.workspace).resolve()
        entry = str(getattr(self.app, "entry", "") or "")
        if ":" in entry:
            entry_path = entry.rsplit(":", 1)[0].strip()
            if entry_path:
                p = Path(entry_path)
                if p.exists():
                    return p.resolve().parent if p.is_file() else p.resolve()
        return Path.cwd()

    def use_default_path(self) -> None:
        self.path_var.set(str(self._default_path()))

    def _browse_path(self) -> None:
        start = self.path_var.get().strip() or str(self._default_path())
        chosen = filedialog.askdirectory(title="Select project root", initialdir=start)
        if chosen:
            self.path_var.set(chosen)

    def _set_output(self, text: str) -> None:
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.config(state="disabled")

    def _set_hint_detail(self, text: str) -> None:
        self.hint_detail.config(state="normal")
        self.hint_detail.delete("1.0", "end")
        self.hint_detail.insert("1.0", text)
        self.hint_detail.config(state="disabled")

    def _set_hint_summary(self, hints: List[DoctorVisualHint]) -> None:
        blockers = sum(int(h.count) for h in hints if h.level == "error")
        warnings = sum(int(h.count) for h in hints if h.level == "warn")
        infos = sum(int(h.count) for h in hints if h.level == "info")
        self.hint_summary_var.set(f"Hints: blockers={blockers}, warnings={warnings}, infos={infos}")

    def _render_hints(self, hints: List[DoctorVisualHint]) -> None:
        self._hint_row_map = {}
        for row_id in self.hint_table.get_children():
            self.hint_table.delete(row_id)
        self._set_hint_summary(hints)
        if not hints:
            self._set_hint_detail("No diagnostics. Doctor is clean for current checks.")
            return
        for hint in hints:
            row_id = self.hint_table.insert(
                "",
                "end",
                values=(hint.level.upper(), hint.category, hint.code, str(hint.count), hint.title),
                tags=(hint.level,),
            )
            self._hint_row_map[str(row_id)] = hint
        first = self.hint_table.get_children()
        if first:
            self.hint_table.selection_set(first[0])
            self.hint_table.focus(first[0])
            self._on_hint_select(None)

    def _on_hint_select(self, _event: Any) -> None:
        sel = self.hint_table.selection()
        if not sel:
            return
        hint = self._hint_row_map.get(str(sel[0]))
        if hint is None:
            return
        lines = [
            f"Code: {hint.code}",
            f"Level: {hint.level.upper()}",
            f"Category: {hint.category}",
            f"Count: {hint.count}",
            f"Meaning: {hint.title}",
            f"Action: {hint.suggestion}",
        ]
        if hint.sample:
            lines.append(f"Sample: {hint.sample}")
        self._set_hint_detail("\n".join(lines))

    def run_doctor(self) -> None:
        try:
            from nsgablack.project import format_doctor_report, run_project_doctor
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Doctor unavailable: {exc}")
            self._set_output(f"Failed to import doctor modules:\n{exc}")
            self._render_hints([])
            return

        raw = self.path_var.get().strip()
        path = Path(raw).resolve() if raw else self._default_path()
        strict = bool(self.strict_var.get())

        try:
            report = run_project_doctor(
                path=path,
                instantiate_solver=bool(self.build_var.get()),
                strict=strict,
            )
            text = format_doctor_report(report)
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Doctor failed: {exc}")
            self._set_output(f"Doctor run failed:\n{exc}")
            self._render_hints([])
            return

        strict_fail = strict and report.warn_count > 0
        failed = report.error_count > 0 or strict_fail
        mirror_count, plugin_state_count = count_doctor_guard_issues(report)
        self.guard_var.set(
            f"Strict guards: mirror={mirror_count}, plugin-state={plugin_state_count}"
        )
        hints = build_doctor_visual_hints(report, strict=strict)
        self._render_hints(hints)
        if failed:
            self.status_var.set(
                f"FAILED: errors={report.error_count}, warnings={report.warn_count}, infos={report.info_count}"
            )
        else:
            self.status_var.set(
                f"OK: errors={report.error_count}, warnings={report.warn_count}, infos={report.info_count}"
            )

        if strict_fail:
            text = f"{text}\n[STRICT] warnings>0 => fail"
        self._set_output(text)
