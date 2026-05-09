from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .contract_relations import build_contract_edge_rows
from .facade import catalog_source_info, list_entries, search_entries
from .registry import CatalogEntry

_DEFAULT_EXPORT_FORMATS: tuple[str, ...] = (
    "table-csv",
    "edge-csv",
    "key-csv",
    "dot",
    "mermaid",
    "family-dot",
    "family-mermaid",
)
_VALID_EXPORT_FORMATS = {"json", "table-csv", "edge-csv", "key-csv", "dot", "mermaid", "family-dot", "family-mermaid"}
_RELATION_FAMILY_ORDER: tuple[str, ...] = ("context", "artifact", "phase", "companion")

_KIND_COLORS: dict[str, str] = {
    "adapter": "#dbeafe",
    "plugin": "#fef3c7",
    "bias": "#dcfce7",
    "representation": "#fee2e2",
    "suite": "#ede9fe",
    "tool": "#e5e7eb",
    "doc": "#e0f2fe",
    "example": "#fae8ff",
}

_RELATION_FAMILY_COLORS: dict[str, str] = {
    "context": "#0f766e",
    "artifact": "#7c3aed",
    "phase": "#b45309",
    "companion": "#64748b",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_export_formats(formats: Sequence[str] | None) -> tuple[str, ...]:
    if not formats:
        return _DEFAULT_EXPORT_FORMATS
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in formats:
        key = str(raw or "").strip().lower()
        if not key:
            continue
        if key == "all":
            for name in ("json", *list(_DEFAULT_EXPORT_FORMATS)):
                if name not in seen:
                    normalized.append(name)
                    seen.add(name)
            continue
        if key not in _VALID_EXPORT_FORMATS:
            raise ValueError(f"Unsupported relation export format: {raw}")
        if key not in seen:
            normalized.append(key)
            seen.add(key)
    return tuple(normalized) or _DEFAULT_EXPORT_FORMATS


def _csv_join(values: Sequence[str]) -> str:
    return " | ".join(str(value).strip() for value in values if str(value).strip())


def _dot_escape(text: object) -> str:
    raw = str(text or "")
    return raw.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _mermaid_escape(text: object) -> str:
    raw = str(text or "")
    return raw.replace('"', "'").replace("\n", "<br/>")


def _relation_family_sort_index(family: object) -> int:
    key = str(family or "").strip().lower()
    return _RELATION_FAMILY_ORDER.index(key) if key in _RELATION_FAMILY_ORDER else 99


def _build_relation_key_rows(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in edges:
        family = str(edge.get("relation_family", "") or "").strip().lower()
        value = str(edge.get("relation_value", "") or "").strip()
        if not family or not value:
            continue
        token = (family, value)
        row = grouped.setdefault(
            token,
            {
                "relation_family": family,
                "relation_value": value,
                "edge_count": 0,
                "producer_keys": set(),
                "producer_kinds": set(),
                "consumer_keys": set(),
                "consumer_kinds": set(),
            },
        )
        row["edge_count"] = int(row.get("edge_count", 0) or 0) + 1
        source_key = str(edge.get("source_key", "") or "").strip()
        source_kind = str(edge.get("source_kind", "") or "").strip()
        target_key = str(edge.get("target_key", "") or "").strip()
        target_kind = str(edge.get("target_kind", "") or "").strip()
        if source_key:
            row["producer_keys"].add(source_key)
        if source_kind:
            row["producer_kinds"].add(source_kind)
        if target_key:
            row["consumer_keys"].add(target_key)
        if target_kind:
            row["consumer_kinds"].add(target_kind)

    rows: list[dict[str, Any]] = []
    for family, value in sorted(grouped.keys(), key=lambda item: (_relation_family_sort_index(item[0]), item[1])):
        row = grouped[(family, value)]
        producer_keys = tuple(sorted(str(item) for item in row.get("producer_keys", set())))
        producer_kinds = tuple(sorted(str(item) for item in row.get("producer_kinds", set())))
        consumer_keys = tuple(sorted(str(item) for item in row.get("consumer_keys", set())))
        consumer_kinds = tuple(sorted(str(item) for item in row.get("consumer_kinds", set())))
        rows.append(
            {
                "relation_family": family,
                "relation_value": value,
                "edge_count": int(row.get("edge_count", 0) or 0),
                "producer_count": len(producer_keys),
                "consumer_count": len(consumer_keys),
                "producer_keys": producer_keys,
                "producer_kinds": producer_kinds,
                "consumer_keys": consumer_keys,
                "consumer_kinds": consumer_kinds,
            }
        )
    return rows


def _family_bundle(bundle: Mapping[str, Any], family: str) -> dict[str, Any]:
    family_key = str(family or "").strip().lower()
    source_edges = [
        dict(edge)
        for edge in tuple(bundle.get("edges", ()) or ())
        if str(edge.get("relation_family", "") or "").strip().lower() == family_key
    ]
    node_keys: set[str] = set()
    for edge in source_edges:
        source_key = str(edge.get("source_key", "") or "").strip()
        target_key = str(edge.get("target_key", "") or "").strip()
        if source_key:
            node_keys.add(source_key)
        if target_key and bool(edge.get("target_in_catalog", False)):
            node_keys.add(target_key)
    source_nodes = [
        dict(node)
        for node in tuple(bundle.get("nodes", ()) or ())
        if str(node.get("key", "") or "").strip() in node_keys
    ]
    relation_keys = [
        dict(row)
        for row in tuple(bundle.get("relation_keys", ()) or ())
        if str(row.get("relation_family", "") or "").strip().lower() == family_key
    ]
    summary = {
        "total_nodes": len(source_nodes),
        "total_edges": len(source_edges),
        "relation_key_count": len(relation_keys),
        "family": family_key,
    }
    return {
        "exported_at_utc": bundle.get("exported_at_utc"),
        "profile": bundle.get("profile"),
        "scope": bundle.get("scope"),
        "project_root": bundle.get("project_root"),
        "project_found": bundle.get("project_found"),
        "include_global": bundle.get("include_global"),
        "kind": bundle.get("kind"),
        "query": bundle.get("query"),
        "search_field": bundle.get("search_field"),
        "field_filters": dict(bundle.get("field_filters", {}) or {}),
        "source": dict(bundle.get("source", {}) or {}),
        "summary": summary,
        "nodes": source_nodes,
        "edges": source_edges,
        "relation_keys": relation_keys,
    }


def _filter_entries(
    *,
    profile: str | None,
    scope: str | None,
    project_path: str | Path | None,
    include_global: bool,
    kind: str | None,
    query: str,
    search_field: str,
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None,
    db_path: str | None,
    source_mode: str | None,
) -> tuple[list[CatalogEntry], list[CatalogEntry]]:
    universe_entries = list(
        list_entries(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=None,
            limit=None,
            field_filters=None,
            db_path=db_path,
            source_mode=source_mode,
        )
    )
    query_text = str(query or "").strip()
    if not query_text:
        filtered_entries = list(
            list_entries(
                profile=profile,
                scope=scope,
                project_path=project_path,
                include_global=include_global,
                kind=kind,
                limit=None,
                field_filters=field_filters,
                db_path=db_path,
                source_mode=source_mode,
            )
        )
        return universe_entries, filtered_entries
    match_limit = max(len(universe_entries), 1)
    filtered_entries = list(
        search_entries(
            query_text,
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            field=search_field,
            limit=match_limit,
            field_filters=field_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
    )
    return universe_entries, filtered_entries


def build_catalog_relation_bundle(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    query: str = "",
    search_field: str = "all",
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    universe_entries, filtered_entries = _filter_entries(
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
        kind=kind,
        query=query,
        search_field=search_field,
        field_filters=field_filters,
        db_path=db_path,
        source_mode=source_mode,
    )
    source_info = catalog_source_info(
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
        db_path=db_path,
        source_mode=source_mode,
    )

    universe_by_key = {entry.key: entry for entry in universe_entries}
    filtered_by_key = {entry.key: entry for entry in filtered_entries}
    reverse_links: dict[str, list[str]] = {}
    missing_from_entry: dict[str, list[str]] = {}
    for entry in universe_entries:
        for companion_key in entry.companions:
            if companion_key in universe_by_key:
                reverse_links.setdefault(companion_key, []).append(entry.key)
            else:
                missing_from_entry.setdefault(entry.key, []).append(companion_key)

    edges: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    for entry in filtered_entries:
        linked_by = tuple(sorted(reverse_links.get(entry.key, ())))
        missing_companions = tuple(sorted(missing_from_entry.get(entry.key, ())))
        companions = tuple(entry.companions)
        nodes.append(
            {
                "key": entry.key,
                "title": entry.title,
                "kind": entry.kind,
                "import_path": entry.import_path,
                "summary": entry.summary,
                "tags": tuple(entry.tags),
                "companions": companions,
                "linked_by": linked_by,
                "missing_companions": missing_companions,
                "required_companions": tuple(entry.required_companions),
                "context_requires": tuple(entry.context_requires),
                "context_provides": tuple(entry.context_provides),
                "artifact_requires": tuple(getattr(entry, "artifact_requires", ()) or ()),
                "artifact_provides": tuple(getattr(entry, "artifact_provides", ()) or ()),
                "phase_in": tuple(getattr(entry, "phase_in", ()) or ()),
                "phase_out": tuple(getattr(entry, "phase_out", ()) or ()),
                "out_degree": len(companions),
                "in_degree": len(linked_by),
            }
        )
        for companion_key in companions:
            target_entry = universe_by_key.get(companion_key)
            edges.append(
                {
                    "source_key": entry.key,
                    "source_kind": entry.kind,
                    "target_key": companion_key,
                    "target_kind": target_entry.kind if target_entry is not None else None,
                    "target_title": target_entry.title if target_entry is not None else None,
                    "target_in_catalog": target_entry is not None,
                    "target_in_export": companion_key in filtered_by_key,
                    "relation": "companion",
                }
            )

    contract_edges = build_contract_edge_rows(
        source_entries=filtered_entries,
        consumer_candidates=universe_entries,
        filtered_keys=set(filtered_by_key.keys()),
    )
    edges.extend(contract_edges)
    relation_key_rows = _build_relation_key_rows(edges)

    nodes.sort(key=lambda item: (str(item.get("kind", "")), str(item.get("key", ""))))
    edges.sort(
        key=lambda item: (
            str(item.get("source_kind", "")),
            str(item.get("source_key", "")),
            str(item.get("target_key", "")),
            str(item.get("relation", "")),
            str(item.get("relation_value", "")),
        )
    )
    relation_counts = {
        "companion": sum(1 for item in edges if item.get("relation") == "companion"),
        "context_contract": sum(1 for item in edges if item.get("relation") == "context_contract"),
        "artifact_contract": sum(1 for item in edges if item.get("relation") == "artifact_contract"),
        "phase_contract": sum(1 for item in edges if item.get("relation") == "phase_contract"),
    }
    summary = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "companion_edges": relation_counts["companion"],
        "context_contract_edges": relation_counts["context_contract"],
        "artifact_contract_edges": relation_counts["artifact_contract"],
        "phase_contract_edges": relation_counts["phase_contract"],
        "relation_counts": relation_counts,
        "relation_key_count": len(relation_key_rows),
        "relation_key_counts": {
            family: sum(1 for row in relation_key_rows if str(row.get("relation_family", "")) == family)
            for family in ("context", "artifact", "phase")
        },
        "nodes_with_companions": sum(1 for item in nodes if item["out_degree"] > 0),
        "nodes_with_linked_by": sum(1 for item in nodes if item["in_degree"] > 0),
        "missing_companion_refs": sum(len(tuple(item["missing_companions"])) for item in nodes),
        "max_out_degree": max((int(item["out_degree"]) for item in nodes), default=0),
        "max_in_degree": max((int(item["in_degree"]) for item in nodes), default=0),
    }
    return {
        "exported_at_utc": _utc_now_iso(),
        "profile": str(profile or source_info.get("profile") or "default"),
        "scope": str(scope or source_info.get("scope") or "framework"),
        "project_root": source_info.get("project_root"),
        "project_found": bool(source_info.get("project_found", False)),
        "include_global": bool(include_global),
        "kind": str(kind or "").strip() or None,
        "query": str(query or ""),
        "search_field": str(search_field or "all"),
        "field_filters": dict(field_filters or {}),
        "source": source_info,
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "relation_keys": relation_key_rows,
    }


def _default_output_base(*, output_path: str | Path | None, profile: str | None, scope: str | None, kind: str | None) -> Path:
    if output_path:
        return Path(output_path)
    profile_key = str(profile or "default").strip() or "default"
    scope_key = str(scope or "framework").strip() or "framework"
    kind_key = str(kind or "all").strip() or "all"
    return Path("out") / "catalog_relations" / f"{profile_key}_{scope_key}_{kind_key}"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, bundle: Mapping[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_table_csv(path: Path, nodes: Sequence[Mapping[str, Any]]) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "key",
                "title",
                "kind",
                "import_path",
                "summary",
                "out_degree",
                "in_degree",
                "tags",
                "companions",
                "linked_by",
                "missing_companions",
                "required_companions",
                "context_requires",
                "context_provides",
                "artifact_requires",
                "artifact_provides",
                "phase_in",
                "phase_out",
            ],
        )
        writer.writeheader()
        for node in nodes:
            writer.writerow(
                {
                    "key": node.get("key"),
                    "title": node.get("title"),
                    "kind": node.get("kind"),
                    "import_path": node.get("import_path"),
                    "summary": node.get("summary"),
                    "out_degree": node.get("out_degree"),
                    "in_degree": node.get("in_degree"),
                    "tags": _csv_join(node.get("tags", ())),
                    "companions": _csv_join(node.get("companions", ())),
                    "linked_by": _csv_join(node.get("linked_by", ())),
                    "missing_companions": _csv_join(node.get("missing_companions", ())),
                    "required_companions": _csv_join(node.get("required_companions", ())),
                    "context_requires": _csv_join(node.get("context_requires", ())),
                    "context_provides": _csv_join(node.get("context_provides", ())),
                    "artifact_requires": _csv_join(node.get("artifact_requires", ())),
                    "artifact_provides": _csv_join(node.get("artifact_provides", ())),
                    "phase_in": _csv_join(node.get("phase_in", ())),
                    "phase_out": _csv_join(node.get("phase_out", ())),
                }
            )


def _write_edge_csv(path: Path, edges: Sequence[Mapping[str, Any]]) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_key",
                "source_kind",
                "target_key",
                "target_kind",
                "target_title",
                "target_in_catalog",
                "target_in_export",
                "relation",
                "relation_field",
                "relation_value",
                "relation_family",
            ],
        )
        writer.writeheader()
        for edge in edges:
            writer.writerow(dict(edge))


