from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..utils.engineering.run_contracts import (
    make_artifact_record,
    make_assembly_record,
    make_run_record,
    make_surface_record,
    stable_signature,
)


@dataclass(frozen=True, slots=True)
class FilesystemArtifactSpec:
    field_name: str
    suffix: str
    artifact_id: str
    artifact_kind: str
    artifact_role: str
    producer_ref: str
    fmt: str
    title: str


FILESYSTEM_ARTIFACT_SPECS: tuple[FilesystemArtifactSpec, ...] = (
    FilesystemArtifactSpec(
        field_name="summary_json_path",
        suffix=".summary.json",
        artifact_id="benchmark_summary_json",
        artifact_kind="summary",
        artifact_role="report",
        producer_ref="plugin:benchmark_harness",
        fmt="json",
        title="Benchmark Summary",
    ),
    FilesystemArtifactSpec(
        field_name="modules_json_path",
        suffix=".modules.json",
        artifact_id="modules_report_json",
        artifact_kind="module_report",
        artifact_role="report",
        producer_ref="plugin:module_report",
        fmt="json",
        title="Module Report",
    ),
    FilesystemArtifactSpec(
        field_name="bias_json_path",
        suffix=".bias.json",
        artifact_id="bias_report_json",
        artifact_kind="bias_report",
        artifact_role="report",
        producer_ref="plugin:module_report",
        fmt="json",
        title="Bias Report",
    ),
    FilesystemArtifactSpec(
        field_name="repro_bundle_json_path",
        suffix=".repro_bundle.json",
        artifact_id="repro_bundle_json",
        artifact_kind="repro_bundle",
        artifact_role="bundle",
        producer_ref="runtime:repro_bundle",
        fmt="json",
        title="Repro Bundle",
    ),
    FilesystemArtifactSpec(
        field_name="sequence_graph_json_path",
        suffix=".sequence_graph.json",
        artifact_id="sequence_graph_json",
        artifact_kind="sequence_graph",
        artifact_role="trace",
        producer_ref="plugin:sequence_graph",
        fmt="json",
        title="Sequence Graph",
    ),
    FilesystemArtifactSpec(
        field_name="decision_trace_summary_path",
        suffix=".decision_trace.summary.json",
        artifact_id="decision_trace_summary_json",
        artifact_kind="decision_trace_summary",
        artifact_role="trace",
        producer_ref="plugin:decision_trace",
        fmt="json",
        title="Decision Trace Summary",
    ),
    FilesystemArtifactSpec(
        field_name="decision_trace_jsonl_path",
        suffix=".decision_trace.jsonl",
        artifact_id="decision_trace_jsonl",
        artifact_kind="decision_trace",
        artifact_role="trace",
        producer_ref="plugin:decision_trace",
        fmt="jsonl",
        title="Decision Trace JSONL",
    ),
    FilesystemArtifactSpec(
        field_name="progress_csv_path",
        suffix=".csv",
        artifact_id="benchmark_progress_csv",
        artifact_kind="progress",
        artifact_role="progress",
        producer_ref="plugin:benchmark_harness",
        fmt="csv",
        title="Benchmark Progress",
    ),
)

_SPEC_BY_FIELD = {spec.field_name: spec for spec in FILESYSTEM_ARTIFACT_SPECS}


@dataclass(frozen=True, slots=True)
class FilesystemSurfaceTarget:
    root_path: str
    focus_run_id: str | None = None
    focus_artifact_id: str | None = None
    safe_label: str = ""


def _utc_iso_from_timestamp(timestamp: float | int | None) -> str | None:
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def default_artifact_root(root: str | Path | None = None) -> Path:
    base = Path(root) if root is not None else (Path.cwd() / "runs")
    return base.expanduser().resolve()


def _target_from_input(root: str | Path | None = None) -> FilesystemSurfaceTarget:
    resolved = default_artifact_root(root)
    focus_run_id: str | None = None
    focus_artifact_id: str | None = None
    root_path = resolved
    if resolved.exists() and resolved.is_file():
        run_id, spec = _split_run_artifact_path(resolved.name)
        root_path = resolved.parent
        if run_id is not None:
            focus_run_id = run_id
        if spec is not None:
            focus_artifact_id = spec.artifact_id
    safe_label = str(root_path)
    if focus_run_id:
        safe_label += f" :: {focus_run_id}"
    if focus_artifact_id:
        safe_label += f" :: {focus_artifact_id}"
    return FilesystemSurfaceTarget(
        root_path=str(root_path),
        focus_run_id=focus_run_id,
        focus_artifact_id=focus_artifact_id,
        safe_label=safe_label,
    )


