from __future__ import annotations

from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, ttk


def count_doctor_guard_issues(report: Any) -> tuple[int, int]:
    """Return (solver_mirror_write_count, plugin_direct_state_access_count)."""
    diagnostics = list(getattr(report, "diagnostics", ()) or ())
    mirror_count = sum(1 for d in diagnostics if getattr(d, "code", "") == "solver-mirror-write")
    plugin_state_count = sum(
        1 for d in diagnostics if getattr(d, "code", "") == "plugin-direct-solver-state-access"
    )
    return int(mirror_count), int(plugin_state_count)


class DoctorView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self.path_var = tk.StringVar(value=str(self._default_path()))
        self.build_var = tk.BooleanVar(value=True)
        self.strict_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")
        self.guard_var = tk.StringVar(value="Strict guards: mirror=-, plugin-state=-")
        self._run_btn: ttk.Button | None = None
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
        self.output = tk.Text(self.tab, height=16, wrap="word", borderwidth=1, relief="solid")
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

    def run_doctor(self) -> None:
        try:
            from nsgablack.project import format_doctor_report, run_project_doctor
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Doctor unavailable: {exc}")
            self._set_output(f"Failed to import doctor modules:\n{exc}")
            return

        raw = self.path_var.get().strip()
        path = Path(raw).resolve() if raw else self._default_path()

        try:
            report = run_project_doctor(
                path=path,
                instantiate_solver=bool(self.build_var.get()),
                strict=bool(self.strict_var.get()),
            )
            text = format_doctor_report(report)
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Doctor failed: {exc}")
            self._set_output(f"Doctor run failed:\n{exc}")
            return

        strict_fail = bool(self.strict_var.get()) and report.warn_count > 0
        failed = report.error_count > 0 or strict_fail
        mirror_count, plugin_state_count = count_doctor_guard_issues(report)
        self.guard_var.set(
            f"Strict guards: mirror={mirror_count}, plugin-state={plugin_state_count}"
        )
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
