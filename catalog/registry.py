from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple
import importlib
import os
from pathlib import Path
import re
from blackbase.catalog import load_catalog_paths

from blackbase.catalog import Catalog as SharedCatalog
from blackbase.catalog import CatalogEntry as SharedCatalogEntry

try:  # py>=3.11
    import tomllib as _toml
except Exception:  # pragma: no cover - import fallback
    try:  # py<3.11
        import tomli as _toml
    except Exception:  # pragma: no cover - optional dependency missing
        _toml = None


@dataclass(frozen=True)
class CatalogEntry(SharedCatalogEntry):
    """A discoverability record for one framework component."""

    def load(self):
        """Import and return the referenced symbol."""
        mod_path, _, sym = self.import_path.partition(":")
        if not mod_path or not sym:
            raise ValueError(f"Invalid import_path: {self.import_path!r}")
        if self.metadata.get("case_root"):
            return super().load()
        project_context = _example_project_context(mod_path)
        if project_context is not None:
            project_root, case_name = project_context
            from blackbase.project.runtime import case_import_context

            with case_import_context(project_root, case_name):
                mod = importlib.import_module(mod_path)
                return getattr(mod, sym)
        return super().load()


def _example_project_context(module_path: str) -> tuple[Path, str] | None:
    parts = str(module_path).split(".")
    if len(parts) < 6 or parts[:2] != ["examples", "cases"]:
        return None
    try:
        cases_index = parts.index("cases", 2)
    except ValueError:
        return None
    if cases_index + 1 >= len(parts):
        return None
    project_name = parts[2]
    case_name = parts[cases_index + 1]
    here = Path(__file__).resolve()
    repo_root = here.parent.parent
    project_root = repo_root / "examples" / "cases" / project_name
    if (project_root / "project_config.py").is_file() and (project_root / "cases" / case_name).is_dir():
        return project_root, case_name
    return None


