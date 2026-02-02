from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk


class CatalogView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._build()

    def _build(self) -> None:
        ttk.Label(self.tab, text="Catalog Search", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(self.tab, text="Type keywords to search components/examples.", foreground="#666").pack(anchor="w")
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
        ttk.Label(kind_row, text="Match").pack(side="left", padx=(6, 0))
        self.catalog_match_var = tk.StringVar(value="all")
        self.catalog_match_combo = ttk.Combobox(
            kind_row,
            textvariable=self.catalog_match_var,
            state="readonly",
            width=10,
            values=("all", "name", "tag"),
        )
        self.catalog_match_combo.pack(side="left", padx=(6, 6))
        self.catalog_match_combo.bind("<<ComboboxSelected>>", lambda _e: self.search())
        self.catalog_query_var = tk.StringVar()
        self.catalog_entry = ttk.Entry(search_row, textvariable=self.catalog_query_var)
        self.catalog_entry.pack(side="left", fill="x", expand=True)
        self.catalog_entry.bind("<Return>", lambda _e: self.search())
        ttk.Button(search_row, text="Search", command=self.search).pack(side="left", padx=(6, 0))

        self.catalog_result_tree = ttk.Treeview(
            self.tab,
            columns=("key", "kind", "title"),
            show="headings",
            height=10,
        )
        self.catalog_result_tree.heading("key", text="key")
        self.catalog_result_tree.heading("kind", text="kind")
        self.catalog_result_tree.heading("title", text="title")
        self.catalog_result_tree.column("key", width=220, anchor="w")
        self.catalog_result_tree.column("kind", width=90, anchor="w")
        self.catalog_result_tree.column("title", width=160, anchor="w")
        self.catalog_result_tree.pack(fill="both", expand=True, pady=(0, 6))
        self.catalog_result_tree.bind("<<TreeviewSelect>>", self.on_select)

        ttk.Label(self.tab, text="Summary", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.catalog_summary = tk.Text(self.tab, height=8, wrap="word", borderwidth=1, relief="solid")
        self.catalog_summary.pack(fill="both", expand=False, pady=(4, 6))
        self.catalog_summary.insert("1.0", "Search results will appear above.")
        self.catalog_summary.config(state="disabled")

    def load_catalog(self) -> Dict[str, Dict[str, Any]]:
        try:
            import sys
            from pathlib import Path
            ROOT = Path(__file__).resolve().parents[2]
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from nsgablack.catalog import get_catalog
        except Exception:
            return {}

        cat = get_catalog()
        self.app._catalog_obj = cat
        out = {}
        for e in cat.list():
            out[e.key] = {
                "key": e.key,
                "kind": e.kind,
                "title": e.title,
                "summary": e.summary,
                "tags": list(e.tags),
                "companions": list(e.companions),
            }
        return out

    def search(self) -> None:
        query = self.catalog_query_var.get().strip()
        self.catalog_result_tree.delete(*self.catalog_result_tree.get_children())

        results: List[Dict[str, Any]] = []
        kind_filter = self.catalog_kind_var.get().strip().lower()
        match_filter = self.catalog_match_var.get().strip().lower()
        if self.app._catalog_obj is not None:
            try:
                kinds = None if (not kind_filter or kind_filter == "all") else [kind_filter]
                entries = self.app._catalog_obj.search(query, kinds=kinds, fields=match_filter, limit=50)
                for e in entries:
                    results.append(
                        {
                            "key": e.key,
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
                else:
                    text = " ".join(
                        [
                            str(info.get("key", "")),
                            str(info.get("kind", "")),
                            str(info.get("title", "")),
                            str(info.get("summary", "")),
                        ]
                    ).lower()
                if query.lower() in text:
                    hay.append(info)
            results = hay

        for info in results:
            self.catalog_result_tree.insert(
                "",
                "end",
                values=(info.get("key", ""), info.get("kind", ""), info.get("title", "")),
            )

        self._set_summary(f"Results: {len(results)}")

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
                    info = {
                        "key": entry.key,
                        "kind": entry.kind,
                        "title": entry.title,
                        "summary": entry.summary,
                        "companions": list(entry.companions),
                    }
        summary = info.get("summary", "")
        companions = info.get("companions") or []
        extra = ""
        if companions:
            extra = "\n\ncompanions:\n- " + "\n- ".join(companions)
        self._set_summary(f"{summary}{extra}")

    def _set_summary(self, text: str) -> None:
        self.catalog_summary.config(state="normal")
        self.catalog_summary.delete("1.0", "end")
        self.catalog_summary.insert("1.0", text)
        self.catalog_summary.config(state="disabled")

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
