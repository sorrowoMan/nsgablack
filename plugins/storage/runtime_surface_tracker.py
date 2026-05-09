"""Runtime surface tracker plugin.

Persists the formal run-surface contract into the resolved experiment DB target
and also injects the resolved records into ``result["run_surface"]`` for
immediate consumption by UI / tooling layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import uuid
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from ..base import Plugin
from ...experiment.db import (
    ensure_table_columns,
    first_column_texts,
    open_experiment_db,
    resolve_experiment_db_target,
    table_columns,
    table_count,
    table_exists,
)
from ...catalog import get_catalog
from ...project.catalog import find_project_root
from ...utils.context.context_contracts import collect_solver_contracts, detect_context_conflicts
from ...utils.engineering.run_contracts import (
    ArtifactRecord,
    AssemblyRecord,
    RunRecord,
    SurfaceRecord,
    make_artifact_record,
    make_assembly_record,
    make_run_record,
    make_surface_record,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "shape"):
        try:
            shape = list(getattr(value, "shape"))
        except Exception:
            shape = []
        return {
            "type": type(value).__name__,
            "shape": shape,
        }
    if hasattr(value, "tolist") and callable(getattr(value, "tolist", None)):
        try:
            return _to_jsonable(value.tolist())
        except Exception:
            pass
    if hasattr(value, "item") and callable(getattr(value, "item", None)):
        try:
            return _to_jsonable(value.item())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {str(k): _to_jsonable(v) for k, v in vars(value).items() if not str(k).startswith("_")}
        except Exception:
            pass
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False, sort_keys=True)


def _json_loads(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _mapping(value: Any) -> dict[str, Any]:
    return {str(key): raw for key, raw in dict(value).items()} if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in tuple(value) if isinstance(item, Mapping)]


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return float(number)


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _text(value)
        if text is not None:
            return text
    return None


def _run_like_payload(result_payload: Mapping[str, Any]) -> dict[str, Any]:
    result = _mapping(result_payload)
    for key in ("run_summary", "best_run", "locked_best_run", "unlocked_best_run"):
        payload = _mapping(result.get(key))
        if payload:
            return payload
    payload = _mapping(result.get("payload"))
    if payload:
        nested = _mapping(payload.get("run_summary"))
        if nested:
            return nested
    return {}


def _selected_core_rows_from_result(result_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = _mapping(result_payload)
    run_payload = _run_like_payload(result)
    for candidate in (
        _mapping(result.get("core_selection")),
        _mapping(_mapping(result.get("payload")).get("core_selection")),
        _mapping(run_payload.get("core_selection")),
    ):
        rows = _sequence_of_mappings(candidate.get("selected_core_rows"))
        if rows:
            return rows
    prior_rows = _sequence_of_mappings(run_payload.get("consensus_prior_rows"))
    if prior_rows:
        return prior_rows
    return []


def _augment_runtime_run_surface_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(payload)
    result_payload = _mapping(row.get("result_json"))
    run_payload = _run_like_payload(result_payload)
    search_summary = _mapping(run_payload.get("search_summary"))
    structure_engine = _mapping(run_payload.get("structure_engine"))
    structure_engine_meta = _mapping(structure_engine.get("metadata"))
    lane_context = _mapping(
        result_payload.get("heterogeneous_multi_lane_context")
        or run_payload.get("heterogeneous_multi_lane_context")
        or _mapping(run_payload.get("heterogeneous_lane_consensus")).get("lane_spec")
    )
    lane_consensus = _mapping(
        result_payload.get("heterogeneous_lane_consensus")
        or run_payload.get("heterogeneous_lane_consensus")
    )
    selected_core_rows = _selected_core_rows_from_result(result_payload)
    joint_scores = [
        score
        for score in (_float_or_none(row.get("joint_core_score")) for row in selected_core_rows)
        if score is not None
    ]
    cross_lane_scores = [
        score
        for score in (_float_or_none(row.get("cross_lane_stability")) for row in selected_core_rows)
        if score is not None
    ]
    cross_lane_support_rates = [
        score
        for score in (_float_or_none(row.get("cross_lane_support_rate")) for row in selected_core_rows)
        if score is not None
    ]
    cross_lane_family_support_rates = [
        score
        for score in (_float_or_none(row.get("cross_lane_family_support_rate")) for row in selected_core_rows)
        if score is not None
    ]
    direct_joint_core_score = _float_or_none(result_payload.get("joint_core_score"))

    row["search_driver"] = _first_text(
        result_payload.get("search_driver"),
        run_payload.get("search_driver"),
        structure_engine.get("search_driver"),
    )
    row["screening_protocol"] = _first_text(
        result_payload.get("screening_protocol"),
        run_payload.get("screening_protocol"),
        search_summary.get("screening_protocol"),
        structure_engine.get("screening_protocol"),
        structure_engine_meta.get("screening_protocol"),
    )
    row["outer_search_protocol"] = _first_text(
        result_payload.get("outer_search_protocol"),
        run_payload.get("outer_search_protocol"),
        search_summary.get("outer_search_protocol"),
        structure_engine.get("outer_search_protocol"),
        structure_engine_meta.get("outer_search_protocol"),
        search_summary.get("protocol"),
    )
    row["structure_head"] = _first_text(
        result_payload.get("structure_head"),
        run_payload.get("structure_head"),
        structure_engine.get("structure_head"),
        structure_engine_meta.get("structure_head"),
    )
    row["search_input_space"] = _first_text(
        result_payload.get("search_input_space"),
        run_payload.get("search_input_space"),
        structure_engine.get("search_input_space"),
        structure_engine_meta.get("search_input_space"),
    )
    row["pool_expansion_unit"] = _first_text(
        result_payload.get("pool_expansion_unit"),
        run_payload.get("pool_expansion_unit"),
        structure_engine.get("pool_expansion_unit"),
        structure_engine_meta.get("pool_expansion_unit"),
    )
    row["gradient_guidance_mode"] = _first_text(
        result_payload.get("gradient_guidance_mode"),
        run_payload.get("gradient_guidance_mode"),
        structure_engine.get("gradient_guidance_mode"),
        structure_engine_meta.get("gradient_guidance_mode"),
    )
    row["basis_binding_mode"] = _first_text(
        result_payload.get("basis_binding_mode"),
        run_payload.get("basis_binding_mode"),
    )
    row["escape_policy"] = _first_text(
        result_payload.get("escape_policy"),
        run_payload.get("escape_policy"),
    )
    row["equivalence_expression_protocol"] = _first_text(
        result_payload.get("equivalence_expression_protocol"),
        run_payload.get("equivalence_expression_protocol"),
        _mapping(result_payload.get("equivalence_expression_handling")).get("protocol"),
        _mapping(run_payload.get("equivalence_expression_handling")).get("protocol"),
    )
    row["equivalence_expression_mode"] = _first_text(
        result_payload.get("equivalence_expression_mode"),
        run_payload.get("equivalence_expression_mode"),
        _mapping(result_payload.get("equivalence_expression_handling")).get("mode"),
        _mapping(run_payload.get("equivalence_expression_handling")).get("mode"),
    )
    row["equivalence_class_scope"] = _first_text(
        result_payload.get("equivalence_class_scope"),
        run_payload.get("equivalence_class_scope"),
        _mapping(result_payload.get("equivalence_expression_handling")).get("class_scope"),
        _mapping(run_payload.get("equivalence_expression_handling")).get("class_scope"),
    )
    row["interference_feature_protocol"] = _first_text(
        result_payload.get("interference_feature_protocol"),
        run_payload.get("interference_feature_protocol"),
        _mapping(result_payload.get("interference_feature_handling")).get("protocol"),
        _mapping(run_payload.get("interference_feature_handling")).get("protocol"),
    )
    row["interference_feature_mode"] = _first_text(
        result_payload.get("interference_feature_mode"),
        run_payload.get("interference_feature_mode"),
        _mapping(result_payload.get("interference_feature_handling")).get("mode"),
        _mapping(run_payload.get("interference_feature_handling")).get("mode"),
    )
    row["cross_explanatory_rejection_mode"] = _first_text(
        result_payload.get("cross_explanatory_rejection_mode"),
        run_payload.get("cross_explanatory_rejection_mode"),
        _mapping(result_payload.get("interference_feature_handling")).get("cross_explanatory_rejection_mode"),
        _mapping(run_payload.get("interference_feature_handling")).get("cross_explanatory_rejection_mode"),
    )
    row["trivial_nonlinearity_penalty_mode"] = _first_text(
        result_payload.get("trivial_nonlinearity_penalty_mode"),
        run_payload.get("trivial_nonlinearity_penalty_mode"),
        _mapping(result_payload.get("interference_feature_handling")).get("trivial_nonlinearity_penalty_mode"),
        _mapping(run_payload.get("interference_feature_handling")).get("trivial_nonlinearity_penalty_mode"),
    )
    row["environment_invariance_audit_mode"] = _first_text(
        result_payload.get("environment_invariance_audit_mode"),
        run_payload.get("environment_invariance_audit_mode"),
        _mapping(result_payload.get("interference_feature_handling")).get("environment_invariance_audit_mode"),
        _mapping(run_payload.get("interference_feature_handling")).get("environment_invariance_audit_mode"),
    )
    row["proxy_group_policy"] = _first_text(
        result_payload.get("proxy_group_policy"),
        run_payload.get("proxy_group_policy"),
        _mapping(result_payload.get("interference_feature_handling")).get("proxy_group_policy"),
        _mapping(run_payload.get("interference_feature_handling")).get("proxy_group_policy"),
    )
    row["source_overlap_penalty_mode"] = _first_text(
        result_payload.get("source_overlap_penalty_mode"),
        run_payload.get("source_overlap_penalty_mode"),
        _mapping(result_payload.get("interference_feature_handling")).get("source_overlap_penalty_mode"),
        _mapping(run_payload.get("interference_feature_handling")).get("source_overlap_penalty_mode"),
    )
    row["heterogeneous_multi_lane_protocol"] = _first_text(
        result_payload.get("heterogeneous_multi_lane_protocol"),
        run_payload.get("heterogeneous_multi_lane_protocol"),
        lane_context.get("protocol"),
    )
    row["lane_id"] = _first_text(
        result_payload.get("lane_id"),
        run_payload.get("lane_id"),
        lane_consensus.get("lane_id"),
        lane_context.get("lane_id"),
    )
    row["lane_family"] = _first_text(
        result_payload.get("lane_family"),
        run_payload.get("lane_family"),
        lane_consensus.get("lane_family"),
        lane_context.get("lane_family"),
    )
    row["challenger_objective_protocol"] = _first_text(
        result_payload.get("challenger_objective_protocol"),
        run_payload.get("challenger_objective_protocol"),
        lane_consensus.get("challenger_objective_protocol"),
        lane_context.get("challenger_objective_protocol"),
    )
    row["pool_expansion_bias_protocol"] = _first_text(
        result_payload.get("pool_expansion_bias_protocol"),
        run_payload.get("pool_expansion_bias_protocol"),
        lane_consensus.get("pool_expansion_bias_protocol"),
        lane_context.get("pool_expansion_bias_protocol"),
    )
    row["consensus_prior_row_count"] = int(
        _float_or_none(result_payload.get("consensus_prior_row_count")) or 0
    )
    if int(row["consensus_prior_row_count"]) <= 0:
        row["consensus_prior_row_count"] = int(
            len(_sequence_of_mappings(run_payload.get("consensus_prior_rows")))
            or _float_or_none(_mapping(search_summary.get("consensus_prior_summary")).get("row_count"))
            or 0
        )
    row["joint_core_score"] = (
        direct_joint_core_score
        if direct_joint_core_score is not None
        else (None if not joint_scores else float(max(joint_scores)))
    )
    row["joint_core_score_mean"] = (
        None if not joint_scores else float(sum(joint_scores) / float(len(joint_scores)))
    )
    row["cross_lane_stability"] = (
        _float_or_none(result_payload.get("cross_lane_stability"))
        if _float_or_none(result_payload.get("cross_lane_stability")) is not None
        else _float_or_none(lane_consensus.get("cross_lane_stability"))
        if _float_or_none(lane_consensus.get("cross_lane_stability")) is not None
        else None if not cross_lane_scores else float(max(cross_lane_scores))
    )
    row["cross_lane_support_rate"] = (
        _float_or_none(lane_consensus.get("cross_lane_support_rate"))
        if _float_or_none(lane_consensus.get("cross_lane_support_rate")) is not None
        else None if not cross_lane_support_rates else float(max(cross_lane_support_rates))
    )
    row["cross_lane_family_support_rate"] = (
        _float_or_none(lane_consensus.get("cross_lane_family_support_rate"))
        if _float_or_none(lane_consensus.get("cross_lane_family_support_rate")) is not None
        else None
        if not cross_lane_family_support_rates
        else float(max(cross_lane_family_support_rates))
    )
    row["selected_core_row_count"] = int(len(selected_core_rows))
    return row


def _catalog_key_to_ref(key: str | None, *, fallback_prefix: str) -> str | None:
    text = _text(key)
    if text is None:
        return None
    if ":" in text:
        return text
    if "." in text:
        prefix, rest = text.split(".", 1)
        return f"{prefix}:{rest}"
    return f"{fallback_prefix}:{text}"


def _dedupe(values: Iterable[str | None]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text is None or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _compact_result_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in dict(result).items():
        if str(key) == "artifacts" and isinstance(value, Mapping):
            payload[str(key)] = {str(k): _to_jsonable(v) for k, v in value.items()}
            continue
        payload[str(key)] = _to_jsonable(value)
    return payload


def ensure_runtime_surface_schema(conn: Any) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_run_surface (
            run_id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            tag TEXT,
            status TEXT NOT NULL,
            surface_key TEXT,
            surface_kind TEXT,
            driver_ref TEXT,
            family_ref TEXT,
            assembly_signature TEXT,
            started_at_utc TEXT,
            finished_at_utc TEXT,
            duration_s REAL,
            subject_kind TEXT,
            subject_key TEXT,
            primary_metric_name TEXT,
            primary_metric_value REAL,
            output_dir TEXT,
            surface_record_json TEXT NOT NULL,
            assembly_record_json TEXT NOT NULL,
            run_record_json TEXT NOT NULL,
            artifact_records_json TEXT,
            result_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_artifact_surface (
            run_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            artifact_role TEXT,
            producer_ref TEXT,
            surface_key TEXT,
            assembly_signature TEXT,
            artifact_record_json TEXT NOT NULL,
            PRIMARY KEY (run_id, artifact_id)
        )
        """
    )
    ensure_table_columns(
        conn,
        "runtime_run_surface",
        {
            "artifact_records_json": "TEXT",
            "result_json": "TEXT",
        },
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_run_surface_surface_key ON runtime_run_surface(surface_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_run_surface_driver_ref ON runtime_run_surface(driver_ref)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_run_surface_assembly_signature ON runtime_run_surface(assembly_signature)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_artifact_surface_role ON runtime_artifact_surface(artifact_role)"
    )


def persist_runtime_surface_records(
    db_path: str | Path,
    *,
    surface_record: SurfaceRecord,
    assembly_record: AssemblyRecord,
    run_record: RunRecord,
    artifact_records: Sequence[ArtifactRecord] = (),
    result_payload: Mapping[str, Any] | None = None,
) -> None:
    artifact_rows = [record.to_dict() for record in tuple(artifact_records or ())]
    compact_result = _compact_result_payload(result_payload or {})
    with _connect_runtime_surface_db(db_path) as conn:
        ensure_runtime_surface_schema(conn)
        conn.execute(
            """
            INSERT INTO runtime_run_surface (
                run_id, namespace, tag, status, surface_key, surface_kind, driver_ref, family_ref,
                assembly_signature, started_at_utc, finished_at_utc, duration_s, subject_kind,
                subject_key, primary_metric_name, primary_metric_value, output_dir,
                surface_record_json, assembly_record_json, run_record_json, artifact_records_json, result_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                namespace=excluded.namespace,
                tag=excluded.tag,
                status=excluded.status,
                surface_key=excluded.surface_key,
                surface_kind=excluded.surface_kind,
                driver_ref=excluded.driver_ref,
                family_ref=excluded.family_ref,
                assembly_signature=excluded.assembly_signature,
                started_at_utc=excluded.started_at_utc,
                finished_at_utc=excluded.finished_at_utc,
                duration_s=excluded.duration_s,
                subject_kind=excluded.subject_kind,
                subject_key=excluded.subject_key,
                primary_metric_name=excluded.primary_metric_name,
                primary_metric_value=excluded.primary_metric_value,
                output_dir=excluded.output_dir,
                surface_record_json=excluded.surface_record_json,
                assembly_record_json=excluded.assembly_record_json,
                run_record_json=excluded.run_record_json,
                artifact_records_json=excluded.artifact_records_json,
                result_json=excluded.result_json
            """,
            (
                run_record.run_id,
                run_record.namespace,
                run_record.tag,
                run_record.status,
                run_record.surface_key,
                run_record.surface_kind,
                run_record.driver_ref,
                run_record.family_ref,
                run_record.assembly_signature,
                run_record.started_at_utc,
                run_record.finished_at_utc,
                run_record.duration_s,
                run_record.subject_kind,
                run_record.subject_key,
                run_record.primary_metric_name,
                run_record.primary_metric_value,
                run_record.output_dir,
                _json_dumps(surface_record.to_dict()),
                _json_dumps(assembly_record.to_dict()),
                _json_dumps(run_record.to_dict()),
                _json_dumps(artifact_rows),
                _json_dumps(compact_result),
            ),
        )
        for artifact_record in tuple(artifact_records or ()):
            conn.execute(
                """
                INSERT INTO runtime_artifact_surface (
                    run_id, artifact_id, artifact_role, producer_ref, surface_key, assembly_signature, artifact_record_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, artifact_id) DO UPDATE SET
                    artifact_role=excluded.artifact_role,
                    producer_ref=excluded.producer_ref,
                    surface_key=excluded.surface_key,
                    assembly_signature=excluded.assembly_signature,
                    artifact_record_json=excluded.artifact_record_json
                """,
                (
                    artifact_record.run_id,
                    artifact_record.artifact_id,
                    artifact_record.artifact_role,
                    artifact_record.producer_ref,
                    artifact_record.surface_key,
                    artifact_record.assembly_signature,
                    _json_dumps(artifact_record.to_dict()),
                ),
            )
        conn.commit()


@dataclass
class RuntimeSurfaceTrackerConfig:
    db_path: str = "runs/runtime_surface.sqlite3"
    namespace: str = "default"
    tag: str | None = None
    project_root: str | None = None
    surface_key: str | None = None
    surface_label: str | None = None
    print_summary: bool = False


class RuntimeSurfaceTrackerPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    artifact_provides = ("runtime_surface_db", "runtime_surface_run_ref")
    context_notes = (
        "Materializes SurfaceRecord/AssemblyRecord/RunRecord/ArtifactRecord into the resolved experiment DB target and injects run_surface into the solver result.",
    )

    def __init__(
        self,
        name: str = "runtime_surface_tracker",
        *,
        config: Optional[RuntimeSurfaceTrackerConfig] = None,
        priority: int = 100,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or RuntimeSurfaceTrackerConfig()
        self.cfg.db_path = resolve_experiment_db_target(getattr(self.cfg, "db_path", None))
        self._started_at_utc: str | None = None
        self._catalog_import_map: dict[str, str] | None = None

    def _connect(self) -> Any:
        return open_experiment_db(str(self.cfg.db_path))

    def _ensure_schema(self, conn: Any) -> None:
        ensure_runtime_surface_schema(conn)

    def on_solver_init(self, solver: Any) -> None:
        self._started_at_utc = _utc_now_iso()
        return None

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        solver = self.solver
        if solver is None:
            return None

        run_id = self._resolve_run_id(solver, result)
        if run_id is None:
            run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        result.setdefault("run_id", run_id)
        artifacts = result.setdefault("artifacts", {})
        if not isinstance(artifacts, dict):
            artifacts = {}
            result["artifacts"] = artifacts
        artifacts.setdefault("runtime_surface_db", str(self.cfg.db_path))
        artifacts.setdefault("runtime_surface_run_ref", str(run_id))

        surface_record, assembly_record, run_record, artifact_records = self._build_contract_records(
            solver=solver,
            result=result,
            run_id=str(run_id),
        )

        result["run_surface"] = {
            "contract_version": surface_record.contract_version,
            "surface_record": surface_record.to_dict(),
            "assembly_record": assembly_record.to_dict(),
            "run_record": run_record.to_dict(),
            "artifact_records": [record.to_dict() for record in artifact_records],
            "db_path": str(self.cfg.db_path),
        }

        persist_runtime_surface_records(
            str(self.cfg.db_path),
            surface_record=surface_record,
            assembly_record=assembly_record,
            run_record=run_record,
            artifact_records=artifact_records,
            result_payload=result,
        )

        if bool(self.cfg.print_summary):
            print(
                "[runtime-surface] "
                f"run_id={run_record.run_id} surface_key={run_record.surface_key} "
                f"assembly_signature={run_record.assembly_signature}"
            )
        return None

    def _catalog_import_to_key(self) -> dict[str, str]:
        if self._catalog_import_map is not None:
            return self._catalog_import_map
        try:
            entries = get_catalog(profile="framework-core").list()
        except Exception:
            entries = ()
        self._catalog_import_map = {
            str(entry.import_path): str(entry.key)
            for entry in entries
            if _text(getattr(entry, "import_path", None))
        }
        return self._catalog_import_map

    def _catalog_ref_for_object(self, obj: Any, *, fallback_prefix: str) -> str | None:
        if obj is None:
            return None
        cls = obj if isinstance(obj, type) else obj.__class__
        import_path = f"{cls.__module__}:{cls.__name__}"
        key = self._catalog_import_to_key().get(import_path)
        if key:
            return _catalog_key_to_ref(key, fallback_prefix=fallback_prefix)
        name = getattr(obj, "name", None)
        if name is not None:
            return f"{fallback_prefix}:{_slug(name)}"
        return f"{fallback_prefix}:{_slug(cls.__name__)}"

    def _resolve_project_root(self, solver: Any) -> Path | None:
        explicit = _text(getattr(self.cfg, "project_root", None)) or _text(getattr(solver, "project_root", None))
        if explicit:
            return Path(explicit).expanduser().resolve()
        cwd_root = find_project_root(Path.cwd())
        if cwd_root is not None:
            return cwd_root.resolve()
        return None

    def _resolve_run_id(self, solver: Any, result: Mapping[str, Any]) -> str | None:
        rid = _text(result.get("run_id")) if isinstance(result, Mapping) else None
        if rid:
            return rid
        artifacts = result.get("artifacts") if isinstance(result, Mapping) else None
        if isinstance(artifacts, Mapping):
            rid = _text(artifacts.get("run_id"))
            if rid:
                return rid
        for attr in ("run_id", "_last_run_id", "benchmark_run_id"):
            rid = _text(getattr(solver, attr, None))
            if rid:
                return rid
        plugin_manager = getattr(solver, "plugin_manager", None)
        if plugin_manager is not None and hasattr(plugin_manager, "list_plugins"):
            try:
                for plugin in plugin_manager.list_plugins(enabled_only=False):
                    cfg = getattr(plugin, "cfg", None)
                    rid = _text(getattr(cfg, "run_id", None)) if cfg is not None else None
                    if rid:
                        return rid
            except Exception:
                pass
        return None

    def _resolve_output_dir(self, solver: Any, result: Mapping[str, Any]) -> str | None:
        artifacts = result.get("artifacts") if isinstance(result, Mapping) else None
        if isinstance(artifacts, Mapping):
            for value in artifacts.values():
                if isinstance(value, (str, Path)):
                    try:
                        return str(Path(str(value)).expanduser().resolve().parent)
                    except Exception:
                        continue
        plugin_manager = getattr(solver, "plugin_manager", None)
        if plugin_manager is not None and hasattr(plugin_manager, "list_plugins"):
            try:
                for plugin in plugin_manager.list_plugins(enabled_only=False):
                    cfg = getattr(plugin, "cfg", None)
                    out = _text(getattr(cfg, "output_dir", None)) if cfg is not None else None
                    if out:
                        return str(Path(out).expanduser().resolve())
            except Exception:
                pass
        return None

    def _build_problem_subject(self, solver: Any) -> tuple[str | None, str | None, dict[str, Any]]:
        problem = getattr(solver, "problem", None)
        if problem is None:
            return None, None, {}
        cls = problem.__class__
        subject_key = f"problem:{cls.__module__}.{cls.__name__}"
        payload = {
            "class": cls.__name__,
            "module": cls.__module__,
            "name": _text(getattr(problem, "name", None)),
            "dimension": getattr(problem, "dimension", None),
            "objectives": _to_jsonable(getattr(problem, "objectives", None)),
            "bounds_shape": len(getattr(problem, "bounds", ()) or ()),
        }
        return "problem", subject_key, payload

    def _build_params_payload(self, solver: Any) -> dict[str, Any]:
        adapter = getattr(solver, "adapter", None)
        payload = {
            "solver_class": solver.__class__.__name__,
            "adapter_class": None if adapter is None else adapter.__class__.__name__,
            "solver_params": {
                "pop_size": getattr(solver, "pop_size", None),
                "max_generations": getattr(solver, "max_generations", None),
                "max_steps": getattr(solver, "max_steps", None),
                "mutation_rate": getattr(solver, "mutation_rate", None),
                "crossover_rate": getattr(solver, "crossover_rate", None),
                "parallel_backend": getattr(solver, "parallel_backend", None),
                "parallel_max_workers": getattr(solver, "parallel_max_workers", None),
            },
            "adapter_state": _to_jsonable(getattr(adapter, "cfg", None)),
        }
        return {str(k): _to_jsonable(v) for k, v in payload.items()}

    def _representation_refs(self, pipeline: Any) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, Any]]:
        if pipeline is None:
            return (), (), {}
        pipeline_ref = self._catalog_ref_for_object(pipeline, fallback_prefix="pipeline")
        slot_payload: dict[str, Any] = {}
        representation_refs: list[str] = []
        for slot_name in ("initializer", "mutator", "repair", "crossover", "encoder"):
            component = getattr(pipeline, slot_name, None)
            ref = self._catalog_ref_for_object(component, fallback_prefix="representation")
            if ref is None:
                continue
            representation_refs.append(ref)
            slot_payload[slot_name] = ref
        initializers = getattr(pipeline, "initializers", None)
        if isinstance(initializers, Sequence):
            pool_refs: list[str] = []
            for item in initializers:
                component = item[0] if isinstance(item, Sequence) and item else None
                ref = self._catalog_ref_for_object(component, fallback_prefix="representation")
                if ref is not None:
                    pool_refs.append(ref)
            if pool_refs:
                slot_payload["initializer_pool"] = list(_dedupe(pool_refs))
                representation_refs.extend(pool_refs)
        return (
            _dedupe(representation_refs),
            _dedupe((pipeline_ref,)),
            slot_payload,
        )

    @staticmethod
    def _is_provider_plugin(plugin: Any) -> bool:
        module = str(getattr(plugin.__class__, "__module__", "") or "")
        name = str(plugin.__class__.__name__ or "")
        return (
            "plugins.evaluation" in module
            or name.endswith("ProviderPlugin")
            or name.endswith("EvaluationPlugin")
        )

    def _collect_plugin_refs(self, solver: Any) -> tuple[tuple[str, ...], tuple[str, ...], dict[int, str]]:
        plugin_manager = getattr(solver, "plugin_manager", None)
        plugins = plugin_manager.list_plugins(enabled_only=False) if plugin_manager is not None and hasattr(plugin_manager, "list_plugins") else []
        provider_refs: list[str] = []
        plugin_refs: list[str] = []
        by_id: dict[int, str] = {}
        for plugin in plugins:
            ref = self._catalog_ref_for_object(plugin, fallback_prefix="plugin")
            if ref is None:
                continue
            by_id[id(plugin)] = ref
            if self._is_provider_plugin(plugin):
                provider_refs.append(ref)
            else:
                plugin_refs.append(ref)
        return _dedupe(provider_refs), _dedupe(plugin_refs), by_id

    def _artifact_producer_ref(self, solver: Any, artifact_id: str, plugin_ref_by_id: Mapping[int, str]) -> str | None:
        plugin_manager = getattr(solver, "plugin_manager", None)
        plugins = plugin_manager.list_plugins(enabled_only=False) if plugin_manager is not None and hasattr(plugin_manager, "list_plugins") else []
        for plugin in plugins:
            keys = tuple(str(item).strip() for item in getattr(plugin, "artifact_provides", ()) or () if str(item).strip())
            if str(artifact_id) in keys:
                return plugin_ref_by_id.get(id(plugin))
        if str(artifact_id) in tuple(self.artifact_provides or ()):
            return self._catalog_ref_for_object(self, fallback_prefix="plugin")
        return None

    @staticmethod
    def _artifact_role(artifact_id: str) -> str:
        aid = str(artifact_id).lower()
        if "checkpoint" in aid:
            return "checkpoint"
        if "trace" in aid or "graph" in aid:
            return "trace"
        if "report" in aid or "summary" in aid or "profile" in aid:
            return "report"
        if aid.endswith("_db") or "runtime_surface" in aid:
            return "catalog"
        return "artifact"

    @staticmethod
    def _artifact_location(value: Any) -> tuple[str | None, str | None, str | None, dict[str, Any]]:
        if isinstance(value, (str, Path)):
            path = str(Path(str(value)).expanduser().resolve())
            suffix = Path(path).suffix.lower().lstrip(".") or None
            return path, None, suffix, {}
        if isinstance(value, Mapping):
            return (
                _text(value.get("path")),
                _text(value.get("uri")),
                _text(value.get("format")),
                {str(k): _to_jsonable(v) for k, v in value.items() if str(k) not in {"path", "uri", "format"}},
            )
        return None, None, None, {"value": _to_jsonable(value)}

    @staticmethod
    def _primary_metric(solver: Any, result: Mapping[str, Any]) -> tuple[str | None, float | None]:
        candidates = (
            ("best_objective", result.get("best_objective")),
            ("best_f", result.get("best_f")),
            ("elapsed_sec", result.get("elapsed_sec")),
        )
        for name, value in candidates:
            try:
                if value is None:
                    continue
                return str(name), float(value)
            except Exception:
                continue
        try:
            best_objective = getattr(solver, "best_objective", None)
            if best_objective is not None:
                return "best_objective", float(best_objective)
        except Exception:
            pass
        return None, None

    def _build_contract_records(
        self,
        *,
        solver: Any,
        result: Mapping[str, Any],
        run_id: str,
    ) -> tuple[SurfaceRecord, AssemblyRecord, RunRecord, list[ArtifactRecord]]:
        project_root = self._resolve_project_root(solver)
        project_root_text = None if project_root is None else str(project_root)
        entry_path = None
        entry_module = None
        entry_symbol = None
        if project_root is not None:
            candidate = project_root / "build_solver.py"
            if candidate.is_file():
                entry_path = str(candidate.resolve())
                entry_module = "build_solver"
                entry_symbol = "build_solver"

        solver_ref = self._catalog_ref_for_object(solver, fallback_prefix="solver")
        adapter = getattr(solver, "adapter", None)
        adapter_ref = self._catalog_ref_for_object(adapter, fallback_prefix="adapter")
        driver_ref = adapter_ref or solver_ref
        surface_key = (
            _text(getattr(self.cfg, "surface_key", None))
            or _text(getattr(solver, "surface_key", None))
            or (f"solver:{project_root.name}.build_solver" if project_root is not None else None)
            or solver_ref
            or "solver:unknown"
        )
        surface_label = (
            _text(getattr(self.cfg, "surface_label", None))
            or _text(getattr(solver, "name", None))
            or solver.__class__.__name__
        )

        surface_record = make_surface_record(
            framework="nsgablack",
            project_root=project_root_text,
            scaffold_root=project_root_text,
            surface_kind="solver",
            surface_key=str(surface_key),
            surface_label=str(surface_label),
            entry_path=entry_path,
            entry_module=entry_module,
            entry_symbol=entry_symbol,
            driver_ref=driver_ref,
            family_ref=None,
            tags=("runtime_surface", "solver"),
            metadata_json={
                "solver_ref": solver_ref,
                "adapter_ref": adapter_ref,
            },
        )

        pipeline = getattr(solver, "representation_pipeline", None)
        representation_refs, pipeline_refs, representation_slots = self._representation_refs(pipeline)
        bias_ref = self._catalog_ref_for_object(getattr(solver, "bias_module", None), fallback_prefix="bias")
        provider_refs, plugin_refs, plugin_ref_by_id = self._collect_plugin_refs(solver)
        bias_refs = _dedupe((bias_ref,))
        component_refs = _dedupe((*representation_refs, *bias_refs))
        mount_order = _dedupe((solver_ref, adapter_ref, *pipeline_refs, *representation_refs, *bias_refs, *provider_refs, *plugin_refs))

        solver_contracts = collect_solver_contracts(solver)
        contract_summary = [
            {
                "slot": str(name),
                **contract.to_dict(),
            }
            for name, contract in solver_contracts
        ]

        assembly_record = make_assembly_record(
            framework="nsgablack",
            surface_key=str(surface_key),
            assembly_key=str(surface_key),
            driver_ref=driver_ref,
            family_ref=None,
            solver_ref=solver_ref,
            adapter_ref=adapter_ref,
            representation_refs=representation_refs,
            bias_refs=bias_refs,
            component_refs=component_refs,
            provider_refs=provider_refs,
            plugin_refs=plugin_refs,
            pipeline_refs=pipeline_refs,
            mount_order=mount_order,
            component_slots_json={
                "solver": solver_ref,
                "adapter": adapter_ref,
                "representation_pipeline": list(pipeline_refs),
                "representation_slots": representation_slots,
                "bias_module": list(bias_refs),
                "providers": list(provider_refs),
                "plugins": list(plugin_refs),
            },
            metadata_json={
                "contract_components": contract_summary,
                "contract_conflicts": detect_context_conflicts(solver_contracts),
            },
        )

        subject_kind, subject_key, subject_json = self._build_problem_subject(solver)
        params_json = self._build_params_payload(solver)
        primary_metric_name, primary_metric_value = self._primary_metric(solver, result)
        finished_at_utc = _utc_now_iso()
        duration_s = None
        if _text(result.get("elapsed_sec")) is not None:
            try:
                duration_s = float(result.get("elapsed_sec"))  # type: ignore[arg-type]
            except Exception:
                duration_s = None
        if duration_s is None and self._started_at_utc:
            try:
                duration_s = max(
                    0.0,
                    float(
                        (
                            datetime.fromisoformat(str(finished_at_utc))
                            - datetime.fromisoformat(str(self._started_at_utc))
                        ).total_seconds()
                    ),
                )
            except Exception:
                duration_s = None

        run_record = make_run_record(
            framework="nsgablack",
            run_id=str(run_id),
            namespace=str(self.cfg.namespace or "default"),
            tag=self.cfg.tag,
            status=str(result.get("status", "completed")),
            started_at_utc=self._started_at_utc,
            finished_at_utc=finished_at_utc,
            duration_s=duration_s,
            surface_key=str(surface_key),
            surface_kind="solver",
            surface_signature=surface_record.surface_signature,
            assembly_signature=assembly_record.assembly_signature,
            subject_kind=subject_kind,
            subject_key=subject_key,
            subject_json=subject_json,
            params_json=params_json,
            driver_ref=driver_ref,
            family_ref=None,
            output_dir=self._resolve_output_dir(solver, result),
            primary_metric_name=primary_metric_name,
            primary_metric_value=primary_metric_value,
            metric_summary_json={
                "best_objective": _to_jsonable(result.get("best_objective", getattr(solver, "best_objective", None))),
                "steps": _to_jsonable(result.get("steps")),
                "generation": _to_jsonable(result.get("generation", getattr(solver, "generation", None))),
                "evaluation_count": _to_jsonable(result.get("evaluation_count", getattr(solver, "evaluation_count", None))),
            },
            result_json=_compact_result_payload(result),
            component_refs=mount_order,
            artifact_ids=tuple(str(k) for k in dict(result.get("artifacts", {}) or {}).keys()),
            metadata_json={
                "project_root": project_root_text,
                "solver_ref": solver_ref,
                "adapter_ref": adapter_ref,
            },
        )

        artifact_records: list[ArtifactRecord] = []
        artifacts = result.get("artifacts")
        if isinstance(artifacts, Mapping):
            for artifact_id, artifact_value in artifacts.items():
                path, uri, fmt, metadata = self._artifact_location(artifact_value)
                artifact_records.append(
                    make_artifact_record(
                        framework="nsgablack",
                        run_id=str(run_id),
                        artifact_id=str(artifact_id),
                        artifact_kind=str(fmt or "artifact"),
                        artifact_role=self._artifact_role(str(artifact_id)),
                        producer_ref=self._artifact_producer_ref(solver, str(artifact_id), plugin_ref_by_id),
                        surface_key=str(surface_key),
                        assembly_signature=assembly_record.assembly_signature,
                        path=path,
                        uri=uri,
                        format=fmt,
                        created_at_utc=finished_at_utc,
                        metrics_json={
                            "primary_metric_name": primary_metric_name,
                            "primary_metric_value": primary_metric_value,
                        },
                        metadata_json=metadata,
                        tags=("artifact", self._artifact_role(str(artifact_id))),
                    )
                )
        return surface_record, assembly_record, run_record, artifact_records