def _write_key_csv(path: Path, relation_keys: Sequence[Mapping[str, Any]]) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "relation_family",
                "relation_value",
                "edge_count",
                "producer_count",
                "consumer_count",
                "producer_kinds",
                "consumer_kinds",
                "producer_keys",
                "consumer_keys",
            ],
        )
        writer.writeheader()
        for row in relation_keys:
            writer.writerow(
                {
                    "relation_family": row.get("relation_family"),
                    "relation_value": row.get("relation_value"),
                    "edge_count": row.get("edge_count"),
                    "producer_count": row.get("producer_count"),
                    "consumer_count": row.get("consumer_count"),
                    "producer_kinds": _csv_join(row.get("producer_kinds", ())),
                    "consumer_kinds": _csv_join(row.get("consumer_kinds", ())),
                    "producer_keys": _csv_join(row.get("producer_keys", ())),
                    "consumer_keys": _csv_join(row.get("consumer_keys", ())),
                }
            )


def _write_dot(path: Path, bundle: Mapping[str, Any]) -> None:
    nodes = list(bundle.get("nodes", ()))
    edges = list(bundle.get("edges", ()))
    _ensure_parent(path)
    lines: list[str] = [
        "digraph nsgablack_catalog_relations {",
        "  graph [rankdir=LR, overlap=false, splines=true];",
        "  node [shape=box, style=filled, fontname=\"Arial\", color=\"#334155\"];",
        "  edge [color=\"#64748b\", arrowsize=0.7];",
    ]
    declared: set[str] = set()
    for node in nodes:
        key = str(node.get("key", ""))
        title = str(node.get("title", ""))
        kind = str(node.get("kind", ""))
        fill = _KIND_COLORS.get(kind, "#f8fafc")
        label = f"{key}\\n[{kind}]\\n{title}" if title else f"{key}\\n[{kind}]"
        lines.append(
            f'  "{_dot_escape(key)}" [label="{_dot_escape(label)}", fillcolor="{fill}"];'
        )
        declared.add(key)
    for edge in edges:
        source_key = str(edge.get("source_key", ""))
        target_key = str(edge.get("target_key", ""))
        if target_key not in declared:
            lines.append(
                f'  "{_dot_escape(target_key)}" [label="{_dot_escape(target_key)}\\n[missing]", style="dashed,filled", fillcolor="#ffffff"];'
            )
            declared.add(target_key)
        style = "solid" if bool(edge.get("target_in_catalog", False)) else "dashed"
        relation = str(edge.get("relation", "") or "")
        if relation == "context_contract":
            relation_value = str(edge.get("relation_value", "") or "")
            edge_label = f"ctx:{relation_value}" if relation_value else "context"
            color = _RELATION_FAMILY_COLORS["context"]
        elif relation == "artifact_contract":
            relation_value = str(edge.get("relation_value", "") or "")
            edge_label = f"artifact:{relation_value}" if relation_value else "artifact"
            color = _RELATION_FAMILY_COLORS["artifact"]
        elif relation == "phase_contract":
            relation_value = str(edge.get("relation_value", "") or "")
            edge_label = f"phase:{relation_value}" if relation_value else "phase"
            color = _RELATION_FAMILY_COLORS["phase"]
        else:
            edge_label = relation or "companion"
            color = _RELATION_FAMILY_COLORS["companion"]
        lines.append(
            f'  "{_dot_escape(source_key)}" -> "{_dot_escape(target_key)}" [label="{_dot_escape(edge_label)}", style="{style}", color="{color}"];'
        )
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_mermaid(path: Path, bundle: Mapping[str, Any]) -> None:
    nodes = list(bundle.get("nodes", ()))
    edges = list(bundle.get("edges", ()))
    key_to_id: dict[str, str] = {}
    lines: list[str] = ["flowchart LR"]

    def ensure_node(*, key: str, kind: str, title: str, missing: bool = False) -> str:
        if key in key_to_id:
            return key_to_id[key]
        node_id = f"N{len(key_to_id)}"
        key_to_id[key] = node_id
        label_parts = [key]
        if kind:
            label_parts.append(f"[{kind}]")
        if title:
            label_parts.append(title)
        label = "<br/>".join(_mermaid_escape(part) for part in label_parts if str(part).strip())
        lines.append(f'  {node_id}["{label}"]')
        class_name = "missing" if missing else (str(kind or "").strip().lower() or "unknown")
        lines.append(f"  class {node_id} {class_name};")
        return node_id

    for node in nodes:
        ensure_node(
            key=str(node.get("key", "") or ""),
            kind=str(node.get("kind", "") or ""),
            title=str(node.get("title", "") or ""),
        )

    for edge in edges:
        source_key = str(edge.get("source_key", "") or "")
        source_kind = str(edge.get("source_kind", "") or "")
        target_key = str(edge.get("target_key", "") or "")
        target_kind = str(edge.get("target_kind", "") or "")
        target_title = str(edge.get("target_title", "") or "")
        source_id = ensure_node(key=source_key, kind=source_kind, title="")
        target_id = ensure_node(
            key=target_key,
            kind=target_kind,
            title=target_title,
            missing=not bool(edge.get("target_in_catalog", False)),
        )
        relation = str(edge.get("relation", "") or "")
        relation_value = str(edge.get("relation_value", "") or "")
        if relation == "context_contract":
            label = f"ctx:{relation_value}" if relation_value else "context"
        elif relation == "artifact_contract":
            label = f"artifact:{relation_value}" if relation_value else "artifact"
        elif relation == "phase_contract":
            label = f"phase:{relation_value}" if relation_value else "phase"
        else:
            label = relation or "companion"
        lines.append(f'  {source_id} -- "{_mermaid_escape(label)}" --> {target_id}')

    lines.extend(
        [
            "  classDef adapter fill:#dbeafe,stroke:#334155,color:#0f172a;",
            "  classDef plugin fill:#fef3c7,stroke:#334155,color:#0f172a;",
            "  classDef bias fill:#dcfce7,stroke:#334155,color:#0f172a;",
            "  classDef representation fill:#fee2e2,stroke:#334155,color:#0f172a;",
            "  classDef suite fill:#ede9fe,stroke:#334155,color:#0f172a;",
            "  classDef tool fill:#e5e7eb,stroke:#334155,color:#0f172a;",
            "  classDef doc fill:#e0f2fe,stroke:#334155,color:#0f172a;",
            "  classDef example fill:#fae8ff,stroke:#334155,color:#0f172a;",
            "  classDef unknown fill:#f8fafc,stroke:#94a3b8,color:#0f172a;",
            "  classDef missing fill:#ffffff,stroke:#94a3b8,color:#475569,stroke-dasharray: 4 2;",
        ]
    )

    markdown = "\n".join(
        [
            "# Catalog Relation Graph",
            "",
            f"- profile: `{bundle.get('profile', 'default')}`",
            f"- scope: `{bundle.get('scope', 'framework')}`",
            f"- total nodes: `{bundle.get('summary', {}).get('total_nodes', 0)}`",
            f"- total edges: `{bundle.get('summary', {}).get('total_edges', 0)}`",
            "",
            "```mermaid",
            *lines,
            "```",
            "",
        ]
    )
    _ensure_parent(path)
    path.write_text(markdown, encoding="utf-8")