class Catalog(SharedCatalog):
    def __init__(self, entries: Sequence[CatalogEntry]):
        super().__init__(entries)
        self._entries = list(self._entries)
        self._context_blob_cache: Dict[str, str] = {}
        self._detail_entry_cache: Dict[str, CatalogEntry] = {}
        self._detail_file_cache: Dict[str, Dict[str, object]] = {}

    def get(self, key: str) -> Optional[CatalogEntry]:
        entry = self._by_key.get(key)
        if entry is None:
            return None
        return self._hydrate_entry(entry)

    def list(self, *, kind: Optional[str] = None, tag: Optional[str] = None) -> List[CatalogEntry]:
        out = list(self._entries)
        if kind is not None:
            k = str(kind).lower().strip()
            out = [e for e in out if e.kind == k]
        if tag is not None:
            t = str(tag).lower().strip()
            out = [e for e in out if t in (x.lower() for x in e.tags)]
        return out

    def search(
        self,
        query: str,
        *,
        kinds: Optional[Sequence[str]] = None,
        tags: Optional[Sequence[str]] = None,
        fields: str = "all",
        limit: int = 20,
    ) -> List[CatalogEntry]:
        q_raw = str(query).strip().lower()
        if not q_raw:
            return []
        tokens = [t for t in re.split(r"\s+", q_raw) if t]
        token_groups = _expand_token_groups(tokens)
        kind_set = {str(k).lower().strip() for k in (kinds or [])}
        tag_set = {str(t).lower().strip() for t in (tags or [])}
        field = (fields or "all").strip().lower()
        use_context_in_all = field == "all" and any(
            ("context" in t)
            or (t in {"requires", "provides", "mutates", "cache", "contract", "contracts", "artifact", "artifacts", "phase"})
            for t in tokens
        )
        use_usage_in_all = field == "all" and any(
            (t in {"use", "usage", "wiring", "wire", "companion", "companions", "config", "example"})
            for t in tokens
        )

        def match(e: CatalogEntry) -> bool:
            if kind_set and e.kind not in kind_set:
                return False
            if tag_set:
                e_tags = {t.lower() for t in e.tags}
                if not tag_set.issubset(e_tags):
                    return False
            target = e
            if field in ("context", "usage") or use_context_in_all or use_usage_in_all:
                target = self._hydrate_entry(e)
            if field == "name":
                hay = " ".join([target.key, target.title]).lower()
            elif field == "tag":
                hay = " ".join(target.tags).lower()
            elif field == "context":
                hay = self._entry_context_blob(target)
            elif field == "usage":
                hay = self._entry_usage_blob(target)
            else:
                hay = " ".join([target.key, target.title, target.kind, target.summary, " ".join(target.tags)]).lower()
                if use_context_in_all:
                    hay = f"{hay} {self._entry_context_blob(target)}"
                if use_usage_in_all:
                    hay = f"{hay} {self._entry_usage_blob(target)}"
            return all(any(t in hay for t in group) for group in token_groups)

        out = [e for e in self._entries if match(e)]

        # keep stable-ish grouping by kind and key
        def rank(e: CatalogEntry) -> Tuple[int, str]:
            kind_order = {
                "adapter": 0,
                "plugin": 1,
                "bias": 2,
                "representation": 3,
                "resource": 4,
                "backend": 5,
                "tool": 6,
                "doc": 7,
                "example": 8,
            }
            return (int(kind_order.get(e.kind, 99)), e.key)

        out.sort(key=rank)
        return out[: max(0, int(limit))]

    def _hydrate_entry(self, entry: CatalogEntry) -> CatalogEntry:
        if not entry.detail_ref:
            return entry
        cached = self._detail_entry_cache.get(entry.key)
        if cached is not None:
            return cached
        payload = self._load_detail_payload(entry.detail_ref)
        if not payload:
            self._detail_entry_cache[entry.key] = entry
            return entry
        merged = replace(
            entry,
            summary=str(payload.get("summary", entry.summary) or entry.summary),
            companions=_coerce_str_tuple(payload.get("companions", entry.companions)),
            context_requires=_coerce_str_tuple(payload.get("context_requires", entry.context_requires)),
            context_provides=_coerce_str_tuple(payload.get("context_provides", entry.context_provides)),
            context_mutates=_coerce_str_tuple(payload.get("context_mutates", entry.context_mutates)),
            context_cache=_coerce_str_tuple(payload.get("context_cache", entry.context_cache)),
            context_notes=_coerce_str_tuple(payload.get("context_notes", entry.context_notes)),
            artifact_requires=_coerce_str_tuple(payload.get("artifact_requires", entry.artifact_requires)),
            artifact_provides=_coerce_str_tuple(payload.get("artifact_provides", entry.artifact_provides)),
            phase_in=_coerce_str_tuple(payload.get("phase_in", entry.phase_in)),
            phase_out=_coerce_str_tuple(payload.get("phase_out", entry.phase_out)),
            use_when=_coerce_str_tuple(payload.get("use_when", entry.use_when)),
            minimal_wiring=_coerce_str_tuple(payload.get("minimal_wiring", entry.minimal_wiring)),
            required_companions=_coerce_str_tuple(payload.get("required_companions", entry.required_companions)),
            config_keys=_coerce_str_tuple(payload.get("config_keys", entry.config_keys)),
            example_entry=str(payload.get("example_entry", entry.example_entry) or entry.example_entry),
        )
        self._detail_entry_cache[entry.key] = merged
        self._by_key[entry.key] = merged
        return merged

    def _load_detail_payload(self, detail_ref: str) -> Dict[str, object]:
        ref = str(detail_ref or "").strip()
        if not ref:
            return {}
        cached = self._detail_file_cache.get(ref)
        if cached is not None:
            return cached
        path = Path(ref)
        if not path.exists() or not path.is_file():
            self._detail_file_cache[ref] = {}
            return {}
        payload: Dict[str, object] = {}
        if path.suffix.lower() == ".toml" and _toml is not None:
            try:
                data = _toml.loads(path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, dict):
                    detail_block = data.get("detail")
                    if isinstance(detail_block, dict):
                        payload = detail_block
                    else:
                        payload = data
            except Exception:
                payload = {}
        self._detail_file_cache[ref] = payload if isinstance(payload, dict) else {}
        return self._detail_file_cache[ref]

    def _entry_context_blob(self, e: CatalogEntry) -> str:
        cached = self._context_blob_cache.get(e.key)
        if cached is not None:
            return cached

        parts: List[str] = []

        def add_field(label: str, values: object, *, include_label: bool) -> None:
            if include_label:
                parts.append(label)
            parts.extend(_coerce_str_tuple(values))

        add_field("context_requires", e.context_requires, include_label=bool(e.context_requires))
        add_field("context_provides", e.context_provides, include_label=bool(e.context_provides))
        add_field("context_mutates", e.context_mutates, include_label=bool(e.context_mutates))
        add_field("context_cache", e.context_cache, include_label=bool(e.context_cache))
        add_field("context_notes", e.context_notes, include_label=bool(e.context_notes))
        add_field("artifact_requires", e.artifact_requires, include_label=bool(e.artifact_requires))
        add_field("artifact_provides", e.artifact_provides, include_label=bool(e.artifact_provides))
        add_field("phase_in", e.phase_in, include_label=bool(e.phase_in))
        add_field("phase_out", e.phase_out, include_label=bool(e.phase_out))

        # If contracts are not attached on CatalogEntry, try reading class-level declarations.
        if not parts:
            try:
                symbol = e.load()
            except Exception:
                symbol = None
            if symbol is not None:
                add_field(
                    "context_requires",
                    getattr(symbol, "context_requires", ()),
                    include_label=hasattr(symbol, "context_requires"),
                )
                add_field(
                    "context_provides",
                    getattr(symbol, "context_provides", ()),
                    include_label=hasattr(symbol, "context_provides"),
                )
                add_field(
                    "context_mutates",
                    getattr(symbol, "context_mutates", ()),
                    include_label=hasattr(symbol, "context_mutates"),
                )
                add_field(
                    "context_cache",
                    getattr(symbol, "context_cache", ()),
                    include_label=hasattr(symbol, "context_cache"),
                )
                add_field(
                    "context_notes",
                    getattr(symbol, "context_notes", ()),
                    include_label=hasattr(symbol, "context_notes"),
                )
                add_field(
                    "artifact_requires",
                    getattr(symbol, "artifact_requires", ()),
                    include_label=hasattr(symbol, "artifact_requires"),
                )
                add_field(
                    "artifact_provides",
                    getattr(symbol, "artifact_provides", ()),
                    include_label=hasattr(symbol, "artifact_provides"),
                )
                add_field(
                    "phase_in",
                    getattr(symbol, "phase_in", ()),
                    include_label=hasattr(symbol, "phase_in"),
                )
                add_field(
                    "phase_out",
                    getattr(symbol, "phase_out", ()),
                    include_label=hasattr(symbol, "phase_out"),
                )

        blob = " ".join(parts).lower()
        self._context_blob_cache[e.key] = blob
        return blob

    def _entry_usage_blob(self, e: CatalogEntry) -> str:
        parts: List[str] = []
        parts.extend(_coerce_str_tuple(getattr(e, "use_when", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "minimal_wiring", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "required_companions", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "config_keys", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "example_entry", "")))
        if not parts:
            parts.extend(_coerce_str_tuple(getattr(e, "companions", ())))
        return " ".join(parts).lower()