def build_runtime_surface_tracker_plugin(**kwargs: Any) -> RuntimeSurfaceTrackerPlugin:
    params = dict(kwargs)
    config = RuntimeSurfaceTrackerConfig(
        db_path=str(params.pop("db_path", resolve_experiment_db_target())),
        namespace=str(params.pop("namespace", "default")),
        tag=params.pop("tag", None),
        project_root=params.pop("project_root", None),
        surface_key=params.pop("surface_key", None),
        surface_label=params.pop("surface_label", None),
        print_summary=bool(params.pop("print_summary", False)),
    )
    return RuntimeSurfaceTrackerPlugin(
        name=str(params.pop("name", "runtime_surface_tracker")),
        config=config,
        priority=int(params.pop("priority", 100)),
    )


def _connect_runtime_surface_db(db_path: str | Path) -> Any:
    return open_experiment_db(str(db_path))


def _distinct_text_values(conn: Any, sql: str, params: Sequence[Any] = ()) -> list[str]:
    rows = conn.execute(sql, tuple(params)).fetchall()
    return first_column_texts(rows)


def _decode_row(row: Any, *, json_fields: Sequence[str]) -> dict[str, Any]:
    if isinstance(row, Mapping):
        payload = {str(key): value for key, value in dict(row).items()}
    else:
        payload = {str(key): row[key] for key in row.keys()}
    for field_name in tuple(json_fields):
        payload[str(field_name)] = _json_loads(payload.get(str(field_name)))
    return payload