def _family_output_base(output_base: Path, family: str, suffix: str) -> Path:
    family_key = str(family or "").strip().lower() or "unknown"
    return output_base.with_suffix(f".family.{family_key}{suffix}")


def export_catalog_relations(
    *,
    output_path: str | Path | None = None,
    formats: Sequence[str] | None = None,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    query: str = "",
    search_field: str = "all",
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    normalized_formats = _normalize_export_formats(formats)
    bundle = build_catalog_relation_bundle(
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
        kind=kind,
        query=query,
        search_field=search_field,
        field_filters=field_filters,
        db_path=db_path,
        source_mode=source_mode,
    )
    output_base = _default_output_base(output_path=output_path, profile=profile, scope=scope, kind=kind)
    written_files: dict[str, str] = {}
    if "json" in normalized_formats:
        json_path = output_base if output_base.suffix.lower() == ".json" else output_base.with_suffix(".json")
        _write_json(json_path, bundle)
        written_files["json"] = str(json_path.resolve())
    if "table-csv" in normalized_formats:
        table_path = output_base if output_base.suffix.lower() == ".csv" else output_base.with_suffix(".table.csv")
        _write_table_csv(table_path, bundle.get("nodes", ()))
        written_files["table-csv"] = str(table_path.resolve())
    if "edge-csv" in normalized_formats:
        edge_path = output_base.with_suffix(".edges.csv")
        _write_edge_csv(edge_path, bundle.get("edges", ()))
        written_files["edge-csv"] = str(edge_path.resolve())
    if "key-csv" in normalized_formats:
        key_path = output_base.with_suffix(".relation_keys.csv")
        _write_key_csv(key_path, bundle.get("relation_keys", ()))
        written_files["key-csv"] = str(key_path.resolve())
    if "dot" in normalized_formats:
        dot_path = output_base.with_suffix(".dot")
        _write_dot(dot_path, bundle)
        written_files["dot"] = str(dot_path.resolve())
    if "mermaid" in normalized_formats:
        mermaid_path = output_base.with_suffix(".mermaid.md")
        _write_mermaid(mermaid_path, bundle)
        written_files["mermaid"] = str(mermaid_path.resolve())
    if "family-dot" in normalized_formats:
        family_written: dict[str, str] = {}
        for family in _RELATION_FAMILY_ORDER:
            family_bundle = _family_bundle(bundle, family)
            if int(dict(family_bundle.get("summary", {})).get("total_edges", 0) or 0) <= 0:
                continue
            family_path = _family_output_base(output_base, family, ".dot")
            _write_dot(family_path, family_bundle)
            family_written[family] = str(family_path.resolve())
        written_files["family-dot"] = family_written
    if "family-mermaid" in normalized_formats:
        family_written = {}
        for family in _RELATION_FAMILY_ORDER:
            family_bundle = _family_bundle(bundle, family)
            if int(dict(family_bundle.get("summary", {})).get("total_edges", 0) or 0) <= 0:
                continue
            family_path = _family_output_base(output_base, family, ".mermaid.md")
            _write_mermaid(family_path, family_bundle)
            family_written[family] = str(family_path.resolve())
        written_files["family-mermaid"] = family_written
    return {
        "profile": bundle.get("profile"),
        "scope": bundle.get("scope"),
        "kind": bundle.get("kind"),
        "query": bundle.get("query"),
        "search_field": bundle.get("search_field"),
        "source": bundle.get("source"),
        "summary": bundle.get("summary"),
        "formats": normalized_formats,
        "written_files": written_files,
    }