def _split_run_artifact_path(name: str) -> tuple[str | None, FilesystemArtifactSpec | None]:
    for spec in FILESYSTEM_ARTIFACT_SPECS:
        if name.endswith(spec.suffix):
            return name[: -len(spec.suffix)], spec
    return None, None


def _json_load(path: str | None) -> Any:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _progress_tail(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return {}
    try:
        with file_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            last_row: dict[str, Any] | None = None
            for row in reader:
                payload = dict(row)
                if any(_text(value) for value in payload.values()):
                    last_row = payload
    except Exception:
        return {}
    return last_row or {}


def _plugin_names(modules_payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(modules_payload, Mapping):
        return ()
    plugins = modules_payload.get("plugins")
    if not isinstance(plugins, Sequence) or isinstance(plugins, (str, bytes)):
        return ()
    names: list[str] = []
    for item in plugins:
        if not isinstance(item, Mapping):
            continue
        text = _text(item.get("name") or item.get("class"))
        if text and text not in names:
            names.append(text)
    return tuple(names)


def _component_summary(modules_payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(modules_payload, Mapping):
        return ()
    out: list[str] = []
    solver = modules_payload.get("solver")
    adapter = modules_payload.get("adapter")
    pipeline = modules_payload.get("pipeline")
    if isinstance(solver, Mapping):
        text = _text(solver.get("class"))
        if text:
            out.append(f"solver={text}")
    if isinstance(adapter, Mapping):
        text = _text(adapter.get("class"))
        if text:
            out.append(f"adapter={text}")
    if isinstance(pipeline, Mapping):
        text = _text(pipeline.get("class"))
        if text:
            out.append(f"pipeline={text}")
    return tuple(out)


def _iter_grouped_artifacts(target: FilesystemSurfaceTarget) -> Iterable[dict[str, Any]]:
    artifact_root = Path(target.root_path)
    if not artifact_root.exists() or not artifact_root.is_dir():
        return ()

    grouped: dict[str, dict[str, Any]] = {}
    for path in artifact_root.rglob("*"):
        if not path.is_file():
            continue
        run_id, spec = _split_run_artifact_path(path.name)
        if run_id is None or spec is None:
            continue
        if target.focus_run_id and run_id != target.focus_run_id:
            continue
        if target.focus_artifact_id and spec.artifact_id != target.focus_artifact_id:
            continue
        row = grouped.setdefault(
            run_id,
            {
                "run_id": run_id,
                "artifact_root": str(artifact_root),
                "output_dir": str(path.parent.resolve()),
                "latest_mtime_ns": 0,
            },
        )
        row[spec.field_name] = str(path.resolve())
        row["latest_mtime_ns"] = max(int(row.get("latest_mtime_ns", 0) or 0), int(path.stat().st_mtime_ns))

    return tuple(grouped.values())


def _build_artifact_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    run_id = _text(row.get("run_id"))
    output_dir = _text(row.get("output_dir"))
    modules_payload = row.get("modules_payload") if isinstance(row.get("modules_payload"), Mapping) else {}
    plugin_names = tuple(row.get("plugin_names") or ())
    component_summary = tuple(row.get("component_summary") or ())
    surface_key = _text(row.get("surface_key"))
    assembly_signature = _text(row.get("assembly_signature"))

    artifact_rows: list[dict[str, Any]] = []
    for spec in FILESYSTEM_ARTIFACT_SPECS:
        path = _text(row.get(spec.field_name))
        if not path:
            continue
        file_path = Path(path)
        try:
            stat = file_path.stat()
            size_bytes = int(stat.st_size)
            created_at_utc = _utc_iso_from_timestamp(stat.st_mtime)
        except OSError:
            size_bytes = 0
            created_at_utc = None
        artifact_record = make_artifact_record(
            framework="nsgablack",
            run_id=run_id,
            artifact_id=spec.artifact_id,
            artifact_kind=spec.artifact_kind,
            artifact_role=spec.artifact_role,
            producer_ref=spec.producer_ref,
            surface_key=surface_key,
            assembly_signature=assembly_signature,
            path=path,
            format=spec.fmt,
            created_at_utc=created_at_utc,
            metrics_json={"size_bytes": size_bytes},
            metadata_json={
                "title": spec.title,
                "output_dir": output_dir,
                "plugin_names": list(plugin_names),
                "component_summary": list(component_summary),
                "modules_present": bool(modules_payload),
            },
            tags=("filesystem", spec.artifact_kind, spec.artifact_role),
        )
        artifact_rows.append(
            {
                "run_id": run_id,
                "artifact_id": spec.artifact_id,
                "artifact_role": spec.artifact_role,
                "producer_ref": spec.producer_ref,
                "surface_key": surface_key,
                "assembly_signature": assembly_signature,
                "artifact_record_json": artifact_record.to_dict(),
            }
        )
    artifact_rows.sort(key=lambda item: str(item.get("artifact_id") or ""))
    return artifact_rows


def _build_run_surface(raw: Mapping[str, Any]) -> dict[str, Any]:
    run_id = _text(raw.get("run_id"))
    output_dir = _text(raw.get("output_dir"))
    modules_payload = _json_load(_text(raw.get("modules_json_path")))
    summary_payload = _json_load(_text(raw.get("summary_json_path")))
    bias_payload = _json_load(_text(raw.get("bias_json_path")))
    repro_bundle_payload = _json_load(_text(raw.get("repro_bundle_json_path")))
    progress_tail = _progress_tail(_text(raw.get("progress_csv_path")))

    solver_class = ""
    adapter_class = ""
    pipeline_class = ""
    if isinstance(modules_payload, Mapping):
        solver = modules_payload.get("solver")
        adapter = modules_payload.get("adapter")
        pipeline = modules_payload.get("pipeline")
        solver_class = _text(solver.get("class")) if isinstance(solver, Mapping) else ""
        adapter_class = _text(adapter.get("class")) if isinstance(adapter, Mapping) else ""
        pipeline_class = _text(pipeline.get("class")) if isinstance(pipeline, Mapping) else ""

    status = _text((summary_payload or {}).get("status")) if isinstance(summary_payload, Mapping) else ""
    if not status:
        status = "completed" if progress_tail else "materialized"

    primary_metric_name = "best_score" if _text(progress_tail.get("best_score")) else ""
    primary_metric_value = _to_float(progress_tail.get("best_score"))
    if primary_metric_value is None:
        primary_metric_name = "best_objective" if _text(progress_tail.get("best_objective")) else primary_metric_name
        primary_metric_value = _to_float(progress_tail.get("best_objective"))

    surface_key = f"filesystem:{run_id}"
    driver_ref = adapter_class or "filesystem:unknown_adapter"
    family_ref = f"filesystem:{solver_class or 'run_artifacts'}"
    plugin_names = _plugin_names(modules_payload if isinstance(modules_payload, Mapping) else None)
    component_summary = _component_summary(modules_payload if isinstance(modules_payload, Mapping) else None)
    artifact_count = sum(1 for spec in FILESYSTEM_ARTIFACT_SPECS if _text(raw.get(spec.field_name)))

    surface_record = make_surface_record(
        framework="nsgablack",
        surface_kind="filesystem_run",
        surface_key=surface_key,
        surface_label=run_id,
        driver_ref=driver_ref,
        family_ref=family_ref,
        tags=("filesystem", "run_surface"),
        metadata_json={
            "artifact_root": _text(raw.get("artifact_root")),
            "output_dir": output_dir,
            "solver_class": solver_class,
            "adapter_class": adapter_class,
            "pipeline_class": pipeline_class,
        },
    )
    assembly_record = make_assembly_record(
        framework="nsgablack",
        surface_key=surface_key,
        assembly_key=f"filesystem:{run_id}",
        driver_ref=driver_ref,
        family_ref=family_ref,
        solver_ref=solver_class or None,
        adapter_ref=adapter_class or None,
        pipeline_refs=((pipeline_class,) if pipeline_class else ()),
        plugin_refs=plugin_names,
        component_refs=component_summary,
        mount_order=(*component_summary, *plugin_names),
        component_slots_json={
            "solver_class": solver_class,
            "adapter_class": adapter_class,
            "pipeline_class": pipeline_class,
        },
        metadata_json={
            "artifact_count": artifact_count,
            "output_dir": output_dir,
        },
    )
    artifact_rows = _build_artifact_rows(
        {
            **dict(raw),
            "run_id": run_id,
            "surface_key": surface_key,
            "assembly_signature": assembly_record.assembly_signature,
            "modules_payload": modules_payload,
            "plugin_names": plugin_names,
            "component_summary": component_summary,
        }
    )
    artifact_ids = tuple(str(item.get("artifact_id")) for item in artifact_rows if _text(item.get("artifact_id")))
    run_record = make_run_record(
        framework="nsgablack",
        run_id=run_id,
        status=status or "materialized",
        namespace="filesystem",
        tag="local_artifacts",
        surface_key=surface_key,
        surface_kind="filesystem_run",
        surface_signature=surface_record.surface_signature,
        assembly_signature=assembly_record.assembly_signature,
        subject_kind="artifact_root",
        subject_key=output_dir or _text(raw.get("artifact_root")),
        params_json={"source_backend": "filesystem"},
        driver_ref=driver_ref,
        family_ref=family_ref,
        output_dir=output_dir,
        primary_metric_name=primary_metric_name or None,
        primary_metric_value=primary_metric_value,
        metric_summary_json={
            "progress_tail": progress_tail,
            "summary_payload": summary_payload or {},
            "artifact_count": artifact_count,
        },
        result_json={
            "summary_payload": summary_payload or {},
            "bias_payload": bias_payload or {},
            "repro_bundle_payload": repro_bundle_payload or {},
            "progress_tail": progress_tail,
        },
        component_refs=(*component_summary, *plugin_names),
        artifact_ids=artifact_ids,
        metadata_json={
            "source_backend": "filesystem",
            "artifact_root": _text(raw.get("artifact_root")),
        },
    )

    latest_mtime_ns = int(raw.get("latest_mtime_ns", 0) or 0)
    finished_at_utc = _utc_iso_from_timestamp(latest_mtime_ns / 1_000_000_000 if latest_mtime_ns else None)

    return {
        "run_id": run_id,
        "namespace": "filesystem",
        "tag": "local_artifacts",
        "status": run_record.status,
        "surface_key": surface_key,
        "surface_kind": "filesystem_run",
        "driver_ref": driver_ref,
        "family_ref": family_ref,
        "assembly_signature": assembly_record.assembly_signature,
        "started_at_utc": None,
        "finished_at_utc": finished_at_utc,
        "duration_s": None,
        "subject_kind": run_record.subject_kind,
        "subject_key": run_record.subject_key,
        "primary_metric_name": run_record.primary_metric_name,
        "primary_metric_value": run_record.primary_metric_value,
        "output_dir": output_dir,
        "surface_record_json": surface_record.to_dict(),
        "assembly_record_json": assembly_record.to_dict(),
        "run_record_json": run_record.to_dict(),
        "artifact_records_json": [dict(item.get("artifact_record_json") or {}) for item in artifact_rows],
        "result_json": run_record.result_json,
        "artifact_rows": artifact_rows,
        "solver_class": solver_class,
        "adapter_class": adapter_class,
        "pipeline_class": pipeline_class,
        "summary_payload": summary_payload,
        "modules_payload": modules_payload,
        "bias_payload": bias_payload,
        "repro_bundle_payload": repro_bundle_payload,
        "progress_tail": progress_tail,
        "last_step": _text(progress_tail.get("step")),
        "last_best_score": _text(progress_tail.get("best_score")),
        "artifact_file_count": int(artifact_count),
        "plugin_names": plugin_names,
        "component_summary": component_summary,
        "selection_key": f"run:{run_id}",
        "source_backend": "filesystem",
        "latest_mtime_ns": latest_mtime_ns,
    }


def _iter_run_surfaces(target: FilesystemSurfaceTarget) -> tuple[dict[str, Any], ...]:
    rows = [_build_run_surface(raw) for raw in _iter_grouped_artifacts(target)]
    rows.sort(key=lambda item: (-int(item.get("latest_mtime_ns", 0) or 0), str(item.get("run_id") or "")))
    return tuple(rows)


def filesystem_surface_summary(root: str | Path | None = None) -> dict[str, Any]:
    target = _target_from_input(root)
    run_rows = _iter_run_surfaces(target)
    artifact_count = sum(len(tuple(row.get("artifact_rows") or ())) for row in run_rows)
    return {
        "backend": "filesystem",
        "target": target.safe_label,
        "tables": {
            "runtime_run_surface": len(run_rows),
            "runtime_artifact_surface": artifact_count,
        },
    }


def filesystem_surface_filter_values(root: str | Path | None = None) -> dict[str, list[str]]:
    target = _target_from_input(root)
    run_rows = _iter_run_surfaces(target)
    artifact_rows = [item for row in run_rows for item in tuple(row.get("artifact_rows") or ())]

    def _sorted_unique(values: Iterable[Any]) -> list[str]:
        clean = sorted({text for text in (_text(value) for value in values) if text})
        return clean

    return {
        "run_status": _sorted_unique(row.get("status") for row in run_rows),
        "run_surface_key": _sorted_unique(row.get("surface_key") for row in run_rows),
        "run_driver_ref": _sorted_unique(row.get("driver_ref") for row in run_rows),
        "run_family_ref": _sorted_unique(row.get("family_ref") for row in run_rows),
        "run_assembly_signature": _sorted_unique(row.get("assembly_signature") for row in run_rows),
        "artifact_role": _sorted_unique(row.get("artifact_role") for row in artifact_rows),
        "artifact_producer_ref": _sorted_unique(row.get("producer_ref") for row in artifact_rows),
        "artifact_surface_key": _sorted_unique(row.get("surface_key") for row in artifact_rows),
        "artifact_assembly_signature": _sorted_unique(row.get("assembly_signature") for row in artifact_rows),
    }


def list_filesystem_run_surfaces(
    root: str | Path | None = None,
    *,
    run_id: str | None = None,
    status: str | None = None,
    surface_key: str | None = None,
    driver_ref: str | None = None,
    family_ref: str | None = None,
    assembly_signature: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    target = _target_from_input(root)
    rows = list(_iter_run_surfaces(target))

    def _match(row: Mapping[str, Any]) -> bool:
        if run_id and _text(row.get("run_id")) != _text(run_id):
            return False
        if status and _text(row.get("status")) != _text(status):
            return False
        if surface_key and _text(row.get("surface_key")) != _text(surface_key):
            return False
        if driver_ref and _text(row.get("driver_ref")) != _text(driver_ref):
            return False
        if family_ref and _text(row.get("family_ref")) != _text(family_ref):
            return False
        if assembly_signature and _text(row.get("assembly_signature")) != _text(assembly_signature):
            return False
        return True

    return [row for row in rows if _match(row)][: max(1, int(limit))]


def list_filesystem_artifact_surfaces(
    root: str | Path | None = None,
    *,
    run_id: str | None = None,
    artifact_role: str | None = None,
    producer_ref: str | None = None,
    surface_key: str | None = None,
    assembly_signature: str | None = None,
    artifact_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    target = _target_from_input(root)
    run_rows = _iter_run_surfaces(target)
    artifact_rows = [item for row in run_rows for item in tuple(row.get("artifact_rows") or ())]

    def _match(row: Mapping[str, Any]) -> bool:
        if run_id and _text(row.get("run_id")) != _text(run_id):
            return False
        if artifact_role and _text(row.get("artifact_role")) != _text(artifact_role):
            return False
        if producer_ref and _text(row.get("producer_ref")) != _text(producer_ref):
            return False
        if surface_key and _text(row.get("surface_key")) != _text(surface_key):
            return False
        if assembly_signature and _text(row.get("assembly_signature")) != _text(assembly_signature):
            return False
        if artifact_id and _text(row.get("artifact_id")) != _text(artifact_id):
            return False
        return True

    artifact_rows.sort(key=lambda item: (str(item.get("run_id") or ""), str(item.get("artifact_id") or "")))
    return [row for row in artifact_rows if _match(row)][: max(1, int(limit))]


def show_filesystem_run_surface(root: str | Path | None, *, run_id: str) -> dict[str, Any] | None:
    rows = list_filesystem_run_surfaces(root, run_id=run_id, limit=1)
    return rows[0] if rows else None


def show_filesystem_artifact_surface(
    root: str | Path | None,
    *,
    run_id: str,
    artifact_id: str,
) -> dict[str, Any] | None:
    rows = list_filesystem_artifact_surfaces(root, run_id=run_id, artifact_id=artifact_id, limit=1)
    return rows[0] if rows else None


def discover_filesystem_run_surfaces(
    *,
    root: str | Path | None = None,
    query: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    text = _text(query).lower()
    rows = list_filesystem_run_surfaces(root, limit=max(1, int(limit)))
    if not text:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        fields = [
            _text(row.get("run_id")),
            _text(row.get("driver_ref")),
            _text(row.get("family_ref")),
            _text(row.get("output_dir")),
            " ".join(str(item) for item in tuple(((row.get("run_record_json") or {}).get("component_refs")) or ())),
        ]
        if any(text in field.lower() for field in fields if field):
            filtered.append(row)
    return filtered[: max(1, int(limit))]


__all__ = [
    "FILESYSTEM_ARTIFACT_SPECS",
    "FilesystemArtifactSpec",
    "FilesystemSurfaceTarget",
    "default_artifact_root",
    "discover_filesystem_run_surfaces",
    "filesystem_surface_filter_values",
    "filesystem_surface_summary",
    "list_filesystem_artifact_surfaces",
    "list_filesystem_run_surfaces",
    "show_filesystem_artifact_surface",
    "show_filesystem_run_surface",
]