def list_runtime_run_surfaces(
    db_path: str | Path,
    *,
    run_id: str | None = None,
    status: str | None = None,
    surface_key: str | None = None,
    driver_ref: str | None = None,
    family_ref: str | None = None,
    assembly_signature: str | None = None,
    screening_protocol: str | None = None,
    outer_search_protocol: str | None = None,
    structure_head: str | None = None,
    search_input_space: str | None = None,
    pool_expansion_unit: str | None = None,
    gradient_guidance_mode: str | None = None,
    basis_binding_mode: str | None = None,
    escape_policy: str | None = None,
    equivalence_expression_protocol: str | None = None,
    equivalence_expression_mode: str | None = None,
    interference_feature_protocol: str | None = None,
    interference_feature_mode: str | None = None,
    cross_explanatory_rejection_mode: str | None = None,
    trivial_nonlinearity_penalty_mode: str | None = None,
    environment_invariance_audit_mode: str | None = None,
    lane_id: str | None = None,
    lane_family: str | None = None,
    challenger_objective_protocol: str | None = None,
    pool_expansion_bias_protocol: str | None = None,
    joint_core_score_min: float | None = None,
    cross_lane_stability_min: float | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if run_id is not None:
        where.append("run_id = ?")
        params.append(str(run_id))
    if status is not None:
        where.append("status = ?")
        params.append(str(status))
    if surface_key is not None:
        where.append("surface_key = ?")
        params.append(str(surface_key))
    if driver_ref is not None:
        where.append("driver_ref = ?")
        params.append(str(driver_ref))
    if family_ref is not None:
        where.append("family_ref = ?")
        params.append(str(family_ref))
    if assembly_signature is not None:
        where.append("assembly_signature = ?")
        params.append(str(assembly_signature))
    sql = "SELECT * FROM runtime_run_surface"
    if where:
        sql += " WHERE " + " AND ".join(where)
    apply_runtime_filters = any(
        value is not None
        for value in (
            screening_protocol,
            outer_search_protocol,
            structure_head,
            search_input_space,
            pool_expansion_unit,
            gradient_guidance_mode,
            basis_binding_mode,
            escape_policy,
            equivalence_expression_protocol,
            equivalence_expression_mode,
            interference_feature_protocol,
            interference_feature_mode,
            cross_explanatory_rejection_mode,
            trivial_nonlinearity_penalty_mode,
            environment_invariance_audit_mode,
            lane_id,
            lane_family,
            challenger_objective_protocol,
            pool_expansion_bias_protocol,
            joint_core_score_min,
            cross_lane_stability_min,
        )
    )
    with _connect_runtime_surface_db(db_path) as conn:
        if not table_exists(conn, "runtime_run_surface"):
            return []
        if conn.backend == "postgresql":
            sql += " ORDER BY finished_at_utc DESC NULLS LAST, started_at_utc DESC NULLS LAST, run_id DESC"
        else:
            sql += " ORDER BY rowid DESC"
        if not apply_runtime_filters:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        rows = conn.execute(sql, tuple(params)).fetchall()
    decoded_rows = [
        _augment_runtime_run_surface_row(
            _decode_row(
                row,
                json_fields=(
                    "surface_record_json",
                    "assembly_record_json",
                    "run_record_json",
                    "artifact_records_json",
                    "result_json",
                ),
            )
        )
        for row in rows
    ]
    if screening_protocol is not None:
        decoded_rows = [
            row for row in decoded_rows if _text(row.get("screening_protocol")) == _text(screening_protocol)
        ]
    if outer_search_protocol is not None:
        decoded_rows = [
            row for row in decoded_rows if _text(row.get("outer_search_protocol")) == _text(outer_search_protocol)
        ]
    if structure_head is not None:
        decoded_rows = [row for row in decoded_rows if _text(row.get("structure_head")) == _text(structure_head)]
    if search_input_space is not None:
        decoded_rows = [
            row for row in decoded_rows if _text(row.get("search_input_space")) == _text(search_input_space)
        ]
    if pool_expansion_unit is not None:
        decoded_rows = [
            row for row in decoded_rows if _text(row.get("pool_expansion_unit")) == _text(pool_expansion_unit)
        ]
    if gradient_guidance_mode is not None:
        decoded_rows = [
            row for row in decoded_rows if _text(row.get("gradient_guidance_mode")) == _text(gradient_guidance_mode)
        ]
    if basis_binding_mode is not None:
        decoded_rows = [
            row for row in decoded_rows if _text(row.get("basis_binding_mode")) == _text(basis_binding_mode)
        ]
    if escape_policy is not None:
        decoded_rows = [
            row for row in decoded_rows if _text(row.get("escape_policy")) == _text(escape_policy)
        ]
    if equivalence_expression_protocol is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("equivalence_expression_protocol")) == _text(equivalence_expression_protocol)
        ]
    if equivalence_expression_mode is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("equivalence_expression_mode")) == _text(equivalence_expression_mode)
        ]
    if interference_feature_protocol is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("interference_feature_protocol")) == _text(interference_feature_protocol)
        ]
    if interference_feature_mode is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("interference_feature_mode")) == _text(interference_feature_mode)
        ]
    if cross_explanatory_rejection_mode is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("cross_explanatory_rejection_mode")) == _text(cross_explanatory_rejection_mode)
        ]
    if trivial_nonlinearity_penalty_mode is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("trivial_nonlinearity_penalty_mode")) == _text(trivial_nonlinearity_penalty_mode)
        ]
    if environment_invariance_audit_mode is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("environment_invariance_audit_mode")) == _text(environment_invariance_audit_mode)
        ]
    if lane_id is not None:
        decoded_rows = [row for row in decoded_rows if _text(row.get("lane_id")) == _text(lane_id)]
    if lane_family is not None:
        decoded_rows = [row for row in decoded_rows if _text(row.get("lane_family")) == _text(lane_family)]
    if challenger_objective_protocol is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("challenger_objective_protocol")) == _text(challenger_objective_protocol)
        ]
    if pool_expansion_bias_protocol is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if _text(row.get("pool_expansion_bias_protocol")) == _text(pool_expansion_bias_protocol)
        ]
    joint_core_threshold = _float_or_none(joint_core_score_min)
    if joint_core_threshold is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if (_float_or_none(row.get("joint_core_score")) is not None)
            and float(_float_or_none(row.get("joint_core_score")) or 0.0) >= float(joint_core_threshold)
        ]
    cross_lane_threshold = _float_or_none(cross_lane_stability_min)
    if cross_lane_threshold is not None:
        decoded_rows = [
            row
            for row in decoded_rows
            if (_float_or_none(row.get("cross_lane_stability")) is not None)
            and float(_float_or_none(row.get("cross_lane_stability")) or 0.0) >= float(cross_lane_threshold)
        ]
    return decoded_rows[: max(1, int(limit))]


