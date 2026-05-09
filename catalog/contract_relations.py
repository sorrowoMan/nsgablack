from __future__ import annotations

from typing import Any, Mapping, Sequence

from .registry import CatalogEntry

_RELATION_SPEC_ORDER: tuple[dict[str, str], ...] = (
    {
        "family": "context",
        "provider_field": "context_provides",
        "consumer_field": "context_requires",
        "provider_group": "context_provides",
        "consumer_group": "context_requires",
        "relation": "context_contract",
        "provider_label": "产物 -> {value} -> 消费者",
        "consumer_label": "依赖 <- {value} <- 生产者",
        "provider_note": "消费上下文产物：{value}",
        "consumer_note": "提供所需上下文：{value}",
        "family_label": "上下文链路",
    },
    {
        "family": "artifact",
        "provider_field": "artifact_provides",
        "consumer_field": "artifact_requires",
        "provider_group": "artifact_provides",
        "consumer_group": "artifact_requires",
        "relation": "artifact_contract",
        "provider_label": "Artifact -> {value} -> 消费者",
        "consumer_label": "Artifact 依赖 <- {value} <- 生产者",
        "provider_note": "消费 artifact 产物：{value}",
        "consumer_note": "提供所需 artifact：{value}",
        "family_label": "Artifact 链路",
    },
    {
        "family": "phase",
        "provider_field": "phase_out",
        "consumer_field": "phase_in",
        "provider_group": "phase_out",
        "consumer_group": "phase_in",
        "relation": "phase_contract",
        "provider_label": "Phase Out -> {value} -> 下游",
        "consumer_label": "Phase In <- {value} <- 上游",
        "provider_note": "进入该阶段后继续流转：{value}",
        "consumer_note": "依赖该阶段输入：{value}",
        "family_label": "Phase 链路",
    },
)
_RELATION_FAMILY_ORDER: tuple[str, ...] = tuple(str(spec["family"]) for spec in _RELATION_SPEC_ORDER)