def _coerce_str_tuple(value: object) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, dict):
        # Keep deterministic order on dict-like configs.
        return tuple(
            str(k).strip()
            for k in value.keys()
            if str(k).strip()
        )
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return tuple(out)
    text = str(value).strip()
    return (text,) if text else ()


def _expand_token_groups(tokens: List[str]) -> List[List[str]]:
    """Expand search tokens with simple Chinese <-> English alias mapping."""
    alias_map = {
        "\u52a8\u6001": ['dynamic'],
        "\u5207\u6362": ['switch', 'dynamic_switch'],
        "\u63d2\u4ef6": ['plugin'],
        "\u5957\u4ef6": ['suite'],
        "\u504f\u7f6e": ['bias'],
        "\u9002\u914d\u5668": ['adapter'],
        "\u8868\u793a": ['representation', 'repr'],
        "\u7ba1\u7ebf": ['pipeline'],
        "\u793a\u4f8b": ['example', 'demo', 'template'],
        "\u6a21\u677f": ['template', 'example'],
        "\u5e76\u884c": ['parallel'],
        "\u591a\u76ee\u6807": ['multiobjective', 'mo'],
        "\u7ea6\u675f": ['constraint'],
        "\u56fe": ['graph'],
        "\u53ef\u89c6\u5316": ['viz', 'visual', 'visualization', 'run_inspector'],
        "\u53ef\u89c6\u5316\u5148\u9a8c": ['visualization', 'prior', 'structure_prior', 'run_inspector'],
        "\u5148\u9a8c": ['prior', 'structure_prior'],
        "\u8def\u5f84": ['path'],
        "\u542f\u53d1": ['heuristic'],
        "\u8bc4\u4f30": ['evaluation', 'evaluate'],
        "\u641c\u7d22": ['search'],
        "\u534f\u540c": ['cooperation', 'multi_strategy', 'multi-strategy'],
        "\u591a\u7b56\u7565": ['multi_strategy', 'multi-strategy'],
        "\u89d2\u8272": ['role'],
        "\u9000\u706b": ['simulated_annealing', 'sa'],
        "\u7981\u5fcc": ['tabu'],
        "\u5dee\u5206\u8fdb\u5316": ['differential_evolution', 'de'],
        "\u7c92\u5b50\u7fa4": ['pso'],
        "\u53d8\u5f02": ['mutation', 'mutator'],
        "\u521d\u59cb\u5316": ['initializer', 'init'],
        "\u4fee\u590d": ['repair'],
        "\u7f16\u7801": ['encode'],
        "\u89e3\u7801": ['decode'],
        "\u57fa\u51c6": ['benchmark'],
        "\u76d1\u63a7": ['monitor'],
        "\u6536\u655b": ['convergence'],
        "\u7cbe\u82f1": ['elite'],
        "\u591a\u6837\u6027": ['diversity'],
        "\u4ee3\u7406": ['surrogate'],
        "\u7edf\u8ba1": ['metrics'],
        "\u65e5\u5fd7": ['logging', 'log', 'report'],
        "\u62a5\u544a": ['report'],
        "\u5206\u5e03\u5f0f": ['distributed', 'ray'],
        "\u4e3b\u52a8\u5b66\u4e60": ['active_learning', 'active'],
        "\u524d\u6cbf": ['frontier'],
        "\u7ed3\u6784\u5148\u9a8c": ['structure', 'prior'],
        "\u5bf9\u79f0": ['symmetry'],
        "\u591a\u4fdd\u771f": ['multi_fidelity'],
        "\u98ce\u9669": ['risk', 'cvar', 'worst_case'],
        "\u9c81\u68d2": ['robust', 'robustness'],
        "\u4fe1\u8d56\u57df": ['trust_region', 'tr'],
        "\u5b50\u7a7a\u95f4": ['subspace', 'low_rank'],
        "\u975e\u5149\u6ed1": ['nonsmooth', 'non_smooth'],
        "\u6a21\u578b": ['model', 'surrogate'],
        "\u8499\u7279\u5361\u6d1b": ['monte_carlo', 'mc'],
    }
    out: List[List[str]] = []
    for t in tokens:
        group = [t]
        group.extend(alias_map.get(t, []))
        seen = set()
        uniq = []
        for item in group:
            if item in seen:
                continue
            seen.add(item)
            uniq.append(item)
        out.append(uniq)
    return out