def list_runtime_artifact_surfaces(
    db_path: str | Path,
    *,
    run_id: str | None = None,
    artifact_role: str | None = None,
    producer_ref: str | None = None,
    surface_key: str | None = None,
    assembly_signature: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if run_id is not None:
        where.append("run_id = ?")
        params.append(str(run_id))
    if artifact_role is not None:
        where.append("artifact_role = ?")
        params.append(str(artifact_role))
    if producer_ref is not None:
        where.append("producer_ref = ?")
        params.append(str(producer_ref))
    if surface_key is not None:
        where.append("surface_key = ?")
        params.append(str(surface_key))
    if assembly_signature is not None:
        where.append("assembly_signature = ?")
        params.append(str(assembly_signature))
    sql = "SELECT * FROM runtime_artifact_surface"
    if where:
        sql += " WHERE " + " AND ".join(where)
    params.append(max(1, int(limit)))
    with _connect_runtime_surface_db(db_path) as conn:
        if not table_exists(conn, "runtime_artifact_surface"):
            return []
        if conn.backend == "postgresql":
            sql += " ORDER BY run_id DESC, artifact_id ASC LIMIT ?"
        else:
            sql += " ORDER BY rowid DESC LIMIT ?"
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [
        _decode_row(
            row,
            json_fields=("artifact_record_json",),
        )
        for row in rows
    ]


def show_runtime_run_surface(
    db_path: str | Path,
    *,
    run_id: str,
) -> dict[str, Any] | None:
    with _connect_runtime_surface_db(db_path) as conn:
        if not table_exists(conn, "runtime_run_surface"):
            return None
        row = conn.execute(
            "SELECT * FROM runtime_run_surface WHERE run_id = ?",
            (str(run_id),),
        ).fetchone()
    if row is None:
        return None
    return _augment_runtime_run_surface_row(
        _decode_row(
            row,
            json_fields=(
                "surface_record_json",
                "assembly_record_json",
                "run_record_json",
                "artifact_records_json",
                "result_json",
            ),
        )
    )


def show_runtime_artifact_surface(
    db_path: str | Path,
    *,
    run_id: str,
    artifact_id: str,
) -> dict[str, Any] | None:
    with _connect_runtime_surface_db(db_path) as conn:
        if not table_exists(conn, "runtime_artifact_surface"):
            return None
        row = conn.execute(
            "SELECT * FROM runtime_artifact_surface WHERE run_id = ? AND artifact_id = ?",
            (str(run_id), str(artifact_id)),
        ).fetchone()
    if row is None:
        return None
    return _decode_row(row, json_fields=("artifact_record_json",))


def runtime_surface_summary(db_path: str | Path) -> dict[str, Any]:
    db_resolved = str(db_path)
    with _connect_runtime_surface_db(db_path) as conn:
        run_count = table_count(conn, "runtime_run_surface")
        artifact_count = table_count(conn, "runtime_artifact_surface")
        run_table_ready = table_exists(conn, "runtime_run_surface")
        artifact_table_ready = table_exists(conn, "runtime_artifact_surface")
        return {
            "db_path": db_resolved,
            "backend": str(getattr(conn, "backend", "sqlite")),
            "tables": {
                "runtime_run_surface": run_count,
                "runtime_artifact_surface": artifact_count,
            },
            "statuses": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT status
                FROM runtime_run_surface
                WHERE status IS NOT NULL AND TRIM(status) <> ''
                ORDER BY status ASC
                """,
            ),
            "surface_keys": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT surface_key
                FROM runtime_run_surface
                WHERE surface_key IS NOT NULL AND TRIM(surface_key) <> ''
                ORDER BY surface_key ASC
                """,
            ),
            "driver_refs": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT driver_ref
                FROM runtime_run_surface
                WHERE driver_ref IS NOT NULL AND TRIM(driver_ref) <> ''
                ORDER BY driver_ref ASC
                """,
            ),
            "artifact_roles": [] if not artifact_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT artifact_role
                FROM runtime_artifact_surface
                WHERE artifact_role IS NOT NULL AND TRIM(artifact_role) <> ''
                ORDER BY artifact_role ASC
                """,
            ),
        }


