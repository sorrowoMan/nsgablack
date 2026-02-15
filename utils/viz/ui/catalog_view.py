from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk


def scope_from_key(key: str) -> str:
    return "project" if str(key).startswith("project.") else "framework"


class CatalogView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Catalog Search", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            self.tab,
            text="Type keywords to search components/examples (e.g. vns, context_requires, visualization prior).",
            foreground="#666",
        ).pack(anchor="w")
        search_row = ttk.Frame(self.tab)
        search_row.pack(fill="x", pady=(6, 6))
        kind_row = ttk.Frame(self.tab)
        kind_row.pack(fill="x", pady=(0, 6))
        ttk.Label(kind_row, text="Kind").pack(side="left")
        self.catalog_kind_var = tk.StringVar(value="all")
        self.catalog_kind_combo = ttk.Combobox(
            kind_row,
            textvariable=self.catalog_kind_var,
            state="readonly",
            width=18,
            values=("all", "suite", "adapter", "plugin", "bias", "representation", "tool", "example"),
        )
        self.catalog_kind_combo.pack(side="left", padx=(6, 6))
        self.catalog_kind_combo.bind("<<ComboboxSelected>>", lambda _e: self.search())
        ttk.Label(kind_row, text="Scope").pack(side="left")
        self.catalog_scope_var = tk.StringVar(value="all")
        self.catalog_scope_combo = ttk.Combobox(
            kind_row,
            textvariable=self.catalog_scope_var,
            state="readonly",
            width=12,
            values=("all", "project", "framework"),
        )
        self.catalog_scope_combo.pack(side="left", padx=(6, 6))
        self.catalog_scope_combo.bind("<<ComboboxSelected>>", lambda _e: self.search())
        ttk.Label(kind_row, text="Match").pack(side="left", padx=(6, 0))
        self.catalog_match_var = tk.StringVar(value="all")
        self.catalog_match_combo = ttk.Combobox(
            kind_row,
            textvariable=self.catalog_match_var,
            state="readonly",
            width=10,
            values=("all", "name", "tag", "context", "usage"),
        )
        self.catalog_match_combo.pack(side="left", padx=(6, 6))
        self.catalog_match_combo.bind("<<ComboboxSelected>>", lambda _e: self.search())
        self.catalog_query_var = tk.StringVar()
        self.catalog_entry = ttk.Entry(search_row, textvariable=self.catalog_query_var)
        self.catalog_entry.pack(side="left", fill="x", expand=True)
        self.catalog_entry.bind("<Return>", lambda _e: self.search())
        ttk.Button(search_row, text="Search", command=self.search).pack(side="left", padx=(6, 0))
        ttk.Button(search_row, text="Preset: Context", command=lambda: self._apply_preset("context_requires", "context")).pack(side="left", padx=(6, 0))
        ttk.Button(search_row, text="Preset: Viz Prior", command=lambda: self._apply_preset("visualization prior", "all")).pack(side="left", padx=(6, 0))

        self.catalog_result_tree = ttk.Treeview(
            self.tab,
            columns=("key", "scope", "kind", "title"),
            show="headings",
            height=10,
        )
        self.catalog_result_tree.heading("key", text="key")
        self.catalog_result_tree.heading("scope", text="scope")
        self.catalog_result_tree.heading("kind", text="kind")
        self.catalog_result_tree.heading("title", text="title")
        self.catalog_result_tree.column("key", width=210, anchor="w")
        self.catalog_result_tree.column("scope", width=90, anchor="w")
        self.catalog_result_tree.column("kind", width=90, anchor="w")
        self.catalog_result_tree.column("title", width=160, anchor="w")
        self.catalog_result_tree.pack(fill="both", expand=True, pady=(0, 6))
        self.catalog_result_tree.bind("<<TreeviewSelect>>", self.on_select)

        self.catalog_status_var = tk.StringVar(value="Results: 0")
        ttk.Label(self.tab, textvariable=self.catalog_status_var, foreground="#666").pack(anchor="w", pady=(0, 4))

        self._section_meta = (
            ("summary", "Summary"),
            ("usage", "How to Use"),
            ("contract", "Context Contract"),
            ("companions", "Companions"),
            ("example", "Example"),
        )
        self.detail_notebook = ttk.Notebook(self.tab)
        self.detail_notebook.pack(fill="x", pady=(0, 6))
        self._detail_texts: Dict[str, tk.Text] = {}
        for key, label in self._section_meta:
            section_frame = ttk.Frame(self.detail_notebook)
            self.detail_notebook.add(section_frame, text=label)
            text = tk.Text(section_frame, height=10, wrap="word", borderwidth=1, relief="solid")
            text.pack(fill="both", expand=True, padx=4, pady=4)
            text.config(state="disabled")
            self._detail_texts[key] = text
        self._clear_cards()

    def _set_detail_text(self, section_key: str, text: str) -> None:
        widget = self._detail_texts.get(section_key)
        if widget is None:
            return
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text if text.strip() else "(none)")
        widget.config(state="disabled")

    def _clear_cards(self) -> None:
        sections = {
            "summary": "Select one entry to view details.",
            "usage": "(none)",
            "contract": "(none)",
            "companions": "(none)",
            "example": "(none)",
        }
        for key, value in sections.items():
            self._set_detail_text(key, value)
        self._select_detail_tab("summary")

    def _select_detail_tab(self, section_key: str) -> None:
        keys = [key for key, _label in self._section_meta]
        try:
            idx = keys.index(section_key)
        except ValueError:
            idx = 0
        self.detail_notebook.select(idx)

    def load_catalog(self) -> Dict[str, Dict[str, Any]]:
        try:
            import sys

            ROOT = Path(__file__).resolve().parents[2]
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from nsgablack.catalog import build_usage_profile, get_catalog
            from nsgablack.project.catalog import load_project_catalog
        except Exception:
            return {}

        cat = None
        project_root = self._detect_project_root()
        if project_root is not None:
            try:
                cat = load_project_catalog(project_root, include_global=True)
            except Exception:
                cat = None
        if cat is None:
            cat = get_catalog()

        self.app._catalog_obj = cat
        out = {}
        for e in cat.list():
            scope = scope_from_key(e.key)
            usage = build_usage_profile(e)
            out[e.key] = {
                "key": e.key,
                "scope": scope,
                "kind": e.kind,
                "title": e.title,
                "summary": e.summary,
                "tags": list(e.tags),
                "companions": list(e.companions),
                "context_requires": list(getattr(e, "context_requires", ()) or ()),
                "context_provides": list(getattr(e, "context_provides", ()) or ()),
                "context_mutates": list(getattr(e, "context_mutates", ()) or ()),
                "context_cache": list(getattr(e, "context_cache", ()) or ()),
                "context_notes": list(getattr(e, "context_notes", ()) or ()),
                "use_when": list(usage.use_when),
                "minimal_wiring": list(usage.minimal_wiring),
                "required_companions": list(usage.required_companions),
                "config_keys": list(usage.config_keys),
                "example_entry": usage.example_entry,
            }
        return out

    def search(self) -> None:
        query = self.catalog_query_var.get().strip()
        self.catalog_result_tree.delete(*self.catalog_result_tree.get_children())

        results: List[Dict[str, Any]] = []
        kind_filter = self.catalog_kind_var.get().strip().lower()
        scope_filter = self.catalog_scope_var.get().strip().lower()
        match_filter = self.catalog_match_var.get().strip().lower()
        if self.app._catalog_obj is not None:
            try:
                kinds = None if (not kind_filter or kind_filter == "all") else [kind_filter]
                entries = self.app._catalog_obj.search(query, kinds=kinds, fields=match_filter, limit=50)
                for e in entries:
                    scope = scope_from_key(e.key)
                    if scope_filter != "all" and scope != scope_filter:
                        continue
                    results.append(
                        {
                            "key": e.key,
                            "scope": scope,
                            "kind": e.kind,
                            "title": e.title,
                            "summary": e.summary,
                            "companions": list(e.companions),
                            "tags": list(e.tags),
                        }
                    )
            except Exception:
                results = []
        else:
            hay = []
            for info in self.app.catalog.values():
                if match_filter == "name":
                    text = " ".join(
                        [
                            str(info.get("key", "")),
                            str(info.get("title", "")),
                        ]
                    ).lower()
                elif match_filter == "tag":
                    text = " ".join(info.get("tags", []) or []).lower()
                elif match_filter == "context":
                    text = " ".join(
                        [
                            " ".join(info.get("context_requires", []) or []),
                            " ".join(info.get("context_provides", []) or []),
                            " ".join(info.get("context_mutates", []) or []),
                            " ".join(info.get("context_cache", []) or []),
                            " ".join(info.get("context_notes", []) or []),
                        ]
                    ).lower()
                elif match_filter == "usage":
                    text = " ".join(
                        [
                            " ".join(info.get("use_when", []) or []),
                            " ".join(info.get("minimal_wiring", []) or []),
                            " ".join(info.get("required_companions", []) or []),
                            " ".join(info.get("config_keys", []) or []),
                            str(info.get("example_entry", "")),
                        ]
                    ).lower()
                else:
                    text = " ".join(
                        [
                            str(info.get("key", "")),
                            str(info.get("kind", "")),
                            str(info.get("title", "")),
                            str(info.get("summary", "")),
                            " ".join(info.get("use_when", []) or []),
                            " ".join(info.get("minimal_wiring", []) or []),
                        ]
                    ).lower()
                if query.lower() in text:
                    scope = str(info.get("scope", "framework")).strip().lower()
                    if scope_filter != "all" and scope != scope_filter:
                        continue
                    hay.append(info)
            results = hay

        for info in results:
            self.catalog_result_tree.insert(
                "",
                "end",
                values=(
                    info.get("key", ""),
                    info.get("scope", scope_from_key(str(info.get("key", "")))),
                    info.get("kind", ""),
                    info.get("title", ""),
                ),
            )

        self.catalog_status_var.set(f"Results: {len(results)}")
        self._clear_cards()

    def on_select(self, _event: Any) -> None:
        sel = self.catalog_result_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        values = self.catalog_result_tree.item(item_id, "values")
        key = values[0] if values else ""
        info = self.app.catalog.get(str(key), {})
        if not info:
            if self.app._catalog_obj is not None:
                entry = self.app._catalog_obj.get(str(key))
                if entry is not None:
                    from nsgablack.catalog import build_usage_profile

                    usage = build_usage_profile(entry)
                    info = {
                        "key": entry.key,
                        "scope": scope_from_key(entry.key),
                        "kind": entry.kind,
                        "title": entry.title,
                        "summary": entry.summary,
                        "companions": list(entry.companions),
                        "context_requires": list(getattr(entry, "context_requires", ()) or ()),
                        "context_provides": list(getattr(entry, "context_provides", ()) or ()),
                        "context_mutates": list(getattr(entry, "context_mutates", ()) or ()),
                        "context_cache": list(getattr(entry, "context_cache", ()) or ()),
                        "context_notes": list(getattr(entry, "context_notes", ()) or ()),
                        "use_when": list(usage.use_when),
                        "minimal_wiring": list(usage.minimal_wiring),
                        "required_companions": list(usage.required_companions),
                        "config_keys": list(usage.config_keys),
                        "example_entry": usage.example_entry,
                    }
        summary = str(info.get("summary", "") or "")
        companions = info.get("companions") or []
        contracts = self._format_contracts(info)
        usage = self._format_usage(info)
        scope = str(info.get("scope", scope_from_key(str(key))))
        kind = str(info.get("kind", "") or "")

        summary_card = f"key: {key}\nscope: {scope}\nkind: {kind}\n\n{summary}".strip()
        companions_card = "\n".join(f"- {c}" for c in companions) if companions else "(none)"
        example_entry = str(info.get("example_entry", "") or "").strip()

        self._set_detail_text("summary", summary_card)
        self._set_detail_text("usage", usage)
        self._set_detail_text("contract", contracts)
        self._set_detail_text("companions", companions_card)
        self._set_detail_text("example", example_entry or "(none)")
        self._select_detail_tab("summary")

    def key_for_plugin(self, plugin_name: str) -> Optional[str]:
        if not self.app.catalog:
            return None
        target = str(plugin_name).strip().lower()
        for key, info in self.app.catalog.items():
            if info.get("kind") != "plugin":
                continue
            suffix = key.split(".", 1)[-1].strip().lower()
            if suffix == target:
                return key
        return None

    def key_for_bias(self, bias_name: str) -> Optional[str]:
        if not self.app.catalog:
            return None
        target = str(bias_name).strip().lower()
        for key, info in self.app.catalog.items():
            if info.get("kind") != "bias":
                continue
            suffix = key.split(".", 1)[-1].strip().lower()
            if suffix == target:
                return key
        return None

    def _apply_preset(self, query: str, match_field: str) -> None:
        self.catalog_query_var.set(query)
        if match_field in ("all", "name", "tag", "context", "usage"):
            self.catalog_match_var.set(match_field)
        self.search()

    def _format_contracts(self, info: Dict[str, Any]) -> str:
        rows = []
        for field in (
            "context_requires",
            "context_provides",
            "context_mutates",
            "context_cache",
            "context_notes",
        ):
            values = info.get(field) or []
            clean = [str(v).strip() for v in values if str(v).strip()]
            if clean:
                rows.append(f"{field}:\n- " + "\n- ".join(clean))
            else:
                rows.append(f"{field}:\n- (none)")
        return "\n\n".join(rows)

    def _format_usage(self, info: Dict[str, Any]) -> str:
        rows: List[str] = []
        for field in ("use_when", "minimal_wiring", "required_companions", "config_keys"):
            values = info.get(field) or []
            clean = [str(v).strip() for v in values if str(v).strip()]
            if clean:
                rows.append(f"{field}:\n- " + "\n- ".join(clean))
        example_entry = str(info.get("example_entry", "") or "").strip()
        if example_entry:
            rows.append(f"example_entry:\n- {example_entry}")
        return "\n\n".join(rows) if rows else "(none)"

    def _detect_project_root(self) -> Optional[Path]:
        workspace = getattr(self.app, "workspace", None)
        if workspace is not None:
            wp = Path(workspace)
            for cand in [wp] + list(wp.parents):
                if (cand / "project_registry.py").is_file():
                    return cand

        entry = getattr(self.app, "entry", "") or ""
        entry_path = entry.rsplit(":", 1)[0].strip()
        if not entry_path:
            return None

        target = Path(entry_path)
        if not target.is_absolute():
            target = Path.cwd() / target
        if not target.exists():
            return None
        start = target.parent if target.is_file() else target

        cur = start
        for cand in [cur] + list(cur.parents):
            if (cand / "project_registry.py").is_file():
                return cand
        return None