def _normalize_catalog_profile(profile: Optional[str]) -> str:
    raw = str(profile or os.environ.get("NSGABLACK_CATALOG_PROFILE", "default")).strip().lower()
    if raw in {"framework-core", "framework_core", "core"}:
        return "framework-core"
    return "default"


_CATALOG_BY_PROFILE: Dict[str, Catalog] = {}


def _uses_examples_path(text: str) -> bool:
    raw = str(text or "").lower()
    return (
        "examples/" in raw
        or "examples\\" in raw
        or "nsgablack.examples_registry" in raw
    )


def _apply_catalog_profile(entries: Sequence[CatalogEntry], profile: str) -> List[CatalogEntry]:
    normalized = _normalize_catalog_profile(profile)
    if normalized != "framework-core":
        return list(entries)

    out: List[CatalogEntry] = []
    for entry in entries:
        if entry.kind in {"example", "doc"}:
            continue
        if _uses_examples_path(entry.import_path):
            continue
        if _uses_examples_path(entry.example_entry):
            entry = replace(entry, example_entry="")
        out.append(entry)
    return out


def _load_entrypoint_entries() -> List[CatalogEntry]:
    """
    Load catalog entries from Python entrypoints (third-party extensions).

    Entry point group: `nsgablack.catalog`

    Each entry point should resolve to either:
    - a `CatalogEntry`
    - an iterable of `CatalogEntry`
    - a callable returning one of the above
    """
    try:
        from importlib.metadata import entry_points  # py>=3.10
    except Exception:  # pragma: no cover
        return []

    out: List[CatalogEntry] = []
    try:
        eps = entry_points(group="nsgablack.catalog")
    except Exception:  # pragma: no cover
        return []

    for ep in eps:
        try:
            obj = ep.load()
            if callable(obj):
                obj = obj()
            if isinstance(obj, CatalogEntry):
                out.append(obj)
            elif isinstance(obj, (list, tuple)):
                out.extend([x for x in obj if isinstance(x, CatalogEntry)])
        except Exception:
            continue
    return out



class CatalogProvider:
    """Catalog source provider interface."""

    name: str = "provider"

    def load(self) -> List[CatalogEntry]:
        raise NotImplementedError