def normalize_relation_values(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        text = str(values).strip()
        return (text,) if text else ()
    if isinstance(values, Mapping):
        out = []
        for key in values.keys():
            text = str(key).strip()
            if text:
                out.append(text)
        return tuple(sorted(set(out)))
    if isinstance(values, (list, tuple, set, frozenset)):
        out = []
        for item in values:
            text = str(item).strip()
            if text:
                out.append(text)
        return tuple(sorted(set(out)))
    text = str(values).strip()
    return (text,) if text else ()


def _unique_sorted(*groups: object) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in normalize_relation_values(group):
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
    return tuple(sorted(out))


def _is_artifact_key(value: str) -> bool:
    key = str(value or "").strip().lower()
    if not key:
        return False
    return key.endswith("_ref") or key == "snapshot_key" or key.endswith("_path") or ".path" in key


def _is_phase_key(value: str) -> bool:
    key = str(value or "").strip().lower()
    if not key:
        return False
    return key == "phase" or key == "phase_id" or "phase" in key


def _entry_field_values(entry: CatalogEntry, field_name: str) -> tuple[str, ...]:
    key = str(field_name or "").strip()
    if key.startswith("context_"):
        return normalize_relation_values(getattr(entry, key, ()))

    explicit = normalize_relation_values(getattr(entry, key, ()))
    context_requires = normalize_relation_values(getattr(entry, "context_requires", ()))
    context_provides = normalize_relation_values(getattr(entry, "context_provides", ()))
    context_mutates = normalize_relation_values(getattr(entry, "context_mutates", ()))

    if key == "artifact_requires":
        inferred = tuple(value for value in context_requires if _is_artifact_key(value))
        return _unique_sorted(explicit, inferred)
    if key == "artifact_provides":
        inferred = tuple(value for value in (*context_provides, *context_mutates) if _is_artifact_key(value))
        return _unique_sorted(explicit, inferred)
    if key == "phase_in":
        inferred = tuple(value for value in context_requires if _is_phase_key(value))
        return _unique_sorted(explicit, inferred)
    if key == "phase_out":
        inferred = tuple(value for value in (*context_provides, *context_mutates) if _is_phase_key(value))
        return _unique_sorted(explicit, inferred)
    return explicit


def enrich_entry_relation_fields(entry: CatalogEntry) -> CatalogEntry:
    artifact_requires = _entry_field_values(entry, "artifact_requires")
    artifact_provides = _entry_field_values(entry, "artifact_provides")
    phase_in = _entry_field_values(entry, "phase_in")
    phase_out = _entry_field_values(entry, "phase_out")
    if (
        tuple(getattr(entry, "artifact_requires", ()) or ()) == artifact_requires
        and tuple(getattr(entry, "artifact_provides", ()) or ()) == artifact_provides
        and tuple(getattr(entry, "phase_in", ()) or ()) == phase_in
        and tuple(getattr(entry, "phase_out", ()) or ()) == phase_out
    ):
        return entry
    return CatalogEntry(
        key=entry.key,
        title=entry.title,
        kind=entry.kind,
        import_path=entry.import_path,
        tags=tuple(entry.tags),
        summary=entry.summary,
        companions=tuple(entry.companions),
        context_requires=tuple(entry.context_requires),
        context_provides=tuple(entry.context_provides),
        context_mutates=tuple(entry.context_mutates),
        context_cache=tuple(entry.context_cache),
        context_notes=tuple(entry.context_notes),
        artifact_requires=artifact_requires,
        artifact_provides=artifact_provides,
        phase_in=phase_in,
        phase_out=phase_out,
        use_when=tuple(entry.use_when),
        minimal_wiring=tuple(entry.minimal_wiring),
        required_companions=tuple(entry.required_companions),
        config_keys=tuple(entry.config_keys),
        example_entry=str(entry.example_entry or ""),
        detail_ref=str(entry.detail_ref or ""),
    )


def _relation_family_sort_index(family: str) -> int:
    key = str(family or "").strip()
    return _RELATION_FAMILY_ORDER.index(key) if key in _RELATION_FAMILY_ORDER else 99


def _relation_note(spec: Mapping[str, str], *, role: str, value: str) -> str:
    if role == "consumer":
        template = str(spec.get("provider_note", "") or "").strip()
    elif role == "producer":
        template = str(spec.get("consumer_note", "") or "").strip()
    else:
        template = ""
    return template.format(value=value) if template else ""


def relation_entry_payload(
    entry: CatalogEntry,
    *,
    contract_value: str | None = None,
    relation_role: str | None = None,
    relation_family: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": entry.key,
        "title": entry.title,
        "kind": entry.kind,
        "summary": entry.summary,
    }
    value = str(contract_value or "").strip()
    if value:
        payload["contract_value"] = value
        payload["relation_key"] = value
        payload["contract_key"] = value
        payload["context_key"] = value
    role = str(relation_role or "").strip()
    family = str(relation_family or "").strip()
    if family:
        payload["relation_family"] = family
    spec = next((item for item in _RELATION_SPEC_ORDER if str(item["family"]) == family), {})
    if role:
        payload["relation_role"] = role
        note = _relation_note(spec, role=role, value=value)
        if note:
            payload["relation_note"] = note
    return payload


def _sorted_unique_entries(entries: Sequence[CatalogEntry], *, skip_key: str = "") -> list[CatalogEntry]:
    unique: dict[str, CatalogEntry] = {}
    for entry in entries:
        if entry.key == skip_key:
            continue
        unique[entry.key] = enrich_entry_relation_fields(entry)
    return sorted(unique.values(), key=lambda item: (str(item.kind), str(item.key)))


def _relation_card_payload(
    *,
    spec: Mapping[str, str],
    direction: str,
    value: str,
    group_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if direction == "out":
        title = str(spec.get("provider_label", "{value}").format(value=value))
    else:
        title = str(spec.get("consumer_label", "{value}").format(value=value))
    return {
        "group_id": group_id,
        "family": str(spec.get("family", "") or ""),
        "family_label": str(spec.get("family_label", "") or ""),
        "direction": direction,
        "value": value,
        "title": title,
        "count": len(rows),
        "preview_items": tuple(rows[:3]),
    }


def _relation_chain_payload(
    *,
    spec: Mapping[str, str],
    value: str,
    incoming_group_id: str = "",
    incoming_rows: Sequence[Mapping[str, Any]] = (),
    outgoing_group_id: str = "",
    outgoing_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    incoming_preview = tuple(incoming_rows[:3])
    outgoing_preview = tuple(outgoing_rows[:3])
    return {
        "family": str(spec.get("family", "") or ""),
        "family_label": str(spec.get("family_label", "") or ""),
        "value": value,
        "title": value,
        "incoming_group_id": incoming_group_id,
        "incoming_label": str(spec.get("consumer_label", "{value}").format(value=value)),
        "incoming_count": len(incoming_rows),
        "incoming_preview_items": incoming_preview,
        "outgoing_group_id": outgoing_group_id,
        "outgoing_label": str(spec.get("provider_label", "{value}").format(value=value)),
        "outgoing_count": len(outgoing_rows),
        "outgoing_preview_items": outgoing_preview,
        "total_count": len(incoming_rows) + len(outgoing_rows),
    }


def build_contract_neighbor_sections(
    entry: CatalogEntry,
    *,
    candidates: Sequence[CatalogEntry] = (),
) -> dict[str, Any]:
    current = enrich_entry_relation_fields(entry)
    related_entries = _sorted_unique_entries(candidates, skip_key=current.key)
    candidate_fields = {
        candidate.key: {
            spec["provider_field"]: set(_entry_field_values(candidate, spec["provider_field"]))
            for spec in _RELATION_SPEC_ORDER
        }
        for candidate in related_entries
    }
    candidate_fields_in = {
        candidate.key: {
            spec["consumer_field"]: set(_entry_field_values(candidate, spec["consumer_field"]))
            for spec in _RELATION_SPEC_ORDER
        }
        for candidate in related_entries
    }

    relation_groups: dict[str, list[dict[str, Any]]] = {}
    relation_labels: dict[str, str] = {}
    relation_cards: list[dict[str, Any]] = []
    relation_chain_index: dict[tuple[str, str], dict[str, Any]] = {}

    for spec in _RELATION_SPEC_ORDER:
        provider_field = str(spec["provider_field"])
        consumer_field = str(spec["consumer_field"])
        provider_group = str(spec["provider_group"])
        consumer_group = str(spec["consumer_group"])
        family = str(spec["family"])

        for value in _entry_field_values(current, provider_field):
            rows = [
                relation_entry_payload(
                    candidate,
                    contract_value=value,
                    relation_role="consumer",
                    relation_family=family,
                )
                for candidate in related_entries
                if value in candidate_fields_in.get(candidate.key, {}).get(consumer_field, set())
            ]
            group_id = f"{provider_group}::{value}"
            relation_labels[group_id] = str(spec["provider_label"]).format(value=value)
            if rows:
                relation_groups[group_id] = rows
                relation_cards.append(
                    _relation_card_payload(spec=spec, direction="out", value=value, group_id=group_id, rows=rows)
                )
                relation_chain_index.setdefault((family, value), {})["outgoing_group_id"] = group_id
                relation_chain_index[(family, value)]["outgoing_rows"] = tuple(rows)

        for value in _entry_field_values(current, consumer_field):
            rows = [
                relation_entry_payload(
                    candidate,
                    contract_value=value,
                    relation_role="producer",
                    relation_family=family,
                )
                for candidate in related_entries
                if value in candidate_fields.get(candidate.key, {}).get(provider_field, set())
            ]
            group_id = f"{consumer_group}::{value}"
            relation_labels[group_id] = str(spec["consumer_label"]).format(value=value)
            if rows:
                relation_groups[group_id] = rows
                relation_cards.append(
                    _relation_card_payload(spec=spec, direction="in", value=value, group_id=group_id, rows=rows)
                )
                relation_chain_index.setdefault((family, value), {})["incoming_group_id"] = group_id
                relation_chain_index[(family, value)]["incoming_rows"] = tuple(rows)

    relation_cards.sort(
        key=lambda item: (
            _relation_family_sort_index(str(item.get("family", ""))),
            0 if str(item.get("direction", "")) == "out" else 1,
            str(item.get("value", "")),
        )
    )
    relation_chain_cards: list[dict[str, Any]] = []
    for spec in _RELATION_SPEC_ORDER:
        family = str(spec["family"])
        family_values = sorted(
            value
            for rel_family, value in relation_chain_index.keys()
            if rel_family == family
        )
        for value in family_values:
            state = relation_chain_index.get((family, value), {})
            incoming_rows = tuple(state.get("incoming_rows", ()) or ())
            outgoing_rows = tuple(state.get("outgoing_rows", ()) or ())
            if not incoming_rows and not outgoing_rows:
                continue
            relation_chain_cards.append(
                _relation_chain_payload(
                    spec=spec,
                    value=value,
                    incoming_group_id=str(state.get("incoming_group_id", "") or ""),
                    incoming_rows=incoming_rows,
                    outgoing_group_id=str(state.get("outgoing_group_id", "") or ""),
                    outgoing_rows=outgoing_rows,
                )
            )

    return {
        "relation_groups": relation_groups,
        "relation_labels": relation_labels,
        "relation_cards": tuple(relation_cards),
        "relation_chain_cards": tuple(relation_chain_cards),
    }


def build_contract_edge_rows(
    *,
    source_entries: Sequence[CatalogEntry],
    consumer_candidates: Sequence[CatalogEntry],
    filtered_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    candidates = [enrich_entry_relation_fields(entry) for entry in consumer_candidates]
    consumers_by_spec: dict[tuple[str, str], dict[str, list[CatalogEntry]]] = {}
    for spec in _RELATION_SPEC_ORDER:
        consumer_field = str(spec["consumer_field"])
        provider_field = str(spec["provider_field"])
        bucket: dict[str, list[CatalogEntry]] = {}
        for candidate in candidates:
            for value in _entry_field_values(candidate, consumer_field):
                bucket.setdefault(value, []).append(candidate)
        consumers_by_spec[(provider_field, consumer_field)] = bucket

    seen: set[tuple[str, str, str, str]] = set()
    edges: list[dict[str, Any]] = []
    exported_keys = set(filtered_keys or ())
    for source in [enrich_entry_relation_fields(entry) for entry in source_entries]:
        for spec in _RELATION_SPEC_ORDER:
            provider_field = str(spec["provider_field"])
            consumer_field = str(spec["consumer_field"])
            relation_name = str(spec["relation"])
            for value in _entry_field_values(source, provider_field):
                for target in consumers_by_spec.get((provider_field, consumer_field), {}).get(value, ()):
                    if target.key == source.key:
                        continue
                    token = (source.key, target.key, relation_name, value)
                    if token in seen:
                        continue
                    seen.add(token)
                    edges.append(
                        {
                            "source_key": source.key,
                            "source_kind": source.kind,
                            "target_key": target.key,
                            "target_kind": target.kind,
                            "target_title": target.title,
                            "target_in_catalog": True,
                            "target_in_export": target.key in exported_keys,
                            "relation": relation_name,
                            "relation_field": f"{provider_field}->{consumer_field}",
                            "relation_value": value,
                            "relation_family": str(spec["family"]),
                        }
                    )
    edges.sort(
        key=lambda item: (
            str(item.get("source_kind", "")),
            str(item.get("source_key", "")),
            str(item.get("target_key", "")),
            str(item.get("relation", "")),
            str(item.get("relation_value", "")),
        )
    )
    return edges
