import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk


ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "runs" / "visualizer"


class ContributionView:
    def __init__(self, app: Any, contrib_tab: ttk.Frame, traj_tab: ttk.Frame) -> None:
        self.app = app
        self.contrib_tab = contrib_tab
        self.traj_tab = traj_tab
        self._build_contrib()
        self._build_traj()

    def _build_contrib(self) -> None:
        ttk.Label(self.contrib_tab, text="Module Contribution", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(self.contrib_tab, text="Based on ModuleReportPlugin outputs", foreground="#666").pack(anchor="w")
        run_pick = ttk.Frame(self.contrib_tab)
        run_pick.pack(fill="x", pady=(6, 4))
        ttk.Label(run_pick, text="Run ID").pack(side="left")
        self.contribution_run_var = tk.StringVar()
        self.contribution_run_combo = ttk.Combobox(
            run_pick,
            textvariable=self.contribution_run_var,
            state="readonly",
            width=32,
        )
        self.contribution_run_combo.pack(side="left", padx=(6, 6), fill="x", expand=True)
        self.contribution_run_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_contribution())
        ttk.Button(run_pick, text="Reload", command=self.reload_run_choices).pack(side="left")

        compare_row = ttk.Frame(self.contrib_tab)
        compare_row.pack(fill="x", pady=(0, 4))
        ttk.Label(compare_row, text="Compare").pack(side="left")
        self.compare_left_var = tk.StringVar()
        self.compare_left_combo = ttk.Combobox(compare_row, textvariable=self.compare_left_var, state="readonly", width=16)
        self.compare_left_combo.pack(side="left", padx=(6, 6))
        ttk.Label(compare_row, text="vs").pack(side="left")
        self.compare_right_var = tk.StringVar()
        self.compare_right_combo = ttk.Combobox(compare_row, textvariable=self.compare_right_var, state="readonly", width=16)
        self.compare_right_combo.pack(side="left", padx=(6, 6))
        ttk.Button(compare_row, text="Diff", command=self.compare_runs).pack(side="left")

        self.compare_text = tk.Text(self.contrib_tab, height=6, wrap="word", borderwidth=1, relief="solid")
        self.compare_text.pack(fill="x", pady=(4, 6))
        self.compare_text.insert("1.0", "Select two runs and click Diff to compare configuration snapshots.")
        self.compare_text.config(state="disabled")

        ttk.Label(self.contrib_tab, text="Structure Hash Map", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        hash_row = ttk.Frame(self.contrib_tab)
        hash_row.pack(fill="x", pady=(4, 2))
        ttk.Button(hash_row, text="Refresh Hash Map", command=self._refresh_hash_map).pack(side="left")
        self.hash_text = tk.Text(self.contrib_tab, height=5, wrap="word", borderwidth=1, relief="solid")
        self.hash_text.pack(fill="x", pady=(4, 6))
        self.hash_text.insert("1.0", "No hash map yet. Run once to generate snapshots.")
        self.hash_text.config(state="disabled")

        self.contribution_text = tk.Text(self.contrib_tab, height=6, wrap="word", borderwidth=1, relief="solid")
        self.contribution_text.pack(fill="x", pady=(6, 6))
        self.contribution_text.insert("1.0", "No report yet. Run once to generate module/bias reports.")
        self.contribution_text.config(state="disabled")
        ttk.Label(self.contrib_tab, text="Bias Contributions (sorted)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.bias_tree = ttk.Treeview(
            self.contrib_tab,
            columns=("name", "total", "usage", "avg", "weight"),
            show="headings",
            height=8,
        )
        self.bias_tree.heading("name", text="name")
        self.bias_tree.heading("total", text="total")
        self.bias_tree.heading("usage", text="count")
        self.bias_tree.heading("avg", text="avg")
        self.bias_tree.heading("weight", text="weight")
        self.bias_tree.column("name", width=140, anchor="w")
        self.bias_tree.column("total", width=90, anchor="e")
        self.bias_tree.column("usage", width=60, anchor="e")
        self.bias_tree.column("avg", width=90, anchor="e")
        self.bias_tree.column("weight", width=70, anchor="e")
        self.bias_tree.pack(fill="both", expand=True, pady=(4, 6))
        self.bias_tree.bind("<<TreeviewSelect>>", self._on_bias_select)
        ttk.Label(self.contrib_tab, text="Bias Detail (per-call / per-generation)", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.bias_detail_text = tk.Text(self.contrib_tab, height=6, wrap="word", borderwidth=1, relief="solid")
        self.bias_detail_text.pack(fill="both", expand=True, pady=(4, 6))
        self.bias_detail_text.insert("1.0", "Select a bias row to see per-call / per-generation details.")
        self.bias_detail_text.config(state="disabled")

        ttk.Button(self.contrib_tab, text="Refresh", command=self.refresh_contribution).pack(fill="x", pady=(2, 0))

    def _build_traj(self) -> None:
        ttk.Label(self.traj_tab, text="Strategy Weight Trajectory", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(self.traj_tab, text="Switch events from dynamic_switch", foreground="#666").pack(anchor="w")
        traj_pick = ttk.Frame(self.traj_tab)
        traj_pick.pack(fill="x", pady=(6, 4))
        ttk.Label(traj_pick, text="Run ID").pack(side="left")
        self.traj_run_combo = ttk.Combobox(
            traj_pick,
            textvariable=self.contribution_run_var,
            state="readonly",
            width=32,
        )
        self.traj_run_combo.pack(side="left", padx=(6, 6), fill="x", expand=True)
        self.traj_run_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_contribution())
        ttk.Button(traj_pick, text="Reload", command=self.reload_run_choices).pack(side="left")
        self.switch_canvas = tk.Canvas(self.traj_tab, height=220, background="white", highlightthickness=1, highlightbackground="#ddd")
        self.switch_canvas.pack(fill="both", expand=True, pady=(6, 6))
        self.switch_canvas.create_text(6, 10, anchor="w", fill="#888", text="Weight trajectory will appear here after a run.")

    def add_run_choice(self, run_id: str) -> None:
        run_id = str(run_id).strip()
        if not run_id:
            return
        if run_id not in self.app._run_choices:
            self.app._run_choices.insert(0, run_id)
        values = ["ALL"] + [r for r in self.app._run_choices if r.upper() != "ALL"]
        self.contribution_run_combo["values"] = values
        self.compare_left_combo["values"] = values
        self.compare_right_combo["values"] = values
        self.contribution_run_var.set(run_id)

    def reload_run_choices(self) -> None:
        base = Path("runs")
        ids = set()
        if base.exists():
            for path in base.glob("*.modules.json"):
                ids.add(path.name.replace(".modules.json", ""))
            for path in base.glob("*.bias.json"):
                ids.add(path.name.replace(".bias.json", ""))
        if self.app._last_run_id:
            ids.add(self.app._last_run_id)
        self.app._run_choices = sorted(ids, reverse=True)
        values = ["ALL"] + self.app._run_choices
        self.contribution_run_combo["values"] = values
        self.compare_left_combo["values"] = values
        self.compare_right_combo["values"] = values
        if not self.contribution_run_var.get() and self.app._last_run_id:
            self.contribution_run_var.set(self.app._last_run_id)

    def refresh_contribution(self) -> None:
        run_id = self.contribution_run_var.get().strip() or self.app._last_run_id or self.app.run_id_var.get().strip()
        if not run_id:
            self._set_contribution_text("No run id available.")
            self._set_bias_rows([])
            self._draw_switch_trajectory([])
            return
        if run_id.upper() == "ALL":
            text, bias_rows = self._load_all_contributions()
            self._draw_switch_trajectory([])
        else:
            text, bias_rows = self._load_contribution_report(run_id, self.app._last_artifacts)
            self._draw_switch_trajectory(self._load_switch_events(run_id))
        self._set_contribution_text(text)
        self._set_bias_rows(bias_rows)
        self._refresh_hash_map()
        if run_id:
            self.contribution_run_var.set(run_id)

    def _set_contribution_text(self, text: str) -> None:
        self.contribution_text.config(state="normal")
        self.contribution_text.delete("1.0", "end")
        self.contribution_text.insert("1.0", text)
        self.contribution_text.config(state="disabled")

    def _set_hash_text(self, text: str) -> None:
        self.hash_text.config(state="normal")
        self.hash_text.delete("1.0", "end")
        self.hash_text.insert("1.0", text)
        self.hash_text.config(state="disabled")

    def _set_bias_rows(self, rows: List[Dict[str, Any]]) -> None:
        for item in self.bias_tree.get_children():
            self.bias_tree.delete(item)
        self.app._bias_detail_map = {}
        for row in rows:
            name = row["name"]
            self.app._bias_detail_map[str(name)] = row
            self.bias_tree.insert(
                "",
                "end",
                values=(name, row["total"], row["usage"], row["avg"], row["weight"]),
                tags=(row["name"],),
            )

    def _load_modules_json(self, run_id: str) -> Optional[Dict[str, Any]]:
        base = Path("runs")
        modules_path = base / f"{run_id}.modules.json"
        if modules_path.exists():
            try:
                return json.loads(modules_path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _load_switch_events(self, run_id: str) -> List[Dict[str, Any]]:
        data = self._load_modules_json(run_id) or {}
        return data.get("dynamic_switch_events", []) or []

    def _load_contribution_report(
        self, run_id: str, artifacts: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        base = Path("runs")
        modules_path = base / f"{run_id}.modules.json"
        bias_path = base / f"{run_id}.bias.json"
        if artifacts and run_id == self.app._last_run_id:
            mod_path = artifacts.get("modules_report_json")
            bias_json_path = artifacts.get("bias_report_json")
            if isinstance(mod_path, str) and mod_path:
                modules_path = Path(mod_path)
            if isinstance(bias_json_path, str) and bias_json_path:
                bias_path = Path(bias_json_path)
        lines: List[str] = []
        bias_rows: List[Dict[str, Any]] = []
        lines.append(f"run_id: {run_id}")
        if modules_path.exists():
            try:
                data = json.loads(modules_path.read_text(encoding="utf-8"))
                lines.append(f"modules_report: {modules_path}")
                plugins = data.get("plugins", [])
                if plugins:
                    lines.append("")
                    lines.append("Plugins:")
                    for p in plugins:
                        name = p.get("name", "")
                        cls = p.get("class", "")
                        enabled = p.get("enabled", True)
                        lines.append(f"- {name} ({cls}) enabled={enabled}")
                pipe = data.get("pipeline") or {}
                if pipe:
                    lines.append("")
                    lines.append("Pipeline:")
                    for k, v in pipe.items():
                        if k == "class":
                            continue
                        if isinstance(v, dict):
                            lines.append(f"- {k}: {v.get('class')}")
                adapter = data.get("adapter", {})
                if isinstance(adapter, dict) and adapter.get("class"):
                    lines.append("")
                    lines.append(f"Adapter: {adapter.get('class')}")

                events = data.get("dynamic_switch_events", []) or []
                if events:
                    lines.append("")
                    lines.append(f"Switch events: {len(events)}")
                    for ev in events[-6:]:
                        gen = ev.get("generation")
                        mode = ev.get("mode")
                        weights = ev.get("strategy_weights", []) or []
                        w_str = ", ".join(
                            f"{w.get('name')}={w.get('weight'):.3g}" if isinstance(w.get("weight"), (int, float)) else f"{w.get('name')}={w.get('weight')}"
                            for w in weights
                        )
                        lines.append(f"- gen={gen} mode={mode} weights: {w_str}")
            except Exception as exc:
                lines.append(f"modules_report load failed: {exc}")
        else:
            lines.append(f"modules_report missing: {modules_path}")

        if bias_path.exists():
            try:
                data = json.loads(bias_path.read_text(encoding="utf-8"))
                lines.append("")
                lines.append(f"bias_report: {bias_path}")
                if not data.get("enabled", False):
                    lines.append("Bias: disabled or unavailable")
                else:
                    total = data.get("total_contribution", 0.0)
                    lines.append(f"total_contribution: {total}")
                    biases = data.get("biases", [])
                    if biases:
                        lines.append("Top biases:")
                        for i, b in enumerate(biases[:8], start=1):
                            name = b.get("name", "")
                            contrib = float(b.get("total_contribution", 0.0) or 0.0)
                            usage = int(b.get("usage_count", 0) or 0)
                            weight = b.get("weight", "")
                            avg = (contrib / usage) if usage > 0 else 0.0
                            lines.append(
                                f"- {i}. {name} contrib={contrib} usage={usage} avg={avg:.4g} weight={weight}"
                            )
                        for b in biases:
                            name = str(b.get("name", ""))
                            contrib = float(b.get("total_contribution", 0.0) or 0.0)
                            usage = int(b.get("usage_count", 0) or 0)
                            weight = b.get("weight", "")
                            avg = (contrib / usage) if usage > 0 else 0.0
                            bias_rows.append(
                                {
                                    "name": name,
                                    "total": f"{contrib:.6g}",
                                    "usage": str(usage),
                                    "avg": f"{avg:.6g}",
                                    "weight": f"{weight}",
                                    "recent_values": b.get("recent_values", []),
                                    "per_generation_stats": b.get("per_generation_stats", []),
                                }
                            )
            except Exception as exc:
                lines.append(f"bias_report load failed: {exc}")
        else:
            lines.append(f"bias_report missing: {bias_path}")

        return "\n".join(lines), bias_rows

    def _load_all_contributions(self) -> Tuple[str, List[Dict[str, Any]]]:
        base = Path("runs")
        totals: Dict[str, Dict[str, Any]] = {}
        run_ids = [r for r in self.app._run_choices if r.upper() != "ALL"]
        for run_id in run_ids:
            bias_path = base / f"{run_id}.bias.json"
            if not bias_path.exists():
                continue
            try:
                data = json.loads(bias_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for b in data.get("biases", []):
                name = str(b.get("name", ""))
                if not name:
                    continue
                contrib = float(b.get("total_contribution", 0.0) or 0.0)
                usage = int(b.get("usage_count", 0) or 0)
                weight = b.get("weight", "")
                agg = totals.setdefault(name, {"total": 0.0, "usage": 0, "weight": weight})
                agg["total"] += contrib
                agg["usage"] += usage
                if weight:
                    agg["weight"] = weight
        rows = []
        for name, agg in sorted(totals.items(), key=lambda x: x[1]["total"], reverse=True):
            usage = agg["usage"]
            total = agg["total"]
            avg = (total / usage) if usage > 0 else 0.0
            rows.append(
                {
                    "name": name,
                    "total": f"{total:.6g}",
                    "usage": str(usage),
                    "avg": f"{avg:.6g}",
                    "weight": f"{agg.get('weight', '')}",
                    "recent_values": [],
                    "per_generation_stats": [],
                }
            )
        text = "Run ID: ALL\n\nAggregated bias contributions across runs."
        return text, rows

    def _diff_snapshots(self, left_id: str, right_id: str) -> str:
        left_path = RUNS_DIR / f"{left_id}.json"
        right_path = RUNS_DIR / f"{right_id}.json"
        if not left_path.exists() or not right_path.exists():
            return "Missing snapshot(s) in runs/visualizer. Run once with UI to generate snapshots."
        try:
            left = json.loads(left_path.read_text(encoding="utf-8"))
            right = json.loads(right_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return f"Snapshot load failed: {exc}"

        diffs = []
        def key_fmt(prefix, name, field):
            return f"{prefix}.{name}.{field}"

        def index_by_name(items):
            return {str(i.get("name", "")): i for i in items or []}

        for prefix, field in [("strategy", "weight"), ("strategy", "enabled")]:
            lmap = index_by_name(left.get("strategies", []))
            rmap = index_by_name(right.get("strategies", []))
            for name in sorted(set(lmap) | set(rmap)):
                lv = lmap.get(name, {}).get(field)
                rv = rmap.get(name, {}).get(field)
                if lv != rv:
                    diffs.append(f"- {key_fmt(prefix, name, field)}: {lv} -> {rv}")

        for prefix, field in [("bias", "enabled"), ("bias", "class")]:
            lmap = index_by_name(left.get("biases", []))
            rmap = index_by_name(right.get("biases", []))
            for name in sorted(set(lmap) | set(rmap)):
                lv = lmap.get(name, {}).get(field)
                rv = rmap.get(name, {}).get(field)
                if lv != rv:
                    diffs.append(f"- {key_fmt(prefix, name, field)}: {lv} -> {rv}")

        for prefix, field in [("plugin", "enabled"), ("plugin", "class")]:
            lmap = index_by_name(left.get("plugins", []))
            rmap = index_by_name(right.get("plugins", []))
            for name in sorted(set(lmap) | set(rmap)):
                lv = lmap.get(name, {}).get(field)
                rv = rmap.get(name, {}).get(field)
                if lv != rv:
                    diffs.append(f"- {key_fmt(prefix, name, field)}: {lv} -> {rv}")

        lp = left.get("pipeline", {}) or {}
        rp = right.get("pipeline", {}) or {}
        for field in ("initializer", "mutator", "repair", "codec"):
            lv = lp.get(field)
            rv = rp.get(field)
            if lv != rv:
                diffs.append(f"- pipeline.{field}: {lv} -> {rv}")

        if not diffs:
            diffs.append("No differences detected.")
        return "\n".join(diffs)



    def _load_snapshot(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = RUNS_DIR / f"{run_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _refresh_hash_map(self) -> None:
        if not RUNS_DIR.exists():
            self._set_hash_text("No snapshots found in runs/visualizer.")
            return
        buckets: Dict[str, List[str]] = {}
        for path in RUNS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            h = data.get("structure_hash_short") or ""
            if not h:
                h = self._compute_structure_hash_short(data)
            rid = data.get("run_id") or path.stem
            if not h:
                continue
            buckets.setdefault(str(h), []).append(str(rid))
        if not buckets:
            self._set_hash_text("No valid structure_hash found.")
            return
        lines = ["Groups by structure_hash_short:"]
        for h, runs in sorted(buckets.items(), key=lambda x: len(x[1]), reverse=True):
            runs_sorted = sorted(runs)
            lines.append(f"- {h}  count={len(runs_sorted)}  runs={', '.join(runs_sorted)}")
        self._set_hash_text("\n".join(lines))

    def _compute_structure_hash_short(self, snap: Dict[str, Any]) -> str:
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
        try:
            raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
        except Exception:
            return ""
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    def _compute_delta_keys(self, left: Dict[str, Any], right: Dict[str, Any]) -> List[str]:
        keys: List[str] = []

        def index_by_name(items):
            return {str(i.get("name", "")): i for i in items or []}

        if left.get("adapter") != right.get("adapter"):
            keys.append("adapter.class")
        if left.get("solver") != right.get("solver"):
            keys.append("solver.class")

        lmap = index_by_name(left.get("strategies", []))
        rmap = index_by_name(right.get("strategies", []))
        for name in sorted(set(lmap) | set(rmap)):
            lv = lmap.get(name, {}).get("enabled")
            rv = rmap.get(name, {}).get("enabled")
            if lv != rv:
                keys.append(f"strategy.{name}.enabled")
            lw = lmap.get(name, {}).get("weight")
            rw = rmap.get(name, {}).get("weight")
            if lw != rw:
                keys.append(f"strategy.{name}.weight")

        lmap = index_by_name(left.get("biases", []))
        rmap = index_by_name(right.get("biases", []))
        for name in sorted(set(lmap) | set(rmap)):
            lv = lmap.get(name, {}).get("enabled")
            rv = rmap.get(name, {}).get("enabled")
            if lv != rv:
                keys.append(f"bias.{name}.enabled")

        lmap = index_by_name(left.get("plugins", []))
        rmap = index_by_name(right.get("plugins", []))
        for name in sorted(set(lmap) | set(rmap)):
            lv = lmap.get(name, {}).get("enabled")
            rv = rmap.get(name, {}).get("enabled")
            if lv != rv:
                keys.append(f"plugin.{name}.enabled")

        lp = left.get("pipeline", {}) or {}
        rp = right.get("pipeline", {}) or {}
        for field in ("initializer", "mutator", "repair", "codec"):
            if lp.get(field) != rp.get(field):
                keys.append(f"pipeline.{field}")

        return keys

    def compare_runs(self) -> None:
        left_id = self.compare_left_var.get().strip()
        right_id = self.compare_right_var.get().strip()
        if not left_id or not right_id:
            self._set_compare_text("Select two runs to compare.")
            return
        header = f"Compare: {left_id} vs {right_id}\n\n"
        body = self._diff_snapshots(left_id, right_id)
        extra = ""
        for rid in (left_id, right_id):
            events = self._load_switch_events(rid)
            if not events:
                continue
            last = events[-1]
            weights = last.get("strategy_weights", []) or []
            w_str = ", ".join(f"{w.get('name')}={w.get('weight'):.6g}" for w in weights)
            extra = (
                f"{extra}\n\nFinal strategy weights ({rid}):\n- {w_str}"
                if w_str
                else extra
            )
        self._set_compare_text(f"{header}{body}{extra}")

        left = self._load_snapshot(left_id)
        right = self._load_snapshot(right_id)
        if left and right:
            self.app._delta_keys = set(self._compute_delta_keys(left, right))
            self.app._refresh_sections()
    def _set_compare_text(self, text: str) -> None:
        self.compare_text.config(state="normal")
        self.compare_text.delete("1.0", "end")
        self.compare_text.insert("1.0", text)
        self.compare_text.config(state="disabled")

    def _on_bias_select(self, _event: Any) -> None:
        sel = self.bias_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        values = self.bias_tree.item(item_id, "values")
        name = values[0] if values else ""
        if not name:
            return
        row = self.app._bias_row_map.get(str(name))
        if row is not None:
            original = row.cget("bg")
            row.configure(bg="#fff2cc")
            self.app.after(700, lambda: row.configure(bg=original))
        detail = self.app._bias_detail_map.get(str(name), {})
        self._set_bias_detail_text(self._format_bias_detail(detail))

    def _set_bias_detail_text(self, text: str) -> None:
        self.bias_detail_text.config(state="normal")
        self.bias_detail_text.delete("1.0", "end")
        self.bias_detail_text.insert("1.0", text)
        self.bias_detail_text.config(state="disabled")

    def _format_bias_detail(self, detail: Dict[str, Any]) -> str:
        if not detail:
            return "No details."
        lines = []
        lines.append(f"name: {detail.get('name')}")
        lines.append(f"total: {detail.get('total')}")
        lines.append(f"usage: {detail.get('usage')}")
        lines.append(f"avg: {detail.get('avg')}")
        lines.append(f"weight: {detail.get('weight')}")
        recent = detail.get("recent_values", []) or []
        if recent:
            lines.append("\nrecent_values:")
            lines.append(", ".join(f"{v:.6g}" if isinstance(v, (int, float)) else str(v) for v in recent[-12:]))
        per_gen = detail.get("per_generation_stats", []) or []
        if per_gen:
            lines.append("\nper_generation_stats:")
            for item in per_gen[-8:]:
                gen = item.get("generation")
                avg_v = item.get("avg_bias")
                cnt = item.get("call_count")
                lines.append(f"- gen={gen} avg={avg_v} count={cnt}")
            spark = self._sparkline([p.get("avg_bias", 0.0) for p in per_gen])
            if spark:
                lines.append(f"trend: {spark}")
        return "\n".join(lines)

    def _sparkline(self, values: List[Any]) -> str:
        chars = " .:-=+*#%@"
        nums = []
        for v in values:
            try:
                nums.append(float(v))
            except Exception:
                nums.append(0.0)
        if not nums:
            return ""
        lo = min(nums)
        hi = max(nums)
        if hi - lo < 1e-12:
            return chars[0] * min(24, len(nums))
        out = []
        for v in nums[-24:]:
            t = (v - lo) / (hi - lo)
            idx = min(len(chars) - 1, max(0, int(t * (len(chars) - 1))))
            out.append(chars[idx])
        return "".join(out)

    def _auto_color(self, idx: int, total: int) -> str:
        if total <= 0:
            total = 1
        hue = (idx / total) % 1.0
        r, g, b = self._hsv_to_rgb(hue, 0.65, 0.9)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> Tuple[int, int, int]:
        h = float(h)
        s = float(s)
        v = float(v)
        i = int(h * 6.0)
        f = h * 6.0 - i
        p = v * (1.0 - s)
        q = v * (1.0 - f * s)
        t = v * (1.0 - (1.0 - f) * s)
        i = i % 6
        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:
            r, g, b = v, p, q
        return int(r * 255), int(g * 255), int(b * 255)

    def _draw_switch_trajectory(self, events: List[Dict[str, Any]]) -> None:
        self.switch_canvas.delete("all")
        if not events:
            self.switch_canvas.create_text(6, 10, anchor="w", fill="#888", text="Weight trajectory will appear here after a run.")
            return
        names = []
        for ev in events:
            for w in ev.get("strategy_weights", []) or []:
                name = str(w.get("name"))
                if name and name not in names:
                    names.append(name)
        if not names:
            return
        width = max(self.switch_canvas.winfo_width(), 600)
        height = max(self.switch_canvas.winfo_height(), 220)
        padding = 20
        xs = []
        for i in range(len(events)):
            if len(events) == 1:
                x = padding
            else:
                x = padding + i * (width - padding * 2) / (len(events) - 1)
            xs.append(x)
        all_vals = []
        for ev in events:
            for w in ev.get("strategy_weights", []) or []:
                try:
                    all_vals.append(float(w.get("weight", 0.0)))
                except Exception:
                    pass
        lo = min(all_vals) if all_vals else 0.0
        hi = max(all_vals) if all_vals else 1.0
        if hi - lo < 1e-9:
            hi = lo + 1.0

        def y_for(v: float) -> float:
            t = (v - lo) / (hi - lo)
            return height - padding - t * (height - padding * 2)

        for idx, name in enumerate(names):
            color = self._auto_color(idx, len(names))
            points = []
            for i, ev in enumerate(events):
                w_list = ev.get("strategy_weights", []) or []
                val = None
                for w in w_list:
                    if str(w.get("name")) == name:
                        try:
                            val = float(w.get("weight", 0.0))
                        except Exception:
                            val = 0.0
                        break
                if val is None:
                    val = 0.0
                points.append((xs[i], y_for(val)))
            for i in range(len(points) - 1):
                self.switch_canvas.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1], fill=color, width=2)
            last_x, last_y = points[-1]
            self.switch_canvas.create_text(last_x + 6, last_y, anchor="w", text=name, fill=color)