def _load_toml_entries(paths: Sequence[Path]) -> List[CatalogEntry]:
    return [CatalogEntry(**entry.as_dict()) for entry in load_catalog_paths(paths)]


class BuiltinTomlProvider(CatalogProvider):
    """
    Builtin catalog source:
    - catalog/entries/*.toml
    """

    name = "builtin_toml"

    def load(self) -> List[CatalogEntry]:
        return _load_toml_entries(
            [
                Path(__file__).with_name("entries"),
            ]
        )


class EnvTomlProvider(CatalogProvider):
    """External catalog from NSGABLACK_CATALOG_PATH (file or directory list)."""

    name = "env_toml"

    def load(self) -> List[CatalogEntry]:
        env = os.environ.get("NSGABLACK_CATALOG_PATH", "").strip()
        if not env:
            return []
        paths: List[Path] = []
        for part in env.split(os.pathsep):
            p = part.strip().strip('"')
            if p:
                paths.append(Path(p))
        return _load_toml_entries(paths)


def _load_external_entries() -> List[CatalogEntry]:
    """Load entries from configured catalog providers."""
    providers: List[CatalogProvider] = [BuiltinTomlProvider(), EnvTomlProvider()]
    try:
        from .store.mysql import mysql_config_enabled, mysql_config_mode
        from .providers.mysql_provider import MySQLCatalogProvider

        if mysql_config_enabled() and mysql_config_mode() != "off":
            providers.append(MySQLCatalogProvider())
    except Exception:
        pass
    out: List[CatalogEntry] = []
    for provider in providers:
        out.extend(provider.load())
    return out


def get_catalog(*, refresh: bool = False, profile: Optional[str] = None) -> Catalog:
    global _CATALOG_BY_PROFILE
    profile_name = _normalize_catalog_profile(profile)
    if refresh or profile_name not in _CATALOG_BY_PROFILE:
        from .usage import enrich_context_contracts, enrich_usage_contracts

        # PostgreSQL "only" mode — all entries from DB, zero memory overhead.
        try:
            from .store.postgres import postgres_config_enabled, postgres_config_mode
            from .providers.postgres_provider import PostgresCatalogProvider
        except Exception:
            postgres_config_enabled = None
            postgres_config_mode = None
            PostgresCatalogProvider = None

        if postgres_config_enabled and postgres_config_mode and PostgresCatalogProvider:
            if postgres_config_enabled() and postgres_config_mode() == "only":
                pg_entries = PostgresCatalogProvider().load()
                profiled_entries = _apply_catalog_profile(list(pg_entries), profile_name)
                enriched = enrich_context_contracts(
                    profiled_entries,
                    kinds=("plugin", "adapter", "bias", "representation", "resource", "backend"),
                )
                enriched = enrich_usage_contracts(enriched)
                _CATALOG_BY_PROFILE[profile_name] = Catalog(enriched)
                return _CATALOG_BY_PROFILE[profile_name]

        # MySQL "only" mode — same pattern.
        try:
            from .store.mysql import mysql_config_enabled, mysql_config_mode
            from .providers.mysql_provider import MySQLCatalogProvider
        except Exception:
            mysql_config_enabled = None
            mysql_config_mode = None
            MySQLCatalogProvider = None

        if mysql_config_enabled and mysql_config_mode and MySQLCatalogProvider:
            if mysql_config_enabled() and mysql_config_mode() == "only":
                mysql_entries = MySQLCatalogProvider().load()
                profiled_entries = _apply_catalog_profile(list(mysql_entries), profile_name)
                enriched = enrich_context_contracts(
                    profiled_entries,
                    kinds=("plugin", "adapter", "bias", "representation", "resource", "backend"),
                )
                enriched = enrich_usage_contracts(enriched)
                _CATALOG_BY_PROFILE[profile_name] = Catalog(enriched)
                return _CATALOG_BY_PROFILE[profile_name]

        extra = _load_external_entries()
        eps = _load_entrypoint_entries()

        # TOML/provider records are authoritative; explicit package entry points
        # may override them by key.
        merged: Dict[str, CatalogEntry] = {e.key: e for e in extra}
        for e in eps:
            merged[e.key] = e
        profiled_entries = _apply_catalog_profile(list(merged.values()), profile_name)

        enriched = enrich_context_contracts(
            profiled_entries,
            kinds=("plugin", "adapter", "bias", "representation", "resource", "backend"),
        )
        enriched = enrich_usage_contracts(enriched)
        _CATALOG_BY_PROFILE[profile_name] = Catalog(enriched)
    return _CATALOG_BY_PROFILE[profile_name]
