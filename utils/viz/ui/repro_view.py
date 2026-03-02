from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import tkinter as tk
from tkinter import filedialog, ttk

from ...runtime.repro_bundle import (
    apply_bundle_to_solver,
    compare_repro_bundle,
    load_repro_bundle,
    replay_spec,
)


class ReproView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._bundle: Dict[str, Any] = {}
        self._bundle_path: Optional[Path] = None
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Repro Bundle", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            self.tab,
            text="Load bundle -> compare current wiring -> run by bundle.",
            foreground="#666",
        ).pack(anchor="w", pady=(2, 8))

        top = ttk.Frame(self.tab)
        top.pack(fill="x")
        self.path_var = tk.StringVar(value="bundle: (none)")
        ttk.Label(top, textvariable=self.path_var, foreground="#666").pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="Load Last", command=self.load_last_run).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Load File", command=self.load_file).pack(side="left", padx=(6, 0))

        btns = ttk.Frame(self.tab)
        btns.pack(fill="x", pady=(8, 6))
        ttk.Button(btns, text="Compare Current", command=self.compare_current).pack(side="left", fill="x", expand=True)
        ttk.Button(btns, text="Run By Bundle", command=self.run_by_bundle).pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(btns, text="Export Last", command=self.export_last).pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.status_var = tk.StringVar(value="ready")
        ttk.Label(self.tab, textvariable=self.status_var, foreground="#666").pack(anchor="w", pady=(0, 4))

        self.detail = tk.Text(self.tab, height=18, wrap="word", borderwidth=1, relief="solid")
        self.detail.pack(fill="both", expand=True)
        self.detail.insert("1.0", "No bundle loaded.")
        self.detail.config(state="disabled")

    def _set_detail(self, text: str) -> None:
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")

    def _bundle_path_for_run(self, run_id: str, artifacts: Mapping[str, Any]) -> Path:
        p = artifacts.get("repro_bundle_json") if isinstance(artifacts, Mapping) else None
        if p:
            return Path(str(p)).expanduser().resolve()
        return (Path("runs") / f"{run_id}.repro_bundle.json").resolve()

    def load_last_run(self) -> None:
        run_id = getattr(self.app, "_last_run_id", None)
        artifacts = getattr(self.app, "_last_artifacts", {}) or {}
        if not run_id:
            self.status_var.set("no run yet")
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

    def load_from_run(self, *, run_id: str, artifacts: Mapping[str, Any]) -> None:
        path = self._bundle_path_for_run(run_id, artifacts)
        self.path_var.set(f"bundle: {path}")
        if not path.is_file():
            self._bundle = {}
            self._bundle_path = None
            self.status_var.set(f"bundle not found: run_id={run_id}")
            self._set_detail("Bundle file not found.")
            return
        bundle = load_repro_bundle(path)
        if not bundle:
            self._bundle = {}
            self._bundle_path = None
            self.status_var.set("bundle parse failed")
            self._set_detail("Failed to parse repro bundle JSON.")
            return
        self._bundle = bundle
        self._bundle_path = path
        self.status_var.set("bundle loaded")
        self._set_detail(self._render_bundle_summary(bundle, path))

    def load_file(self) -> None:
        start_dir = str(self.app.workspace or Path.cwd())
        chosen = filedialog.askopenfilename(
            title="Select repro bundle JSON",
            initialdir=start_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not chosen:
            return
        path = Path(chosen).expanduser().resolve()
        self.path_var.set(f"bundle: {path}")
        bundle = load_repro_bundle(path)
        if not bundle:
            self._bundle = {}
            self._bundle_path = None
            self.status_var.set("bundle parse failed")
            self._set_detail("Failed to parse repro bundle JSON.")
            return
        self._bundle = bundle
        self._bundle_path = path
        self.status_var.set("bundle loaded")
        self._set_detail(self._render_bundle_summary(bundle, path))

    def _render_bundle_summary(self, bundle: Mapping[str, Any], path: Path) -> str:
        spec = replay_spec(bundle)
        wiring = bundle.get("wiring", {}) if isinstance(bundle.get("wiring"), Mapping) else {}
        proof = bundle.get("structure_proof", {}) if isinstance(bundle.get("structure_proof"), Mapping) else {}
        lines = [
            f"path: {path}",
            f"schema: {bundle.get('schema_name')} v{bundle.get('schema_version')}",
            f"run_id: {bundle.get('run_id')}",
            f"created_at: {bundle.get('created_at')}",
            f"entrypoint: {spec.get('entrypoint')}",
            f"workspace: {spec.get('workspace')}",
            f"seed: {spec.get('seed')}",
            f"max_generations: {spec.get('max_generations')}",
            f"max_steps: {spec.get('max_steps')}",
            f"adapter: {wiring.get('adapter')}",
            f"structure_hash: {wiring.get('structure_hash')}",
            f"proof.sequence_signature_set_hash: {proof.get('sequence_signature_set_hash')}",
            f"proof.sequence_trie_fingerprint_hash: {proof.get('sequence_trie_fingerprint_hash')}",
            f"proof.trace_group_digest_hash: {proof.get('trace_group_digest_hash')}",
            f"proof.decision_trace_digest_hash: {proof.get('decision_trace_digest_hash')}",
        ]
        return "\n".join(lines)

    def compare_current(self) -> None:
        if not self._bundle:
            self.status_var.set("load bundle first")
            return
        if self.app.solver is None:
            self.status_var.set("no solver loaded")
            return
        snap = None
        run_view = getattr(self.app, "run_view", None)
        if run_view is not None and hasattr(run_view, "snapshot"):
            try:
                snap = run_view.snapshot(run_id="compare_preview")
            except Exception:
                snap = None
        result = compare_repro_bundle(
            self._bundle,
            current_entrypoint=str(self.app.entry or ""),
            current_workspace=self.app.workspace or Path.cwd(),
            current_snapshot=snap,
            current_solver=self.app.solver,
        )
        lines = [
            f"status: {result.get('status')}",
            f"blockers: {result.get('blockers')}",
            f"warnings: {result.get('warnings')}",
            f"infos: {result.get('infos')}",
        ]
        for row in result.get("findings", []):
            lines.append(
                f"[{row.get('level')}] {row.get('code')}: {row.get('message')} "
                f"(expected={row.get('expected')}, actual={row.get('actual')})"
            )
        if not result.get("findings"):
            lines.append("No drift detected.")
        self._set_detail("\n".join(lines))
        self.status_var.set(f"compare: {result.get('status')}")

    def _load_entry_if_needed(self, entrypoint: str) -> bool:
        text = str(entrypoint or "").strip()
        if not text:
            return True
        if text == str(self.app.entry or "").strip():
            return True
        if ":" in text:
            path_text, func = text.rsplit(":", 1)
        else:
            path_text, func = text, "build_solver"
        self.app._entry_path_var.set(path_text)
        self.app._entry_func_var.set(func or "build_solver")
        self.app._load_selected_entry()
        return self.app.solver is not None

    def run_by_bundle(self) -> None:
        if not self._bundle:
            self.status_var.set("load bundle first")
            return
        if getattr(self.app, "_is_running", False):
            self.status_var.set("run already in progress")
            return
        spec = replay_spec(self._bundle)
        if not self._load_entry_if_needed(str(spec.get("entrypoint") or "")):
            self.status_var.set("failed to load entry from bundle")
            return
        if self.app.solver is None:
            self.status_var.set("no solver")
            return
        applied = apply_bundle_to_solver(self.app.solver, self._bundle)
        base_run_id = str(spec.get("run_id") or self._bundle.get("run_id") or "bundle_run").strip() or "bundle_run"
        replay_run_id = f"{base_run_id}_replay_{time.strftime('%H%M%S')}"
        try:
            self.app.run_id_var.set(replay_run_id)
        except Exception:
            pass
        run_view = getattr(self.app, "run_view", None)
        if run_view is None:
            self.status_var.set("run view unavailable")
            return
        run_view.sync_run_id_plugins(replay_run_id)
        run_view.on_run()
        self.status_var.set("run launched by bundle")
        detail = {
            "action": "run_by_bundle",
            "bundle_path": str(self._bundle_path) if self._bundle_path else None,
            "replay_run_id": replay_run_id,
            "applied": applied,
        }
        self._set_detail(json.dumps(detail, ensure_ascii=False, indent=2))

    def export_last(self) -> None:
        run_id = getattr(self.app, "_last_run_id", None)
        artifacts = getattr(self.app, "_last_artifacts", {}) or {}
        if not run_id:
            self.status_var.set("no run yet")
            return
        path = self._bundle_path_for_run(str(run_id), artifacts)
        if not path.is_file():
            self.status_var.set("last run bundle not found")
            return
        bundle = load_repro_bundle(path)
        if not bundle:
            self.status_var.set("last run bundle parse failed")
            return
        self._bundle = bundle
        self._bundle_path = path
        self.path_var.set(f"bundle: {path}")
        self.status_var.set("loaded last run bundle")
        self._set_detail(self._render_bundle_summary(bundle, path))