def runtime_surface_filter_values(db_path: str | Path) -> dict[str, list[str]]:
    with _connect_runtime_surface_db(db_path) as conn:
        run_table_ready = table_exists(conn, "runtime_run_surface")
        artifact_table_ready = table_exists(conn, "runtime_artifact_surface")
        derived_run_rows = []
        if run_table_ready:
            derived_run_rows = [
                _augment_runtime_run_surface_row(
                    _decode_row(
                        row,
                        json_fields=(
                            "surface_record_json",
                            "assembly_record_json",
                            "run_record_json",
                            "artifact_records_json",
                            "result_json",
                        ),
                    )
                )
                for row in conn.execute("SELECT * FROM runtime_run_surface").fetchall()
            ]
        def _derived_distinct(field_name: str) -> list[str]:
            values = sorted(
                {
                    str(value).strip()
                    for value in (row.get(field_name) for row in derived_run_rows)
                    if str(value or "").strip()
                }
            )
            return values
        return {
            "run_status": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT status
                FROM runtime_run_surface
                WHERE status IS NOT NULL AND TRIM(status) <> ''
                ORDER BY status ASC
                """,
            ),
            "run_surface_key": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT surface_key
                FROM runtime_run_surface
                WHERE surface_key IS NOT NULL AND TRIM(surface_key) <> ''
                ORDER BY surface_key ASC
                """,
            ),
            "run_driver_ref": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT driver_ref
                FROM runtime_run_surface
                WHERE driver_ref IS NOT NULL AND TRIM(driver_ref) <> ''
                ORDER BY driver_ref ASC
                """,
            ),
            "run_family_ref": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT family_ref
                FROM runtime_run_surface
                WHERE family_ref IS NOT NULL AND TRIM(family_ref) <> ''
                ORDER BY family_ref ASC
                """,
            ),
            "run_assembly_signature": [] if not run_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT assembly_signature
                FROM runtime_run_surface
                WHERE assembly_signature IS NOT NULL AND TRIM(assembly_signature) <> ''
                ORDER BY assembly_signature ASC
                """,
            ),
            "run_screening_protocol": _derived_distinct("screening_protocol"),
            "run_outer_search_protocol": _derived_distinct("outer_search_protocol"),
            "run_structure_head": _derived_distinct("structure_head"),
            "run_search_input_space": _derived_distinct("search_input_space"),
            "run_pool_expansion_unit": _derived_distinct("pool_expansion_unit"),
            "run_gradient_guidance_mode": _derived_distinct("gradient_guidance_mode"),
            "run_basis_binding_mode": _derived_distinct("basis_binding_mode"),
            "run_escape_policy": _derived_distinct("escape_policy"),
            "run_equivalence_expression_protocol": _derived_distinct("equivalence_expression_protocol"),
            "run_equivalence_expression_mode": _derived_distinct("equivalence_expression_mode"),
            "run_interference_feature_protocol": _derived_distinct("interference_feature_protocol"),
            "run_interference_feature_mode": _derived_distinct("interference_feature_mode"),
            "run_cross_explanatory_rejection_mode": _derived_distinct("cross_explanatory_rejection_mode"),
            "run_trivial_nonlinearity_penalty_mode": _derived_distinct("trivial_nonlinearity_penalty_mode"),
            "run_environment_invariance_audit_mode": _derived_distinct("environment_invariance_audit_mode"),
            "run_lane_id": _derived_distinct("lane_id"),
            "run_lane_family": _derived_distinct("lane_family"),
            "run_challenger_objective_protocol": _derived_distinct("challenger_objective_protocol"),
            "run_pool_expansion_bias_protocol": _derived_distinct("pool_expansion_bias_protocol"),
            "artifact_role": [] if not artifact_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT artifact_role
                FROM runtime_artifact_surface
                WHERE artifact_role IS NOT NULL AND TRIM(artifact_role) <> ''
                ORDER BY artifact_role ASC
                """,
            ),
            "artifact_producer_ref": [] if not artifact_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT producer_ref
                FROM runtime_artifact_surface
                WHERE producer_ref IS NOT NULL AND TRIM(producer_ref) <> ''
                ORDER BY producer_ref ASC
                """,
            ),
            "artifact_surface_key": [] if not artifact_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT surface_key
                FROM runtime_artifact_surface
                WHERE surface_key IS NOT NULL AND TRIM(surface_key) <> ''
                ORDER BY surface_key ASC
                """,
            ),
            "artifact_assembly_signature": [] if not artifact_table_ready else _distinct_text_values(
                conn,
                """
                SELECT DISTINCT assembly_signature
                FROM runtime_artifact_surface
                WHERE assembly_signature IS NOT NULL AND TRIM(assembly_signature) <> ''
                ORDER BY assembly_signature ASC
                """,
            ),
        }


__all__ = [
    "RuntimeSurfaceTrackerConfig",
    "RuntimeSurfaceTrackerPlugin",
    "build_runtime_surface_tracker_plugin",
    "ensure_runtime_surface_schema",
    "list_runtime_run_surfaces",
    "list_runtime_artifact_surfaces",
    "persist_runtime_surface_records",
    "show_runtime_run_surface",
    "show_runtime_artifact_surface",
    "runtime_surface_summary",
    "runtime_surface_filter_values",
]
