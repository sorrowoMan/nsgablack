from pathlib import Path
import re
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def scope_from_key(key: str) -> str:
    return "project" if str(key).startswith("project.") else "framework"


def context_role_match(info: Dict[str, Any], context_key: str, role: str) -> bool:
    """Check whether one catalog entry matches a context role query."""
    key = str(context_key or "").strip().lower()
    if not key:
        return False

    requires = [str(v).strip().lower() for v in (info.get("context_requires") or []) if str(v).strip()]
    provides = [str(v).strip().lower() for v in (info.get("context_provides") or []) if str(v).strip()]
    mutates = [str(v).strip().lower() for v in (info.get("context_mutates") or []) if str(v).strip()]

    role_key = str(role or "").strip().lower()
    if role_key == "requires":
        hay = requires
    elif role_key == "providers":
        # Treat mutates as provider-side operations in context flow.
        hay = provides + mutates
    else:
        hay = requires + provides + mutates

    if key in hay:
        return True
    return any(key in item for item in hay)


class CatalogView:
    def __init__(self, app: Any, tab: ttk.Frame) -> None:
        self.app = app
        self.tab = tab
        self._project_catalog_by_key: Dict[str, Path] = {}
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
            values=("all", "suite", "adapter", "plugin", "bias", "representation", "tool", "example", "doc"),
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
        actions_row = ttk.Frame(self.tab)
        actions_row.pack(fill="x", pady=(0, 6))
        self.delete_entry_btn = ttk.Button(
            actions_row,
            text="Delete Project Entry",
            command=self._delete_selected_project_entry,
            state="disabled",
        )
        self.delete_entry_btn.pack(side="left")

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
        if hasattr(self, "delete_entry_btn"):
            self.delete_entry_btn.configure(state="disabled")

    def _select_detail_tab(self, section_key: str) -> None:
        keys = [key for key, _label in self._section_meta]
        try:
            idx = keys.index(section_key)
        except ValueError:
            idx = 0
        self.detail_notebook.select(idx)

    def load_catalog(self, *, override_project_root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
        try:
            import sys

            ROOT = Path(__file__).resolve().parents[2]
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from nsgablack.catalog import build_usage_profile, get_catalog
            from nsgablack.catalog.registry import Catalog
            from nsgablack.project.catalog import load_project_catalog
        except Exception:
            return {}

        cat = None
        # Always refresh global registry cache before building UI catalog view.
        try:
            global_cat = get_catalog(refresh=True)
        except Exception:
            global_cat = None

        merged_entries = []
        project_catalog_by_key: Dict[str, Path] = {}
        if global_cat is not None:
            merged_entries.extend(global_cat.list())

        project_roots: list[Path] = []
        project_root = override_project_root if override_project_root is not None else self._detect_project_root()
        if project_root is not None:
            project_roots.append(project_root)

        # If UI is opened from framework root, also discover scaffold projects under workspace.
        workspace = getattr(self.app, "workspace", None)
        if workspace:
            ws = Path(workspace)
            try:
                for child in ws.iterdir():
                    if not child.is_dir():
                        continue
                    if (child / "project_registry.py").is_file() and (child / "build_solver.py").is_file():
                        if child not in project_roots:
                            project_roots.append(child)
            except Exception:
                pass

        for root in project_roots:
            try:
                pcat = load_project_catalog(root, include_global=False)
                project_entries = pcat.list()
                merged_entries.extend(project_entries)
                project_catalog_file = root / "catalog" / "entries.toml"
                for pe in project_entries:
                    project_catalog_by_key[pe.key] = project_catalog_file
            except Exception:
                continue

        if merged_entries:
            # last-write-wins by key
            dedup = {}
            for e in merged_entries:
                dedup[e.key] = e
            cat = Catalog(list(dedup.values()))
        else:
            cat = get_catalog(refresh=True)

        self.app._catalog_obj = cat
        self._project_catalog_by_key = project_catalog_by_key
        out = {}
        for e in cat.list():
            scope = scope_from_key(e.key)
            usage = build_usage_profile(e)
            out[e.key] = {
                "key": e.key,
                "scope": scope,
                "kind": e.kind,
                "title": e.title,
                "import_path": e.import_path,
                "summary": e.summary,
                "project_catalog_file": str(self._project_catalog_by_key.get(e.key, "")),
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

    def _default_catalog_file(self) -> Path:
        workspace = getattr(self.app, "workspace", None)
        if workspace:
            wp = Path(workspace)
            cand = wp / "catalog" / "entries.toml"
            if cand.exists():
                return cand
        here = Path(__file__).resolve()
        # nsgablack/utils/viz/ui -> nsgablack root
        root = here.parents[3]
        return root / "catalog" / "entries.toml"

    def open_register_dialog(self) -> None:
        dialog = tk.Toplevel(self.tab)
        dialog.title("Catalog Entry Registration")
        dialog.geometry("560x520")
        dialog.transient(self.tab.winfo_toplevel())
        dialog.grab_set()

        context_fields = (
            "context_requires",
            "context_provides",
            "context_mutates",
            "context_cache",
            "context_notes",
        )
        vars_map = {
            "file": tk.StringVar(value=str(self._default_catalog_file())),
            "source_file": tk.StringVar(value=""),
            "source_symbol": tk.StringVar(value=""),
            "key": tk.StringVar(value=""),
            "title": tk.StringVar(value=""),
            "kind": tk.StringVar(value="bias"),
            "import_path": tk.StringVar(value=""),
            "summary": tk.StringVar(value=""),
            "tags": tk.StringVar(value=""),
            "companions": tk.StringVar(value=""),
            "use_when": tk.StringVar(value=""),
            "minimal_wiring": tk.StringVar(value=""),
            "required_companions": tk.StringVar(value=""),
            "config_keys": tk.StringVar(value=""),
            "example_entry": tk.StringVar(value=""),
            "context_requires": tk.StringVar(value=""),
            "context_provides": tk.StringVar(value=""),
            "context_mutates": tk.StringVar(value=""),
            "context_cache": tk.StringVar(value=""),
            "context_notes": tk.StringVar(value=""),
        }
        symbol_kind_map: Dict[str, str] = {}
        symbol_display_map: Dict[str, str] = {}
        write_code_on_save_var = tk.BooleanVar(value=True)
        allow_replace_var = tk.BooleanVar(value=False)

        form_notebook = ttk.Notebook(dialog)
        form_notebook.pack(fill="both", expand=True, padx=10, pady=(8, 6))
        source_tab = ttk.Frame(form_notebook)
        identity_tab = ttk.Frame(form_notebook)
        usage_tab = ttk.Frame(form_notebook)
        contract_tab = ttk.Frame(form_notebook)
        form_notebook.add(source_tab, text="Source")
        form_notebook.add(identity_tab, text="Identity")
        form_notebook.add(usage_tab, text="Usage")
        form_notebook.add(contract_tab, text="Context Contract")

        def _add_row(parent: ttk.Frame, label: str, key: str, *, width: int = 78) -> None:
            row = ttk.Frame(parent)
            row.pack(fill="x", padx=10, pady=3)
            ttk.Label(row, text=label, width=18).pack(side="left")
            ttk.Entry(row, textvariable=vars_map[key], width=width).pack(side="left", fill="x", expand=True)

        file_row = ttk.Frame(source_tab)
        file_row.pack(fill="x", padx=10, pady=3)
        ttk.Label(file_row, text="Catalog file", width=18).pack(side="left")
        ttk.Entry(file_row, textvariable=vars_map["file"], width=66).pack(side="left", fill="x", expand=True)

        def _browse_file() -> None:
            chosen = filedialog.asksaveasfilename(
                title="Select catalog entries TOML",
                initialfile="entries.toml",
                defaultextension=".toml",
                filetypes=[("TOML", "*.toml"), ("All files", "*.*")],
                initialdir=str(Path(vars_map["file"].get()).parent),
            )
            if chosen:
                vars_map["file"].set(chosen)

        ttk.Button(file_row, text="Browse", command=_browse_file).pack(side="left", padx=(6, 0))

        source_row = ttk.Frame(source_tab)
        source_row.pack(fill="x", padx=10, pady=3)
        ttk.Label(source_row, text="Source file", width=18).pack(side="left")
        ttk.Entry(source_row, textvariable=vars_map["source_file"], width=66).pack(side="left", fill="x", expand=True)

        def _browse_source_file() -> None:
            chosen = filedialog.askopenfilename(
                title="Select Python source file",
                filetypes=[("Python", "*.py"), ("All files", "*.*")],
                initialdir=str(self._detect_project_root() or Path.cwd()),
            )
            if chosen:
                vars_map["source_file"].set(chosen)
                _scan_symbols()

        ttk.Button(source_row, text="Browse", command=_browse_source_file).pack(side="left", padx=(6, 0))

        symbol_row = ttk.Frame(source_tab)
        symbol_row.pack(fill="x", padx=10, pady=3)
        ttk.Label(symbol_row, text="Component", width=18).pack(side="left")
        marked_only_var = tk.BooleanVar(value=True)
        symbol_combo = ttk.Combobox(
            symbol_row,
            textvariable=vars_map["source_symbol"],
            width=32,
            state="readonly",
            values=(),
        )
        symbol_combo.pack(side="left", padx=(0, 6))
        ttk.Checkbutton(symbol_row, text="Marked only", variable=marked_only_var).pack(side="left", padx=(0, 6))
        ttk.Label(
            source_tab,
            text="Marked = class decorated with @component(...) / @catalog_component(...) / @nsgablack_component(...).",
            foreground="#666",
        ).pack(anchor="w", padx=10, pady=(0, 4))

        def _scan_symbols() -> None:
            nonlocal symbol_kind_map, symbol_display_map
            path_text = vars_map["source_file"].get().strip()
            if not path_text:
                return
            try:
                from nsgablack.catalog.source_sync import list_source_symbols

                symbols = list_source_symbols(Path(path_text), marked_only=bool(marked_only_var.get()))
            except Exception as exc:
                messagebox.showerror("Scan failed", f"Cannot read symbols:\n{exc}", parent=dialog)
                return
            names = [f"{s.name} [marked]" if getattr(s, "marked", False) else s.name for s in symbols]
            symbol_kind_map = {s.name: s.kind for s in symbols}
            symbol_display_map = {
                (f"{s.name} [marked]" if getattr(s, "marked", False) else s.name): s.name
                for s in symbols
            }
            symbol_combo["values"] = names
            current = vars_map["source_symbol"].get().strip()
            if current in symbol_display_map:
                vars_map["source_symbol"].set(current)
            elif names:
                vars_map["source_symbol"].set(names[0])
            if not names:
                vars_map["source_symbol"].set("")

        ttk.Button(symbol_row, text="Scan", command=_scan_symbols).pack(side="left")

        def _to_values(raw: str) -> list[str]:
            vals = []
            for part in str(raw or "").split(","):
                t = part.strip()
                if t:
                    vals.append(t)
            return vals

        def _infer_key(symbol: str, kind: str, source_file: str = "") -> str:
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", str(symbol or "").strip()).lower()
            if kind == "adapter" and snake.endswith("_adapter"):
                snake = snake[: -len("_adapter")]
            elif kind == "bias" and snake.endswith("_bias"):
                snake = snake[: -len("_bias")]
            elif kind == "plugin" and snake.endswith("_plugin"):
                snake = snake[: -len("_plugin")]
            base = f"{kind}.{snake.strip('_') or 'component'}"
            project_root = self._detect_project_root()
            if not project_root or not source_file or not self._is_scaffold_project_root(project_root):
                return base
            try:
                src = Path(source_file).resolve()
                src.relative_to(project_root.resolve())
            except Exception:
                return base
            if not base.startswith("project."):
                return f"project.{base}"
            return base

        def _infer_import_path(source_file: str, symbol: str) -> str:
            source_path = Path(source_file).resolve()
            roots: list[Path] = []
            workspace = getattr(self.app, "workspace", None)
            if workspace:
                roots.append(Path(workspace).resolve())
            roots.append(Path.cwd().resolve())
            for root in roots:
                try:
                    rel = source_path.relative_to(root)
                except ValueError:
                    continue
                module_path = rel.parent if rel.name == "__init__.py" else rel.with_suffix("")
                parts = [p for p in module_path.parts if p and p != "."]
                if parts and parts[0] == "src":
                    parts = parts[1:]
                module = ".".join(parts)
                if module:
                    return f"{module}:{symbol}"
            return f"{source_path.stem}:{symbol}"

        def _load_from_code() -> None:
            source_file = vars_map["source_file"].get().strip()
            symbol = symbol_display_map.get(vars_map["source_symbol"].get().strip(), vars_map["source_symbol"].get().strip())
            if not source_file or not symbol:
                messagebox.showwarning("Missing source", "Please select source file and component.", parent=dialog)
                return
            try:
                from nsgablack.catalog.source_sync import read_symbol_contract

                contract = read_symbol_contract(Path(source_file), symbol)
            except Exception as exc:
                messagebox.showerror("Load failed", f"Cannot read component contract:\n{exc}", parent=dialog)
                return
            kind = symbol_kind_map.get(symbol, vars_map["kind"].get().strip())
            if kind in {"adapter", "bias", "plugin", "representation", "suite", "tool", "example", "doc"}:
                vars_map["kind"].set(kind)
            if not vars_map["key"].get().strip():
                vars_map["key"].set(_infer_key(symbol, vars_map["kind"].get().strip() or "tool", source_file))
            if not vars_map["title"].get().strip():
                vars_map["title"].set(symbol)
            vars_map["import_path"].set(_infer_import_path(source_file, symbol))
            if not vars_map["summary"].get().strip():
                vars_map["summary"].set(f"{vars_map['kind'].get().strip().capitalize()} component: {symbol}.")
            for field in context_fields:
                vars_map[field].set(", ".join(contract.get(field, ())))

        ttk.Button(symbol_row, text="Load From Code", command=_load_from_code).pack(side="left", padx=(6, 0))

        def _refresh_from_code() -> None:
            _scan_symbols()
            source_file = vars_map["source_file"].get().strip()
            symbol = symbol_display_map.get(
                vars_map["source_symbol"].get().strip(),
                vars_map["source_symbol"].get().strip(),
            )
            if source_file and symbol:
                _load_from_code()

        ttk.Button(symbol_row, text="Refresh", command=_refresh_from_code).pack(side="left", padx=(6, 0))

        def _apply_to_code() -> None:
            source_file = vars_map["source_file"].get().strip()
            symbol = symbol_display_map.get(vars_map["source_symbol"].get().strip(), vars_map["source_symbol"].get().strip())
            if not source_file or not symbol:
                messagebox.showwarning("Missing source", "Please select source file and component.", parent=dialog)
                return
            try:
                from nsgablack.catalog.source_sync import apply_symbol_contract

                contract_payload = {field: _to_values(vars_map[field].get()) for field in context_fields}
                apply_symbol_contract(Path(source_file), symbol, contract_payload)
            except Exception as exc:
                messagebox.showerror("Apply failed", f"Cannot write contract to code:\n{exc}", parent=dialog)
                return
            messagebox.showinfo("Saved", f"Updated context contract in source:\n{source_file}", parent=dialog)

        ttk.Button(symbol_row, text="Apply Contract To Code", command=_apply_to_code).pack(side="left", padx=(6, 0))

        _add_row(identity_tab, "key", "key")
        _add_row(identity_tab, "title", "title")

        kind_row = ttk.Frame(identity_tab)
        kind_row.pack(fill="x", padx=10, pady=3)
        ttk.Label(kind_row, text="kind", width=18).pack(side="left")
        kind_combo = ttk.Combobox(
            kind_row,
            textvariable=vars_map["kind"],
            state="readonly",
            width=22,
            values=("adapter", "bias", "plugin", "representation", "suite", "tool", "example", "doc"),
        )
        kind_combo.pack(side="left", padx=(0, 6))
        _add_row(identity_tab, "import_path", "import_path")
        _add_row(identity_tab, "summary", "summary")

        _add_row(usage_tab, "tags (csv)", "tags")
        _add_row(usage_tab, "companions (csv)", "companions")
        _add_row(usage_tab, "use_when (csv)", "use_when")
        _add_row(usage_tab, "minimal_wiring (csv)", "minimal_wiring")
        _add_row(usage_tab, "required_companions (csv)", "required_companions")
        _add_row(usage_tab, "config_keys (csv)", "config_keys")
        _add_row(usage_tab, "example_entry", "example_entry")

        _add_row(contract_tab, "context_requires", "context_requires")
        _add_row(contract_tab, "context_provides", "context_provides")
        _add_row(contract_tab, "context_mutates", "context_mutates")
        _add_row(contract_tab, "context_cache", "context_cache")
        _add_row(contract_tab, "context_notes", "context_notes")

        hint = (
            "Use Source file + Component to auto-fill key/kind/import_path/context contracts.\n"
            "Then edit and save. Required: key/title/kind/import_path/summary."
        )
        ttk.Label(dialog, text=hint, foreground="#666", justify="left").pack(anchor="w", padx=10, pady=(6, 0))
        ttk.Checkbutton(
            contract_tab,
            text="On Save also write context contract back to source code",
            variable=write_code_on_save_var,
        ).pack(anchor="w", padx=10, pady=(4, 8))
        ttk.Checkbutton(
            contract_tab,
            text="Allow replace when key conflicts",
            variable=allow_replace_var,
        ).pack(anchor="w", padx=10, pady=(0, 8))

        actions = ttk.Frame(dialog)
        actions.pack(fill="x", padx=10, pady=10)

        def _save() -> None:
            try:
                from nsgablack.catalog.quick_add import build_entry_payload, upsert_catalog_entry
            except Exception as exc:
                messagebox.showerror("Catalog add failed", f"Cannot import quick add module:\n{exc}", parent=dialog)
                return

            source_file = vars_map["source_file"].get().strip()
            symbol = symbol_display_map.get(vars_map["source_symbol"].get().strip(), vars_map["source_symbol"].get().strip())

            key = vars_map["key"].get().strip()
            title = vars_map["title"].get().strip()
            kind = vars_map["kind"].get().strip()
            import_path = vars_map["import_path"].get().strip()
            summary = vars_map["summary"].get().strip()
            target_file = Path(vars_map["file"].get().strip())

            project_catalog = self._project_catalog_file()
            framework_catalog = self._default_catalog_file()

            # If source belongs to a scaffold project, prefer writing to that project's catalog.
            source_project_root: Optional[Path] = None
            if source_file:
                src_path = Path(source_file)
                if src_path.exists():
                    for cand in [src_path.parent] + list(src_path.parent.parents):
                        if self._is_scaffold_project_root(cand):
                            source_project_root = cand
                            break
            if source_project_root is not None:
                source_project_catalog = source_project_root / "catalog" / "entries.toml"
                try:
                    target_is_framework = target_file.resolve() == framework_catalog.resolve()
                except Exception:
                    target_is_framework = False
                if target_is_framework:
                    target_file = source_project_catalog
                    vars_map["file"].set(str(source_project_catalog))

            if project_catalog is not None:
                try:
                    is_project_catalog = target_file.resolve() == project_catalog.resolve()
                except Exception:
                    is_project_catalog = False
                if (
                    is_project_catalog
                    and key
                    and not key.startswith("project.")
                    and self._is_scaffold_project_root(project_catalog.parent.parent)
                ):
                    key = f"project.{key}"
                    vars_map["key"].set(key)
            elif source_project_root is not None and key and not key.startswith("project."):
                key = f"project.{key}"
                vars_map["key"].set(key)

            if not key or not title or not kind or not import_path or not summary:
                messagebox.showwarning(
                    "Missing fields",
                    "Required: key/title/kind/import_path/summary",
                    parent=dialog,
                )
                return
            if ":" not in import_path:
                messagebox.showwarning(
                    "Invalid import_path",
                    "import_path must be like pkg.module:Symbol",
                    parent=dialog,
                )
                return

            # Pre-check conflicts before writing.
            catalog_snapshot = self.app.catalog or self.load_catalog()
            existing = catalog_snapshot.get(key)
            if existing:
                old_title = str(existing.get("title", "") or "")
                old_import = str(existing.get("import_path", "") or "")
                changed = (old_title != title) or (old_import != import_path)
                if changed and not bool(allow_replace_var.get()):
                    messagebox.showerror(
                        "Key conflict",
                        "Key already exists with different title/import_path.\n"
                        "Enable 'Allow replace when key conflicts' to continue.",
                        parent=dialog,
                    )
                    return
                if changed and not messagebox.askyesno(
                    "Confirm replace",
                    f"Key already exists and differs.\n\n"
                    f"key: {key}\n"
                    f"old title: {old_title}\nnew title: {title}\n"
                    f"old import: {old_import}\nnew import: {import_path}\n\n"
                    f"Replace existing entry?",
                    parent=dialog,
                ):
                    return

            dup_keys: list[str] = []
            for k2, info2 in catalog_snapshot.items():
                if str(k2) == key:
                    continue
                if str(info2.get("import_path", "") or "").strip() == import_path:
                    dup_keys.append(str(k2))
            if dup_keys:
                if not messagebox.askyesno(
                    "Import path conflict",
                    "This import_path is already used by other keys:\n"
                    + "\n".join(f"- {k}" for k in dup_keys[:8])
                    + ("\n..." if len(dup_keys) > 8 else "")
                    + "\n\nContinue save anyway?",
                    parent=dialog,
                ):
                    return

            payload = build_entry_payload(
                key=key,
                title=title,
                kind=kind,
                import_path=import_path,
                summary=summary,
                tags=_to_values(vars_map["tags"].get()),
                companions=_to_values(vars_map["companions"].get()),
                use_when=_to_values(vars_map["use_when"].get()),
                minimal_wiring=_to_values(vars_map["minimal_wiring"].get()),
                required_companions=_to_values(vars_map["required_companions"].get()),
                config_keys=_to_values(vars_map["config_keys"].get()),
                example_entry=vars_map["example_entry"].get().strip(),
                context_requires=_to_values(vars_map["context_requires"].get()),
                context_provides=_to_values(vars_map["context_provides"].get()),
                context_mutates=_to_values(vars_map["context_mutates"].get()),
                context_cache=_to_values(vars_map["context_cache"].get()),
                context_notes=_to_values(vars_map["context_notes"].get()),
            )
            if bool(write_code_on_save_var.get()) and source_file and symbol:
                try:
                    from nsgablack.catalog.source_sync import apply_symbol_contract

                    contract_payload = {
                        field: _to_values(vars_map[field].get())
                        for field in context_fields
                    }
                    apply_symbol_contract(Path(source_file), symbol, contract_payload)
                except Exception as exc:
                    messagebox.showerror(
                        "Catalog add failed",
                        f"Saved canceled: cannot write contract to source code:\n{exc}",
                        parent=dialog,
                    )
                    return
            try:
                upsert_catalog_entry(target_file, payload, replace=True)
            except Exception as exc:
                messagebox.showerror("Catalog add failed", f"Write failed:\n{exc}", parent=dialog)
                return

            reload_root = source_project_root if source_project_root is not None else None
            self.app.catalog = self.load_catalog(override_project_root=reload_root)
            self.search()
            self.catalog_query_var.set(str(payload["key"]))
            self.search()
            self.catalog_status_var.set(f"Saved: {payload['key']} -> {target_file}")
            messagebox.showinfo("Saved", f"Catalog entry saved:\n{payload['key']}", parent=dialog)

        ttk.Button(actions, text="Save", command=_save).pack(side="left")
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="left", padx=(6, 0))

    def _lookup_info(self, entry_key: str) -> Dict[str, Any]:
        info = self.app.catalog.get(str(entry_key), {})
        if info:
            return info
        if self.app._catalog_obj is None:
            return {}
        entry = self.app._catalog_obj.get(str(entry_key))
        if entry is None:
            return {}
        from nsgablack.catalog import build_usage_profile

        usage = build_usage_profile(entry)
        return {
            "key": entry.key,
            "scope": scope_from_key(entry.key),
            "kind": entry.kind,
            "title": entry.title,
            "import_path": entry.import_path,
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

    def search_context_key(self, context_key: str, *, role: str = "all") -> None:
        """Run context search and then narrow by role (providers/requires)."""
        key = str(context_key or "").strip()
        if not key:
            return

        self.catalog_match_var.set("context")
        self.catalog_query_var.set(key)
        self.search()

        role_key = str(role or "all").strip().lower()
        if role_key not in {"providers", "requires"}:
            return

        for item_id in list(self.catalog_result_tree.get_children()):
            values = self.catalog_result_tree.item(item_id, "values")
            entry_key = values[0] if values else ""
            info = self._lookup_info(str(entry_key))
            if not context_role_match(info, key, role_key):
                self.catalog_result_tree.delete(item_id)

        shown = len(self.catalog_result_tree.get_children())
        self.catalog_status_var.set(f"Results: {shown} | role={role_key} | key={key}")
        self._clear_cards()

    def on_select(self, _event: Any) -> None:
        sel = self.catalog_result_tree.selection()
        if not sel:
            self.delete_entry_btn.configure(state="disabled")
            return
        item_id = sel[0]
        values = self.catalog_result_tree.item(item_id, "values")
        key = values[0] if values else ""
        info = self._lookup_info(str(key))
        summary = str(info.get("summary", "") or "")
        source_catalog = str(info.get("project_catalog_file", "") or "").strip()
        companions = info.get("companions") or []
        contracts = self._format_contracts(info)
        usage = self._format_usage(info)
        scope = str(info.get("scope", scope_from_key(str(key))))
        kind = str(info.get("kind", "") or "")

        source_line = f"\nsource_catalog: {source_catalog}" if source_catalog else ""
        summary_card = f"key: {key}\nscope: {scope}\nkind: {kind}{source_line}\n\n{summary}".strip()
        companions_card = "\n".join(f"- {c}" for c in companions) if companions else "(none)"
        example_entry = str(info.get("example_entry", "") or "").strip()

        self._set_detail_text("summary", summary_card)
        self._set_detail_text("usage", usage)
        self._set_detail_text("contract", contracts)
        self._set_detail_text("companions", companions_card)
        self._set_detail_text("example", example_entry or "(none)")
        self._select_detail_tab("summary")
        scope_is_project = str(info.get("scope", scope_from_key(str(key)))).strip().lower() == "project"
        self.delete_entry_btn.configure(state=("normal" if scope_is_project else "disabled"))

    def _project_catalog_file(self) -> Optional[Path]:
        root = self._detect_project_root()
        if root is None:
            return None
        return root / "catalog" / "entries.toml"

    def _is_scaffold_project_root(self, root: Path) -> bool:
        """Strict project-scaffold check: only these roots should use project.* auto-prefix."""
        req_files = ("project_registry.py", "build_solver.py")
        req_dirs = ("problem", "pipeline", "bias", "adapter", "plugins")
        return all((root / f).is_file() for f in req_files) and all((root / d).is_dir() for d in req_dirs)

    def _delete_selected_project_entry(self) -> None:
        sel = self.catalog_result_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select one catalog entry first.", parent=self.tab.winfo_toplevel())
            return
        values = self.catalog_result_tree.item(sel[0], "values")
        key = str(values[0]) if values else ""
        if not key:
            return
        info = self._lookup_info(key)
        scope = str(info.get("scope", scope_from_key(key))).strip().lower()
        if scope != "project":
            messagebox.showerror(
                "Delete blocked",
                "Only project-level catalog entries can be deleted here.",
                parent=self.tab.winfo_toplevel(),
            )
            return
        project_catalog = None
        mapped_catalog = str(info.get("project_catalog_file", "") or "").strip()
        if mapped_catalog:
            project_catalog = Path(mapped_catalog)
        if project_catalog is None:
            project_catalog = self._project_catalog_file()
        if project_catalog is None:
            messagebox.showerror(
                "Delete failed",
                "Project root not found. Open Run Inspector with a project workspace.",
                parent=self.tab.winfo_toplevel(),
            )
            return
        if not project_catalog.exists():
            messagebox.showerror(
                "Delete failed",
                f"Project catalog file not found:\n{project_catalog}",
                parent=self.tab.winfo_toplevel(),
            )
            return
        if not messagebox.askyesno(
            "Confirm delete",
            f"Delete project catalog entry?\n\nkey: {key}\nfile: {project_catalog}",
            parent=self.tab.winfo_toplevel(),
        ):
            return
        try:
            from nsgablack.catalog.quick_add import remove_catalog_entry

            removed = remove_catalog_entry(project_catalog, key)
        except Exception as exc:
            messagebox.showerror("Delete failed", f"Cannot delete entry:\n{exc}", parent=self.tab.winfo_toplevel())
            return
        if not removed:
            messagebox.showwarning("Not found", f"Entry not found: {key}", parent=self.tab.winfo_toplevel())
            return
        self.app.catalog = self.load_catalog()
        self.search()
        self.catalog_status_var.set(f"Deleted: {key} <- {project_catalog}")
        messagebox.showinfo("Deleted", f"Catalog entry deleted:\n{key}", parent=self.tab.winfo_toplevel())

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
