from __future__ import annotations

import hashlib
import json
import math
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from ...utils.engineering.run_contracts import (
    make_artifact_record,
    make_assembly_record,
    make_run_record,
    make_surface_record,
)
from ..storage.runtime_surface_tracker import persist_runtime_surface_records
from .backend_contract import BackendSolveRequest


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(raw) for key, raw in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in value]
    return str(value)


def _metric_float(value: Any, *, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(numeric):
        return float(default)
    return float(numeric)


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


_BALANCED_LEADERBOARD_WEIGHTS: dict[str, float] = {
    "exact": 0.40,
    "phase": 0.20,
    "family": 0.20,
    "rmse_fit": 0.20,
}


def _rmse_fit_score(row: Mapping[str, Any]) -> float:
    rmse = _metric_float(row.get("test_rmse"), default=float("inf"))
    if not math.isfinite(rmse):
        return 0.0
    return float(1.0 / (1.0 + max(0.0, rmse)))


def _balanced_run_score(row: Mapping[str, Any]) -> float:
    exact = _metric_float(row.get("exact_term_recovery_score"), default=0.0)
    phase = _metric_float(row.get("phase_equivalent_term_recovery_score"), default=0.0)
    family = _metric_float(row.get("family_level_term_recovery_score"), default=0.0)
    rmse_fit = _rmse_fit_score(row)
    return float(
        _BALANCED_LEADERBOARD_WEIGHTS["exact"] * exact
        + _BALANCED_LEADERBOARD_WEIGHTS["phase"] * phase
        + _BALANCED_LEADERBOARD_WEIGHTS["family"] * family
        + _BALANCED_LEADERBOARD_WEIGHTS["rmse_fit"] * rmse_fit
    )


def _best_run(runs: Sequence[Mapping[str, Any]], *, mode: str = "exact") -> dict[str, Any] | None:
    rows = [dict(row) for row in tuple(runs)]
    if not rows:
        return None
    normalized = str(mode or "exact").strip().lower()
    if normalized == "rmse":
        rows.sort(
            key=lambda row: (
                _metric_float(row.get("test_rmse"), default=float("inf")),
                -_metric_float(row.get("exact_term_recovery_score"), default=-1.0),
                -_metric_float(row.get("phase_equivalent_term_recovery_score"), default=-1.0),
                -_metric_float(row.get("family_level_term_recovery_score"), default=-1.0),
                -_metric_float(row.get("outer_objective_score"), default=-1.0),
                -_metric_float(row.get("test_r2"), default=-1.0),
            )
        )
        return rows[0]
    if normalized == "balanced":
        rows.sort(
            key=lambda row: (
                -_balanced_run_score(row),
                -_metric_float(row.get("exact_term_recovery_score"), default=-1.0),
                -_metric_float(row.get("phase_equivalent_term_recovery_score"), default=-1.0),
                -_metric_float(row.get("family_level_term_recovery_score"), default=-1.0),
                _metric_float(row.get("test_rmse"), default=float("inf")),
                -_metric_float(row.get("outer_objective_score"), default=-1.0),
                -_metric_float(row.get("test_r2"), default=-1.0),
            )
        )
        return rows[0]
    rows.sort(
        key=lambda row: (
            -_metric_float(row.get("exact_term_recovery_score"), default=-1.0),
            -_metric_float(row.get("phase_equivalent_term_recovery_score"), default=-1.0),
            -_metric_float(row.get("family_level_term_recovery_score"), default=-1.0),
            -_metric_float(row.get("outer_objective_score"), default=-1.0),
            _metric_float(row.get("test_rmse"), default=float("inf")),
            -_metric_float(row.get("test_r2"), default=-1.0),
        )
    )
    return rows[0]


def _leaderboard_entry(
    row: Mapping[str, Any] | None,
    *,
    mode: str,
) -> dict[str, Any]:
    if not row:
        return {"mode": str(mode)}
    out = dict(_jsonable(dict(row)))
    out["mode"] = str(mode)
    out["balanced_score"] = float(_balanced_run_score(row))
    out["rmse_fit_score"] = float(_rmse_fit_score(row))
    return out


def _build_run_leaderboards(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    best_rmse = _best_run(runs, mode="rmse")
    best_exact = _best_run(runs, mode="exact")
    best_balanced = _best_run(runs, mode="balanced")
    return {
        "weights": dict(_BALANCED_LEADERBOARD_WEIGHTS),
        "best_rmse": _leaderboard_entry(best_rmse, mode="best_rmse"),
        "best_exact": _leaderboard_entry(best_exact, mode="best_exact"),
        "best_balanced": _leaderboard_entry(best_balanced, mode="best_balanced"),
    }


def _mean_metric(runs: Sequence[Mapping[str, Any]], field_name: str) -> float | None:
    values: list[float] = []
    for row in tuple(runs):
        value = _metric_float(row.get(field_name), default=float("nan"))
        if math.isfinite(value):
            values.append(float(value))
    return None if not values else float(sum(values) / float(len(values)))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _artifact_expression(artifact: Any) -> str | None:
    if not hasattr(artifact, "expression"):
        return None
    try:
        return str(artifact.expression(target_index=0, precision=8, use_feature_names=True))
    except Exception:
        return None


def _basis_rows_from_artifact(artifact: Any) -> list[dict[str, Any]]:
    metadata = dict(getattr(artifact, "metadata", {}) or {})
    schema = dict(metadata.get("symbolic_artifact_schema", {}) or {})
    basis_structure = dict(schema.get("basis_structure", {}) or {})
    basis_semantics = dict(basis_structure.get("basis_semantics", {}) or {})
    recorded = dict(basis_semantics.get("recorded", {}) or {})
    basis_terms = recorded.get("basis_terms")
    if isinstance(basis_terms, Sequence) and not isinstance(basis_terms, (str, bytes, bytearray)):
        return [dict(row) for row in basis_terms if isinstance(row, Mapping)]
    selected_basis = metadata.get("selected_basis")
    if isinstance(selected_basis, Sequence) and not isinstance(selected_basis, (str, bytes, bytearray)):
        return [dict(row) for row in selected_basis if isinstance(row, Mapping)]
    symbolic_selected_basis = dict(metadata.get("symbolic", {}) or {}).get("selected_basis")
    if isinstance(symbolic_selected_basis, Sequence) and not isinstance(symbolic_selected_basis, (str, bytes, bytearray)):
        return [dict(row) for row in symbolic_selected_basis if isinstance(row, Mapping)]
    return []


def _outer_basis_genome_from_artifact(artifact: Any) -> tuple[dict[str, Any], ...]:
    metadata = dict(getattr(artifact, "metadata", {}) or {})
    raw = metadata.get("orthogonal_outer_basis_genome")
    if not (isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray))):
        raw = dict(metadata.get("symbolic", {}) or {}).get("orthogonal_outer_basis_genome")
    if not (isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray))):
        return tuple()
    return tuple(dict(term) for term in tuple(raw) if isinstance(term, Mapping))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_row_signature(value: Any) -> str:
    raw = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _basis_identity(row: Mapping[str, Any]) -> str:
    basis_class_id = str(row.get("basis_class_id") or "").strip()
    representative = str(row.get("representative_expression") or row.get("expression") or "").strip()
    semantic_family = str(
        row.get("representative_semantic_family") or row.get("semantic_family") or ""
    ).strip()
    if basis_class_id:
        return basis_class_id
    if representative:
        return representative
    if semantic_family:
        return semantic_family
    return _stable_row_signature(row)


@dataclass(frozen=True)
class MlblackConsensusStageReport:
    level: str
    cycle_index: int
    cycle_key: str
    stage_key: str
    stage_label: str
    status: str
    run_count: int = 0
    best_run_id: str | None = None
    best_phase: str | None = None
    primary_metric_name: str | None = None
    primary_metric_value: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": str(self.level),
            "cycle_index": int(self.cycle_index),
            "cycle_key": str(self.cycle_key),
            "stage_key": str(self.stage_key),
            "stage_label": str(self.stage_label),
            "status": str(self.status),
            "run_count": int(self.run_count),
            "best_run_id": None if self.best_run_id is None else str(self.best_run_id),
            "best_phase": None if self.best_phase is None else str(self.best_phase),
            "primary_metric_name": None if self.primary_metric_name is None else str(self.primary_metric_name),
            "primary_metric_value": self.primary_metric_value,
            "metrics": _jsonable(self.metrics),
            "metadata": _jsonable(self.metadata),
            "artifact_paths": _jsonable(self.artifact_paths),
        }


@dataclass(frozen=True)
class MlblackConsensusCycleReport:
    cycle_index: int
    cycle_key: str
    unlocked_run_count: int
    locked_run_count: int
    core_basis_count: int
    locked_seed_terms: int
    comparison: dict[str, Any] = field(default_factory=dict)
    unlocked_best_run: dict[str, Any] | None = None
    locked_best_run: dict[str, Any] | None = None
    core_selection: dict[str, Any] = field(default_factory=dict)
    core_tables: dict[str, Any] = field(default_factory=dict)
    stage_reports: tuple[dict[str, Any], ...] = ()
    artifact_paths: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_index": int(self.cycle_index),
            "cycle_key": str(self.cycle_key),
            "unlocked_run_count": int(self.unlocked_run_count),
            "locked_run_count": int(self.locked_run_count),
            "core_basis_count": int(self.core_basis_count),
            "locked_seed_terms": int(self.locked_seed_terms),
            "comparison": _jsonable(self.comparison),
            "unlocked_best_run": _jsonable(self.unlocked_best_run),
            "locked_best_run": _jsonable(self.locked_best_run),
            "core_selection": _jsonable(self.core_selection),
            "core_tables": _jsonable(self.core_tables),
            "stage_reports": _jsonable(self.stage_reports),
            "artifact_paths": _jsonable(self.artifact_paths),
        }


@dataclass
class MlblackSymbolicConsensusBackendConfig:
    mlblack_root: str = r"C:\Users\hp\Desktop\mlblack"
    benchmark_key: str = "arrhenius_gate_like"
    n_total: int = 240
    train_ratio: float = 0.8
    noise_std: float = 0.025
    dataset_seed: int = 42
    output_root: str | None = None
    db_path: str | None = None
    namespace: str = "nsgablack_mlblack_symbolic_consensus"
    tag_prefix: str = "nsgablack"
    consensus_cycles: int = 1
    unlocked_runs_per_cycle: int = 3
    locked_runs_per_cycle: int = 2
    vanilla_runs: int = 3
    locked_runs: int = 2
    search_seed_base: int = 100
    locked_search_seed_base: int = 900
    core_equivalence_mode: str = "family"
    core_min_support_rate: float = 0.6
    core_min_support_count: int = 0
    core_max_terms: int = 4
    core_min_seed_terms: int = 0
    core_backfill_mode: str = "none"
    core_run_weight_field: str = ""
    orth_candidate_limit: int = 80
    orth_group_count: int = 12
    orth_seed_candidate_count: int = 12
    orth_min_basis_count: int = 2
    orth_max_basis_count: int = 6
    orth_selection_mode: str = "interval_first"
    orth_max_pair_abs_corr: float = 0.35
    orth_max_feature_reuse: int = 2
    orth_max_semantic_repeats: int = 1
    orth_max_piecewise_semantic_repeats: int = 2
    target_score_weight: float = 1.0
    diversity_corr_weight: float = 0.8
    feature_overlap_penalty: float = 0.2
    complexity_penalty: float = 0.03
    new_feature_bonus: float = 0.05
    family_diversity_bonus: float = 0.03
    semantic_family_bonus: float = 0.05
    residual_corr_weight: float = 0.55
    residual_gain_weight: float = 0.85
    semantic_dup_penalty: float = 0.3
    piecewise_gate_bonus: float = 0.14
    screen_target_corr_weight: float = 1.0
    screen_residual_gain_weight: float = 0.65
    screen_semantic_novelty_weight: float = 0.20
    screen_consensus_prior_weight: float = 0.40
    screen_complexity_penalty: float = 0.08
    orth_gate_candidate_screen_reserve: int = 0
    orth_require_gate_candidate_in_group: bool = False
    orth_min_gate_basis_terms: int = 0
    orth_require_periodic_candidate_in_group: bool = False
    orth_min_periodic_basis_terms: int = 0
    orth_mechanistic_feature_groups: tuple[tuple[str, ...], ...] = tuple()
    orth_mechanistic_screen_bonus: float = 0.0
    orth_mechanistic_group_bonus: float = 0.0
    greedy_choice_topk: int = 4
    random_group_trials: int = 6
    outer_search_beam_width: int = 12
    outer_search_branching_factor: int = 3
    outer_search_max_expansions: int = 96
    outer_search_unit: str = "mechanism_object"
    representative_selection_rule: str = "balanced"
    gate_quantiles: tuple[float, ...] = (0.25, 0.5, 0.75)
    orth_assembler_max_added_terms: int = 4
    orth_assembler_topk_features: int = 4
    orth_assembler_max_pair_terms: int = 8
    orth_assembler_max_candidates_per_iter: int = 64
    orth_assembler_candidate_keep_top: int = 6
    orth_assembler_max_expr_depth: int = 6
    orth_assembler_ridge_l2: float = 1e-4
    orth_assembler_basis_binding_mode: str = "defining"
    orth_assembler_escape_policy: str = "forbid"
    orth_assembler_escape_feature_names: tuple[str, ...] = tuple()
    cross_explanatory_rejection_mode: str = "off"
    trivial_nonlinearity_penalty_mode: str = "off"
    environment_invariance_audit_mode: str = "off"
    periodic_equivalence_disambiguation_mode: str = "off"
    phase_spectrum_audit_mode: str = "off"
    periodic_family_prior_mode: str = "off"
    periodic_family_prior_weight: float = 0.30
    periodic_candidate_screen_reserve: int = 0
    regional_correction_promotion_mode: str = "off"
    residual_regime_identification_mode: str = "off"
    regional_correction_basis_mode: str = "off"
    regional_correction_feature_scope: str = "gate_only"
    regional_correction_topk: int = 0
    regional_correction_min_r2_gain: float = 0.0
    regional_correction_search_mode: str = "reopened_local_object_search"
    regional_local_search_beam_width: int = 6
    regional_local_search_branching_factor: int = 2
    regional_local_search_max_expansions: int = 24
    proxy_group_policy: str = "hint_if_available"
    source_overlap_penalty_mode: str = "feature_overlap_penalty"
    search_graph_cache_enabled: bool = False
    enable_experiment_tracker: bool = True
    capability_strict: bool = True
    save_artifact: bool = True
    save_report: bool = True
    cache_results: bool = True
    fallback_objective: float = 1e6


class MlblackSymbolicConsensusBackend:
    """Formal backend: nsgablack delegates symbolic consensus runs to mlblack."""

    _TRAINER_OVERRIDE_KEYS = (
        "orth_candidate_limit",
        "orth_group_count",
        "orth_seed_candidate_count",
        "orth_min_basis_count",
        "orth_max_basis_count",
        "orth_selection_mode",
        "orth_max_pair_abs_corr",
        "orth_max_feature_reuse",
        "orth_max_semantic_repeats",
        "orth_max_piecewise_semantic_repeats",
        "target_score_weight",
        "diversity_corr_weight",
        "feature_overlap_penalty",
        "complexity_penalty",
        "new_feature_bonus",
        "family_diversity_bonus",
        "semantic_family_bonus",
        "residual_corr_weight",
        "residual_gain_weight",
        "semantic_dup_penalty",
        "piecewise_gate_bonus",
        "screen_target_corr_weight",
        "screen_residual_gain_weight",
        "screen_semantic_novelty_weight",
        "screen_consensus_prior_weight",
        "screen_complexity_penalty",
        "orth_gate_candidate_screen_reserve",
        "orth_require_gate_candidate_in_group",
        "orth_min_gate_basis_terms",
        "orth_require_periodic_candidate_in_group",
        "orth_min_periodic_basis_terms",
        "orth_mechanistic_feature_groups",
        "orth_mechanistic_screen_bonus",
        "orth_mechanistic_group_bonus",
        "greedy_choice_topk",
        "random_group_trials",
        "outer_search_beam_width",
        "outer_search_branching_factor",
        "outer_search_max_expansions",
        "outer_search_unit",
        "representative_selection_rule",
        "orth_assembler_max_added_terms",
        "orth_assembler_topk_features",
        "orth_assembler_max_pair_terms",
        "orth_assembler_max_candidates_per_iter",
        "orth_assembler_candidate_keep_top",
        "orth_assembler_max_expr_depth",
        "orth_assembler_ridge_l2",
        "orth_assembler_basis_binding_mode",
        "orth_assembler_escape_policy",
        "orth_assembler_escape_feature_names",
        "cross_explanatory_rejection_mode",
        "trivial_nonlinearity_penalty_mode",
        "environment_invariance_audit_mode",
        "periodic_equivalence_disambiguation_mode",
        "phase_spectrum_audit_mode",
        "periodic_family_prior_mode",
        "periodic_family_prior_weight",
        "periodic_candidate_screen_reserve",
        "regional_correction_promotion_mode",
        "residual_regime_identification_mode",
        "regional_correction_basis_mode",
        "regional_correction_feature_scope",
        "regional_correction_topk",
        "regional_correction_min_r2_gain",
        "regional_correction_search_mode",
        "regional_local_search_beam_width",
        "regional_local_search_branching_factor",
        "regional_local_search_max_expansions",
        "proxy_group_policy",
        "source_overlap_penalty_mode",
        "search_graph_cache_enabled",
    )

    def __init__(self, *, config: MlblackSymbolicConsensusBackendConfig | None = None) -> None:
        self.cfg = config or MlblackSymbolicConsensusBackendConfig()
        self._import_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._imported = False
        self._ml: dict[str, Any] = {}
        self._cache: dict[str, dict[str, Any]] = {}

    def _ensure_mlblack_imports(self) -> None:
        with self._import_lock:
            if self._imported:
                return
            root = Path(self.cfg.mlblack_root).expanduser().resolve()
            if not root.exists():
                raise FileNotFoundError(f"mlblack_root not found: {root}")
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))

            from config import CapabilitySpec, FlowAssemblySpec, NumericizerSpec, TrainerAssemblySpec  # type: ignore
            from core.symbolic import (  # type: ignore
                annotate_basis_entries,
                build_core_basis_tables,
                select_locked_core_seed_genome,
            )
            from examples.known_relation_benchmark_suite import build_known_relation_bundle  # type: ignore
            from training import TrainerState, TrainingInit  # type: ignore
            from workflow import SemanticTrainFlowSpec, run_semantic_train_flow  # type: ignore

            self._ml.update(
                {
                    "CapabilitySpec": CapabilitySpec,
                    "FlowAssemblySpec": FlowAssemblySpec,
                    "NumericizerSpec": NumericizerSpec,
                    "TrainerAssemblySpec": TrainerAssemblySpec,
                    "annotate_basis_entries": annotate_basis_entries,
                    "build_core_basis_tables": build_core_basis_tables,
                    "select_locked_core_seed_genome": select_locked_core_seed_genome,
                    "build_known_relation_bundle": build_known_relation_bundle,
                    "TrainerState": TrainerState,
                    "TrainingInit": TrainingInit,
                    "SemanticTrainFlowSpec": SemanticTrainFlowSpec,
                    "run_semantic_train_flow": run_semantic_train_flow,
                    "mlblack_root": root,
                }
            )
            self._imported = True

    def _apply_orchestrator_hints(
        self,
        *,
        plan: Mapping[str, Any],
        bundle_metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        hints = _mapping(bundle_metadata.get("orchestrator_hints"))
        if not hints:
            return dict(plan)
        merged = dict(plan)
        trainer_overrides = dict(_mapping(merged.get("trainer_params_overrides")))
        hint_overrides = _mapping(hints.get("trainer_params_overrides"))
        for key, value in hint_overrides.items():
            if key not in trainer_overrides:
                trainer_overrides[str(key)] = value
        merged["trainer_params_overrides"] = trainer_overrides

        core_hints = _mapping(hints.get("core_selection"))
        if core_hints:
            if core_hints.get("core_equivalence_mode") is not None and not str(merged.get("core_equivalence_mode") or "").strip():
                merged["core_equivalence_mode"] = str(core_hints.get("core_equivalence_mode"))
            if core_hints.get("core_min_support_rate_floor") is not None:
                merged["core_min_support_rate"] = max(
                    float(merged.get("core_min_support_rate", self.cfg.core_min_support_rate)),
                    float(core_hints.get("core_min_support_rate_floor")),
                )
            if core_hints.get("core_min_support_rate_ceiling") is not None:
                merged["core_min_support_rate"] = min(
                    float(merged.get("core_min_support_rate", self.cfg.core_min_support_rate)),
                    float(core_hints.get("core_min_support_rate_ceiling")),
                )
            if core_hints.get("core_max_terms_floor") is not None:
                merged["core_max_terms"] = max(
                    int(merged.get("core_max_terms", self.cfg.core_max_terms)),
                    int(core_hints.get("core_max_terms_floor")),
                )
            if core_hints.get("core_max_terms_ceiling") is not None:
                merged["core_max_terms"] = min(
                    int(merged.get("core_max_terms", self.cfg.core_max_terms)),
                    int(core_hints.get("core_max_terms_ceiling")),
                )
            if core_hints.get("min_seed_terms") is not None:
                merged["core_min_seed_terms"] = max(
                    int(merged.get("core_min_seed_terms", self.cfg.core_min_seed_terms)),
                    int(core_hints.get("min_seed_terms")),
                )
            if core_hints.get("backfill_mode") is not None and str(core_hints.get("backfill_mode")).strip():
                merged["core_backfill_mode"] = str(core_hints.get("backfill_mode")).strip()
            if core_hints.get("run_weight_field") is not None and str(core_hints.get("run_weight_field")).strip():
                merged["core_run_weight_field"] = str(core_hints.get("run_weight_field")).strip()
        if not merged.get("lane_specs"):
            raw_lane_specs = hints.get("lane_specs")
            if isinstance(raw_lane_specs, Sequence) and not isinstance(raw_lane_specs, (str, bytes, bytearray)):
                merged["lane_specs"] = [
                    dict(item) for item in tuple(raw_lane_specs) if isinstance(item, Mapping)
                ]
        if not str(merged.get("multi_lane_protocol") or "").strip():
            if str(hints.get("multi_lane_protocol") or "").strip():
                merged["multi_lane_protocol"] = str(hints.get("multi_lane_protocol")).strip()
        return merged

    def _resolve_plan(self, request: BackendSolveRequest) -> dict[str, Any]:
        inner_problem = _mapping(request.inner_problem)
        payload = _mapping(request.payload)
        trainer_overrides = _mapping(inner_problem.get("trainer_params_overrides"))
        for key in self._TRAINER_OVERRIDE_KEYS:
            if key in inner_problem and key not in trainer_overrides:
                trainer_overrides[key] = inner_problem[key]
        default_output_root = (
            Path(self.cfg.output_root).expanduser().resolve()
            if self.cfg.output_root
            else Path.cwd().resolve() / "runs" / "mlblack_symbolic_consensus_backend"
        )
        default_db_path = (
            str(Path(self.cfg.db_path).expanduser().resolve())
            if self.cfg.db_path
            else str(default_output_root / "mlblack_experiment_tracker.sqlite3")
        )
        generation = int(_mapping(request.eval_context).get("generation", 0))
        individual_id = int(_mapping(request.eval_context).get("individual_id", 0))
        run_label = str(inner_problem.get("run_label") or f"g{generation:03d}_i{individual_id:03d}")
        consensus_cycles = max(1, int(inner_problem.get("consensus_cycles", self.cfg.consensus_cycles)))
        unlocked_runs_per_cycle = max(
            1,
            int(
                inner_problem.get(
                    "unlocked_runs_per_cycle",
                    inner_problem.get("vanilla_runs", self.cfg.unlocked_runs_per_cycle),
                )
            ),
        )
        locked_runs_per_cycle = max(
            0,
            int(
                inner_problem.get(
                    "locked_runs_per_cycle",
                    inner_problem.get("locked_runs", self.cfg.locked_runs_per_cycle),
                )
            ),
        )
        return {
            "benchmark_key": str(inner_problem.get("benchmark_key") or self.cfg.benchmark_key),
            "n_total": int(inner_problem.get("n_total", self.cfg.n_total)),
            "train_ratio": float(inner_problem.get("train_ratio", self.cfg.train_ratio)),
            "noise_std": float(inner_problem.get("noise_std", self.cfg.noise_std)),
            "dataset_seed": int(inner_problem.get("dataset_seed", self.cfg.dataset_seed)),
            "output_root": str(Path(inner_problem.get("output_root") or default_output_root).expanduser().resolve()),
            "db_path": str(inner_problem.get("db_path") or default_db_path),
            "namespace": str(inner_problem.get("namespace") or self.cfg.namespace),
            "tag_prefix": str(inner_problem.get("tag_prefix") or self.cfg.tag_prefix),
            "run_label": run_label,
            "consensus_cycles": int(consensus_cycles),
            "unlocked_runs_per_cycle": int(unlocked_runs_per_cycle),
            "locked_runs_per_cycle": int(locked_runs_per_cycle),
            "vanilla_runs": int(consensus_cycles * unlocked_runs_per_cycle),
            "locked_runs": int(consensus_cycles * locked_runs_per_cycle),
            "search_seed_base": int(inner_problem.get("search_seed_base", self.cfg.search_seed_base)),
            "locked_search_seed_base": int(
                inner_problem.get("locked_search_seed_base", self.cfg.locked_search_seed_base)
            ),
            "core_equivalence_mode": str(
                inner_problem.get("core_equivalence_mode") or self.cfg.core_equivalence_mode
            ),
            "core_min_support_rate": float(
                inner_problem.get("core_min_support_rate", self.cfg.core_min_support_rate)
            ),
            "core_min_support_count": int(
                inner_problem.get("core_min_support_count", self.cfg.core_min_support_count)
            ),
            "core_max_terms": int(inner_problem.get("core_max_terms", self.cfg.core_max_terms)),
            "core_min_seed_terms": int(
                inner_problem.get("core_min_seed_terms", self.cfg.core_min_seed_terms)
            ),
            "core_backfill_mode": str(
                inner_problem.get("core_backfill_mode") or self.cfg.core_backfill_mode
            ),
            "core_run_weight_field": str(
                inner_problem.get("core_run_weight_field") or self.cfg.core_run_weight_field
            ),
            "lane_specs": [
                dict(item)
                for item in tuple(inner_problem.get("lane_specs", ()) or ())
                if isinstance(item, Mapping)
            ],
            "multi_lane_protocol": str(
                inner_problem.get("multi_lane_protocol") or "heterogeneous_multi_lane_basis_consensus_v1"
            ),
            "trainer_params_overrides": trainer_overrides,
            "force_recompute": bool(inner_problem.get("force_recompute", payload.get("force_recompute", False))),
        }

    @staticmethod
    def _normalize_lane_specs(
        *,
        plan: Mapping[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        raw_specs = tuple(plan.get("lane_specs", ()) or ())
        if not raw_specs:
            return tuple()
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_specs):
            if not isinstance(raw, Mapping):
                continue
            lane_id = str(raw.get("lane_id") or f"lane_{index:02d}").strip() or f"lane_{index:02d}"
            lane_family = str(raw.get("lane_family") or lane_id).strip() or lane_id
            lane_label = str(raw.get("lane_label") or lane_id).strip() or lane_id
            description = str(raw.get("description") or "").strip()
            screening_protocol = str(raw.get("screening_protocol") or "").strip() or None
            challenger_objective_protocol = (
                str(raw.get("challenger_objective_protocol") or "").strip() or None
            )
            pool_expansion_bias_protocol = (
                str(raw.get("pool_expansion_bias_protocol") or "").strip() or None
            )
            representative_selection_rule = str(raw.get("representative_selection_rule") or "").strip() or None
            outer_search_unit = str(raw.get("outer_search_unit") or "").strip() or None
            try:
                lane_weight = float(raw.get("lane_weight", 1.0))
            except (TypeError, ValueError):
                lane_weight = 1.0
            if not math.isfinite(lane_weight):
                lane_weight = 1.0
            repeat_count = max(1, int(raw.get("repeat_count", 1) or 1))
            default_locked_repeat = 1 if int(plan.get("locked_runs_per_cycle", 0) or 0) > 0 else 0
            locked_repeat_count = max(
                0,
                int(raw.get("locked_repeat_count", default_locked_repeat) or 0),
            )
            normalized.append(
                {
                    "lane_index": int(index),
                    "lane_id": str(lane_id),
                    "lane_family": str(lane_family),
                    "lane_label": str(lane_label),
                    "lane_description": str(description),
                    "screening_protocol": screening_protocol,
                    "challenger_objective_protocol": challenger_objective_protocol,
                    "pool_expansion_bias_protocol": pool_expansion_bias_protocol,
                    "representative_selection_rule": representative_selection_rule,
                    "outer_search_unit": outer_search_unit,
                    "lane_weight": float(lane_weight),
                    "repeat_count": int(repeat_count),
                    "locked_repeat_count": int(locked_repeat_count),
                    "trainer_params_overrides": {
                        str(key): value
                        for key, value in _mapping(raw.get("trainer_params_overrides")).items()
                    },
                    "lane_spec": _jsonable(dict(raw)),
                }
            )
        return tuple(normalized)

    @staticmethod
    def _plan_with_lane_overrides(
        *,
        plan: Mapping[str, Any],
        lane_spec: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged = {
            str(key): value for key, value in _mapping(plan.get("trainer_params_overrides")).items()
        }
        if isinstance(lane_spec, Mapping):
            for key, value in _mapping(lane_spec.get("trainer_params_overrides")).items():
                merged[str(key)] = value
        out = dict(plan)
        out["trainer_params_overrides"] = merged
        return out

    @staticmethod
    def _lane_context_payload(
        *,
        plan: Mapping[str, Any],
        lane_spec: Mapping[str, Any] | None,
        cycle_index: int,
        cycle_key: str,
        stage_key: str,
        stage_level: str,
    ) -> dict[str, Any]:
        lane = dict(lane_spec or {})
        if not lane:
            return {}
        protocol = str(plan.get("multi_lane_protocol") or "heterogeneous_multi_lane_basis_consensus_v1")
        context = {
            "protocol": protocol,
            "lane_id": lane.get("lane_id"),
            "lane_family": lane.get("lane_family"),
            "lane_label": lane.get("lane_label"),
            "lane_description": lane.get("lane_description"),
            "lane_weight": lane.get("lane_weight"),
            "screening_protocol": lane.get("screening_protocol"),
            "challenger_objective_protocol": lane.get("challenger_objective_protocol"),
            "pool_expansion_bias_protocol": lane.get("pool_expansion_bias_protocol"),
            "representative_selection_rule": lane.get("representative_selection_rule"),
            "outer_search_unit": lane.get("outer_search_unit"),
            "lane_spec": lane.get("lane_spec") or _jsonable(lane),
        }
        return {
            "heterogeneous_multi_lane_protocol": str(protocol),
            "heterogeneous_multi_lane_context": _jsonable(context),
            "lane_id": lane.get("lane_id"),
            "lane_family": lane.get("lane_family"),
            "lane_label": lane.get("lane_label"),
            "lane_description": lane.get("lane_description"),
            "lane_weight": lane.get("lane_weight"),
            "screening_protocol": lane.get("screening_protocol"),
            "challenger_objective_protocol": lane.get("challenger_objective_protocol"),
            "pool_expansion_bias_protocol": lane.get("pool_expansion_bias_protocol"),
            "representative_selection_rule": lane.get("representative_selection_rule"),
            "outer_search_unit": lane.get("outer_search_unit"),
            "cycle_index": int(cycle_index),
            "cycle_key": str(cycle_key),
            "stage_key": str(stage_key),
            "stage_level": str(stage_level),
        }

    @staticmethod
    def _lane_summary(
        lane_specs: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        normalized = [dict(spec) for spec in tuple(lane_specs) if isinstance(spec, Mapping)]
        return {
            "multi_lane_enabled": bool(len(normalized) > 1),
            "lane_count": int(len(normalized)),
            "lane_ids": [str(spec.get("lane_id")) for spec in normalized if str(spec.get("lane_id") or "").strip()],
            "lane_families": sorted(
                {
                    str(spec.get("lane_family"))
                    for spec in normalized
                    if str(spec.get("lane_family") or "").strip()
                }
            ),
            "lane_specs": _jsonable(normalized),
        }

    def _stable_signature(self, request: BackendSolveRequest, plan: Mapping[str, Any]) -> str:
        payload = {
            "candidate": np.asarray(request.candidate, dtype=float).reshape(-1).round(8).tolist(),
            "plan": {
                key: value
                for key, value in dict(plan).items()
                if key not in {"run_label", "force_recompute"}
            },
        }
        raw = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def _orthogonal_params(
        self,
        *,
        plan: Mapping[str, Any],
        gate_feature_names: Sequence[str],
        enable_piecewise_basis: bool,
        search_seed: int,
        lock_seed_basis: bool,
        artifact_id: str,
    ) -> dict[str, Any]:
        overrides = _mapping(plan.get("trainer_params_overrides"))
        return {
            "parameter_backend": "ridge",
            "task": "point",
            "structure_engine": {
                "structure_mode": "orthogonal_basis_search",
                "search_driver": "orthogonal_basis",
                "dynamic_pool_enabled": True,
                "metadata": {"supports_piecewise_basis": bool(enable_piecewise_basis)},
            },
            "artifact_id": str(artifact_id),
            "candidate_limit": int(overrides.get("orth_candidate_limit", self.cfg.orth_candidate_limit)),
            "group_count": int(overrides.get("orth_group_count", self.cfg.orth_group_count)),
            "seed_candidate_count": int(
                overrides.get("orth_seed_candidate_count", self.cfg.orth_seed_candidate_count)
            ),
            "min_basis_count": int(overrides.get("orth_min_basis_count", self.cfg.orth_min_basis_count)),
            "max_basis_count": int(overrides.get("orth_max_basis_count", self.cfg.orth_max_basis_count)),
            "selection_mode": str(overrides.get("orth_selection_mode", self.cfg.orth_selection_mode)),
            "max_pair_abs_corr": float(
                overrides.get("orth_max_pair_abs_corr", self.cfg.orth_max_pair_abs_corr)
            ),
            "max_feature_reuse": int(
                overrides.get("orth_max_feature_reuse", self.cfg.orth_max_feature_reuse)
            ),
            "max_semantic_repeats": int(
                overrides.get("orth_max_semantic_repeats", self.cfg.orth_max_semantic_repeats)
            ),
            "max_piecewise_semantic_repeats": int(
                overrides.get(
                    "orth_max_piecewise_semantic_repeats",
                    self.cfg.orth_max_piecewise_semantic_repeats,
                )
            ),
            "target_score_weight": float(
                overrides.get("target_score_weight", self.cfg.target_score_weight)
            ),
            "diversity_corr_weight": float(
                overrides.get("diversity_corr_weight", self.cfg.diversity_corr_weight)
            ),
            "feature_overlap_penalty": float(
                overrides.get("feature_overlap_penalty", self.cfg.feature_overlap_penalty)
            ),
            "complexity_penalty": float(
                overrides.get("complexity_penalty", self.cfg.complexity_penalty)
            ),
            "new_feature_bonus": float(
                overrides.get("new_feature_bonus", self.cfg.new_feature_bonus)
            ),
            "family_diversity_bonus": float(
                overrides.get("family_diversity_bonus", self.cfg.family_diversity_bonus)
            ),
            "semantic_family_bonus": float(
                overrides.get("semantic_family_bonus", self.cfg.semantic_family_bonus)
            ),
            "residual_corr_weight": float(
                overrides.get("residual_corr_weight", self.cfg.residual_corr_weight)
            ),
            "residual_gain_weight": float(
                overrides.get("residual_gain_weight", self.cfg.residual_gain_weight)
            ),
            "semantic_dup_penalty": float(
                overrides.get("semantic_dup_penalty", self.cfg.semantic_dup_penalty)
            ),
            "piecewise_gate_bonus": float(
                overrides.get("piecewise_gate_bonus", self.cfg.piecewise_gate_bonus)
            ),
            "screen_target_corr_weight": float(
                overrides.get("screen_target_corr_weight", self.cfg.screen_target_corr_weight)
            ),
            "screen_residual_gain_weight": float(
                overrides.get("screen_residual_gain_weight", self.cfg.screen_residual_gain_weight)
            ),
            "screen_semantic_novelty_weight": float(
                overrides.get("screen_semantic_novelty_weight", self.cfg.screen_semantic_novelty_weight)
            ),
            "screen_consensus_prior_weight": float(
                overrides.get("screen_consensus_prior_weight", self.cfg.screen_consensus_prior_weight)
            ),
            "screen_complexity_penalty": float(
                overrides.get("screen_complexity_penalty", self.cfg.screen_complexity_penalty)
            ),
            "gate_candidate_screen_reserve": int(
                overrides.get("orth_gate_candidate_screen_reserve", self.cfg.orth_gate_candidate_screen_reserve)
            ),
            "require_gate_candidate_in_group": bool(
                overrides.get(
                    "orth_require_gate_candidate_in_group",
                    self.cfg.orth_require_gate_candidate_in_group,
                )
            ),
            "min_gate_basis_terms": int(
                overrides.get("orth_min_gate_basis_terms", self.cfg.orth_min_gate_basis_terms)
            ),
            "require_periodic_candidate_in_group": bool(
                overrides.get(
                    "orth_require_periodic_candidate_in_group",
                    self.cfg.orth_require_periodic_candidate_in_group,
                )
            ),
            "min_periodic_basis_terms": int(
                overrides.get(
                    "orth_min_periodic_basis_terms",
                    self.cfg.orth_min_periodic_basis_terms,
                )
            ),
            "mechanistic_feature_groups": tuple(
                tuple(str(name) for name in tuple(group))
                for group in tuple(
                    overrides.get(
                        "orth_mechanistic_feature_groups",
                        self.cfg.orth_mechanistic_feature_groups,
                    )
                    or ()
                )
            ),
            "mechanistic_screen_bonus": float(
                overrides.get("orth_mechanistic_screen_bonus", self.cfg.orth_mechanistic_screen_bonus)
            ),
            "mechanistic_group_bonus": float(
                overrides.get("orth_mechanistic_group_bonus", self.cfg.orth_mechanistic_group_bonus)
            ),
            "random_seed": int(search_seed),
            "greedy_choice_topk": int(overrides.get("greedy_choice_topk", self.cfg.greedy_choice_topk)),
            "random_group_trials": int(
                overrides.get("random_group_trials", self.cfg.random_group_trials)
            ),
            "outer_search_beam_width": int(
                overrides.get("outer_search_beam_width", self.cfg.outer_search_beam_width)
            ),
            "outer_search_branching_factor": int(
                overrides.get("outer_search_branching_factor", self.cfg.outer_search_branching_factor)
            ),
            "outer_search_max_expansions": int(
                overrides.get("outer_search_max_expansions", self.cfg.outer_search_max_expansions)
            ),
            "outer_search_unit": str(
                overrides.get("outer_search_unit", self.cfg.outer_search_unit)
            ),
            "representative_selection_rule": str(
                overrides.get("representative_selection_rule", self.cfg.representative_selection_rule)
            ),
            "lock_seed_basis": bool(lock_seed_basis),
            "enable_piecewise_basis": bool(enable_piecewise_basis),
            "gate_feature_names": tuple(str(value) for value in tuple(gate_feature_names)),
            "gate_quantiles": tuple(float(value) for value in tuple(self.cfg.gate_quantiles)),
            "assembler_max_added_terms": int(
                overrides.get("orth_assembler_max_added_terms", self.cfg.orth_assembler_max_added_terms)
            ),
            "assembler_topk_features": int(
                overrides.get("orth_assembler_topk_features", self.cfg.orth_assembler_topk_features)
            ),
            "assembler_max_pair_terms": int(
                overrides.get("orth_assembler_max_pair_terms", self.cfg.orth_assembler_max_pair_terms)
            ),
            "assembler_max_candidates_per_iter": int(
                overrides.get(
                    "orth_assembler_max_candidates_per_iter",
                    self.cfg.orth_assembler_max_candidates_per_iter,
                )
            ),
            "assembler_candidate_keep_top": int(
                overrides.get(
                    "orth_assembler_candidate_keep_top",
                    self.cfg.orth_assembler_candidate_keep_top,
                )
            ),
            "assembler_max_expr_depth": int(
                overrides.get("orth_assembler_max_expr_depth", self.cfg.orth_assembler_max_expr_depth)
            ),
            "assembler_ridge_l2": float(
                overrides.get("orth_assembler_ridge_l2", self.cfg.orth_assembler_ridge_l2)
            ),
            "assembler_basis_binding_mode": str(
                overrides.get(
                    "orth_assembler_basis_binding_mode",
                    self.cfg.orth_assembler_basis_binding_mode,
                )
            ),
            "assembler_escape_policy": str(
                overrides.get(
                    "orth_assembler_escape_policy",
                    self.cfg.orth_assembler_escape_policy,
                )
            ),
            "assembler_escape_feature_names": tuple(
                str(value)
                for value in tuple(
                    overrides.get(
                        "orth_assembler_escape_feature_names",
                        self.cfg.orth_assembler_escape_feature_names,
                    )
                    or ()
                )
            ),
            "cross_explanatory_rejection_mode": str(
                overrides.get(
                    "cross_explanatory_rejection_mode",
                    self.cfg.cross_explanatory_rejection_mode,
                )
            ),
            "trivial_nonlinearity_penalty_mode": str(
                overrides.get(
                    "trivial_nonlinearity_penalty_mode",
                    self.cfg.trivial_nonlinearity_penalty_mode,
                )
            ),
            "environment_invariance_audit_mode": str(
                overrides.get(
                    "environment_invariance_audit_mode",
                    self.cfg.environment_invariance_audit_mode,
                )
            ),
            "periodic_equivalence_disambiguation_mode": str(
                overrides.get(
                    "periodic_equivalence_disambiguation_mode",
                    self.cfg.periodic_equivalence_disambiguation_mode,
                )
            ),
            "phase_spectrum_audit_mode": str(
                overrides.get(
                    "phase_spectrum_audit_mode",
                    self.cfg.phase_spectrum_audit_mode,
                )
            ),
            "periodic_family_prior_mode": str(
                overrides.get(
                    "periodic_family_prior_mode",
                    self.cfg.periodic_family_prior_mode,
                )
            ),
            "periodic_family_prior_weight": float(
                overrides.get(
                    "periodic_family_prior_weight",
                    self.cfg.periodic_family_prior_weight,
                )
            ),
            "periodic_candidate_screen_reserve": int(
                overrides.get(
                    "periodic_candidate_screen_reserve",
                    self.cfg.periodic_candidate_screen_reserve,
                )
            ),
            "residual_regime_identification_mode": str(
                overrides.get(
                    "residual_regime_identification_mode",
                    self.cfg.residual_regime_identification_mode,
                )
            ),
            "regional_correction_basis_mode": str(
                overrides.get(
                    "regional_correction_basis_mode",
                    self.cfg.regional_correction_basis_mode,
                )
            ),
            "regional_correction_promotion_mode": str(
                overrides.get(
                    "regional_correction_promotion_mode",
                    self.cfg.regional_correction_promotion_mode,
                )
            ),
            "regional_correction_feature_scope": str(
                overrides.get(
                    "regional_correction_feature_scope",
                    self.cfg.regional_correction_feature_scope,
                )
            ),
            "regional_correction_topk": int(
                overrides.get(
                    "regional_correction_topk",
                    self.cfg.regional_correction_topk,
                )
            ),
            "regional_correction_min_r2_gain": float(
                overrides.get(
                    "regional_correction_min_r2_gain",
                    self.cfg.regional_correction_min_r2_gain,
                )
            ),
            "regional_correction_search_mode": str(
                overrides.get(
                    "regional_correction_search_mode",
                    self.cfg.regional_correction_search_mode,
                )
            ),
            "regional_local_search_beam_width": int(
                overrides.get(
                    "regional_local_search_beam_width",
                    self.cfg.regional_local_search_beam_width,
                )
            ),
            "regional_local_search_branching_factor": int(
                overrides.get(
                    "regional_local_search_branching_factor",
                    self.cfg.regional_local_search_branching_factor,
                )
            ),
            "regional_local_search_max_expansions": int(
                overrides.get(
                    "regional_local_search_max_expansions",
                    self.cfg.regional_local_search_max_expansions,
                )
            ),
            "proxy_group_policy": str(
                overrides.get(
                    "proxy_group_policy",
                    self.cfg.proxy_group_policy,
                )
            ),
            "source_overlap_penalty_mode": str(
                overrides.get(
                    "source_overlap_penalty_mode",
                    self.cfg.source_overlap_penalty_mode,
                )
            ),
            "search_graph_cache_enabled": bool(
                overrides.get("search_graph_cache_enabled", self.cfg.search_graph_cache_enabled)
            ),
        }

    def _build_consensus_seed_state(
        self,
        *,
        seed_genome: Sequence[Mapping[str, Any]],
        selected_core_rows: Sequence[Mapping[str, Any]] | None,
        feature_names: Sequence[str],
        target_names: Sequence[str],
        equivalence_mode: str,
        signature_fields: Mapping[str, Any] | None,
    ) -> Any:
        TrainerState = self._ml["TrainerState"]
        signature = _mapping(signature_fields)
        return TrainerState(
            trainer_name="symbolic_orthogonal",
            payload={
                "schema_version": 1,
                "trainer_name": "symbolic_orthogonal",
                "search_completed": True,
                "genome": tuple(dict(term) for term in tuple(seed_genome)),
                "assembled_genome": tuple(dict(term) for term in tuple(seed_genome)),
                "parameter_values": {},
                "readout_weight": np.zeros((max(1, len(tuple(seed_genome))), 1), dtype=float),
                "readout_bias": np.zeros((1,), dtype=float),
                "residual_std": np.ones((1,), dtype=float),
                "feature_names": tuple(str(value) for value in tuple(feature_names)),
                "target_names": tuple(str(value) for value in tuple(target_names)),
                "consensus_prior_rows": tuple(
                    dict(row) for row in tuple(selected_core_rows or ()) if isinstance(row, Mapping)
                ),
                "search_summary": {
                    "protocol": "nsgablack_orchestrated_mlblack_consensus_locked_core",
                    "equivalence_mode": str(equivalence_mode),
                    "consensus_prior_rows": int(
                        sum(1 for row in tuple(selected_core_rows or ()) if isinstance(row, Mapping))
                    ),
                },
                "seed_protocol": "consensus_locked_core",
            },
            metadata={
                "resume_source": "nsgablack_consensus_locked_core",
                "consensus_equivalence_mode": str(equivalence_mode),
                "consensus_prior_rows": _jsonable(
                    [dict(row) for row in tuple(selected_core_rows or ()) if isinstance(row, Mapping)]
                ),
                "training_signature": _jsonable(signature),
            },
            schema_signature=None if signature.get("schema_signature") is None else str(signature.get("schema_signature")),
            feature_signature=None if signature.get("feature_signature") is None else str(signature.get("feature_signature")),
            target_signature=None if signature.get("target_signature") is None else str(signature.get("target_signature")),
            objective_signature=None if signature.get("objective_signature") is None else str(signature.get("objective_signature")),
            pipeline_signature=None if signature.get("pipeline_signature") is None else str(signature.get("pipeline_signature")),
            numericizer_signature=None if signature.get("numericizer_signature") is None else str(signature.get("numericizer_signature")),
            regime_signature=None if signature.get("regime_signature") is None else str(signature.get("regime_signature")),
            symbolic_family_signature=None
            if signature.get("symbolic_family_signature") is None
            else str(signature.get("symbolic_family_signature")),
        )

    def _artifact_run_summary(
        self,
        *,
        artifact: Any,
        metrics: Mapping[str, Any],
        tracker: Mapping[str, Any],
        output_dir: Path,
        run_name: str,
        run_index: int,
        search_seed: int,
        phase: str,
        lane_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        annotate_basis_entries = self._ml["annotate_basis_entries"]
        metadata = dict(getattr(artifact, "metadata", {}) or {})
        symbolic = dict(metadata.get("symbolic", {}) or {})
        structure_engine = dict(symbolic.get("structure_engine", {}) or {})
        structure_engine_meta = dict(structure_engine.get("metadata", {}) or {})
        schema = dict(metadata.get("symbolic_artifact_schema", {}) or {})
        head_semantics = dict(schema.get("head_semantics", {}) or {})
        basis_structure = dict(schema.get("basis_structure", {}) or {})
        assembler_structure = dict(schema.get("assembler_structure", {}) or {})
        heterogeneous_lane_consensus = dict(schema.get("heterogeneous_lane_consensus", {}) or {})
        orthogonality_status = dict(basis_structure.get("orthogonality_status", {}) or {})
        fit_context = dict(metadata.get("fit_context", {}) or {})
        lane_context = dict(
            metadata.get("heterogeneous_multi_lane_context", {})
            or symbolic.get("heterogeneous_multi_lane_context", {})
            or fit_context.get("heterogeneous_multi_lane_context", {})
            or {}
        )
        lane_spec_payload = dict(lane_payload or {})
        if not lane_context and lane_spec_payload:
            lane_context = {
                "protocol": lane_spec_payload.get("protocol"),
                "lane_id": lane_spec_payload.get("lane_id"),
                "lane_family": lane_spec_payload.get("lane_family"),
                "lane_label": lane_spec_payload.get("lane_label"),
                "lane_description": lane_spec_payload.get("lane_description"),
                "lane_weight": lane_spec_payload.get("lane_weight"),
                "screening_protocol": lane_spec_payload.get("screening_protocol"),
                "challenger_objective_protocol": lane_spec_payload.get("challenger_objective_protocol"),
                "pool_expansion_bias_protocol": lane_spec_payload.get("pool_expansion_bias_protocol"),
                "representative_selection_rule": lane_spec_payload.get("representative_selection_rule"),
                "outer_search_unit": lane_spec_payload.get("outer_search_unit"),
                "lane_spec": lane_spec_payload.get("lane_spec") or _jsonable(lane_spec_payload),
            }
        basis_context = dict(
            metadata.get("basis_context", {})
            or symbolic.get("basis_context", {})
            or basis_structure.get("basis_context", {})
            or {}
        )
        basis_object_gradient_pool = dict(
            metadata.get("basis_object_gradient_pool", {})
            or symbolic.get("basis_object_gradient_pool", {})
            or dict(symbolic.get("inner_symbolic_search", {}) or {}).get("object_gradient_pool", {})
            or assembler_structure.get("object_gradient_pool", {})
            or {}
        )
        truth_recovery = dict(schema.get("truth_contract_recovery", {}) or {})
        outer_objective = dict(
            metadata.get("orthogonal_search_objective", {})
            or schema.get("orthogonal_search_objective", {})
            or {}
        )
        search_summary = dict(metadata.get("search", {}) or {})
        basis_rows = _basis_rows_from_artifact(artifact)
        outer_basis_genome = _outer_basis_genome_from_artifact(artifact)
        basis_entries = annotate_basis_entries(basis_rows, outer_basis_genome)
        training_signature = dict(metadata.get("training_signature", {}) or {})
        consensus_prior_rows = [
            dict(row)
            for row in tuple(
                metadata.get("consensus_prior_rows")
                or symbolic.get("consensus_prior_rows")
                or ()
            )
            if isinstance(row, Mapping)
        ]
        joint_core_scores = [
            float(row.get("joint_core_score"))
            for row in consensus_prior_rows
            if isinstance(row.get("joint_core_score"), (int, float))
        ]
        cross_lane_scores = [
            float(row.get("cross_lane_stability"))
            for row in consensus_prior_rows
            if isinstance(row.get("cross_lane_stability"), (int, float))
        ]
        cross_lane_support_rates = [
            float(row.get("cross_lane_support_rate"))
            for row in consensus_prior_rows
            if isinstance(row.get("cross_lane_support_rate"), (int, float))
        ]
        cross_lane_family_support_rates = [
            float(row.get("cross_lane_family_support_rate"))
            for row in consensus_prior_rows
            if isinstance(row.get("cross_lane_family_support_rate"), (int, float))
        ]
        return {
            "phase": str(phase),
            "run_name": str(run_name),
            "run_index": int(run_index),
            "search_seed": int(search_seed),
            "run_id": str(tracker.get("run_id") or ""),
            "output_dir": str(output_dir),
            "artifact_id": str(getattr(artifact, "artifact_id", "")),
            "final_expression": _artifact_expression(artifact),
            "metrics": _jsonable(dict(metrics)),
            "test_rmse": dict(metrics.get("test", {}) or {}).get("rmse"),
            "test_r2": dict(metrics.get("test", {}) or {}).get("r2"),
            "orthogonality_score": orthogonality_status.get("orthogonality_score"),
            "pair_abs_corr_mean": orthogonality_status.get("pair_abs_corr_mean"),
            "residual_gain_mean": orthogonality_status.get("residual_gain_mean"),
            "semantic_unique_ratio": orthogonality_status.get("semantic_unique_ratio"),
            "search_driver": (
                str(structure_engine.get("search_driver") or metadata.get("search_driver") or "").strip()
                or None
            ),
            "screening_protocol": (
                str(
                    structure_engine.get("screening_protocol")
                    or structure_engine_meta.get("screening_protocol")
                    or ""
                ).strip()
                or None
            ),
            "outer_search_protocol": (
                str(
                    structure_engine.get("outer_search_protocol")
                    or structure_engine_meta.get("outer_search_protocol")
                    or search_summary.get("protocol")
                    or ""
                ).strip()
                or None
            ),
            "structure_head": _first_text(
                metadata.get("structure_head"),
                symbolic.get("structure_head"),
                head_semantics.get("structure_head"),
                assembler_structure.get("structure_head"),
                structure_engine.get("structure_head"),
                structure_engine_meta.get("structure_head"),
            ),
            "search_input_space": _first_text(
                metadata.get("search_input_space"),
                symbolic.get("search_input_space"),
                head_semantics.get("search_input_space"),
                assembler_structure.get("search_input_space"),
                structure_engine.get("search_input_space"),
                structure_engine_meta.get("search_input_space"),
            ),
            "pool_expansion_unit": _first_text(
                metadata.get("pool_expansion_unit"),
                symbolic.get("pool_expansion_unit"),
                head_semantics.get("pool_expansion_unit"),
                assembler_structure.get("pool_expansion_unit"),
                structure_engine.get("pool_expansion_unit"),
                structure_engine_meta.get("pool_expansion_unit"),
            ),
            "gradient_guidance_mode": _first_text(
                metadata.get("gradient_guidance_mode"),
                symbolic.get("gradient_guidance_mode"),
                head_semantics.get("gradient_guidance_mode"),
                assembler_structure.get("gradient_guidance_mode"),
                structure_engine.get("gradient_guidance_mode"),
                structure_engine_meta.get("gradient_guidance_mode"),
            ),
            "basis_binding_mode": _first_text(
                metadata.get("basis_binding_mode"),
                symbolic.get("basis_binding_mode"),
                head_semantics.get("basis_binding_mode"),
                assembler_structure.get("basis_binding_mode"),
            ),
            "escape_policy": _first_text(
                metadata.get("escape_policy"),
                symbolic.get("escape_policy"),
                head_semantics.get("escape_policy"),
                assembler_structure.get("escape_policy"),
            ),
            "equivalence_expression_protocol": _first_text(
                metadata.get("equivalence_expression_protocol"),
                symbolic.get("equivalence_expression_protocol"),
                _mapping(schema.get("equivalence_expression_handling")).get("protocol"),
            ),
            "equivalence_expression_mode": _first_text(
                metadata.get("equivalence_expression_mode"),
                symbolic.get("equivalence_expression_mode"),
                _mapping(schema.get("equivalence_expression_handling")).get("mode"),
            ),
            "equivalence_class_scope": _first_text(
                metadata.get("equivalence_class_scope"),
                symbolic.get("equivalence_class_scope"),
                _mapping(schema.get("equivalence_expression_handling")).get("class_scope"),
            ),
            "interference_feature_protocol": _first_text(
                metadata.get("interference_feature_protocol"),
                symbolic.get("interference_feature_protocol"),
                _mapping(schema.get("interference_feature_handling")).get("protocol"),
            ),
            "interference_feature_mode": _first_text(
                metadata.get("interference_feature_mode"),
                symbolic.get("interference_feature_mode"),
                _mapping(schema.get("interference_feature_handling")).get("mode"),
            ),
            "cross_explanatory_rejection_mode": _first_text(
                metadata.get("cross_explanatory_rejection_mode"),
                symbolic.get("cross_explanatory_rejection_mode"),
                _mapping(schema.get("interference_feature_handling")).get("cross_explanatory_rejection_mode"),
            ),
            "trivial_nonlinearity_penalty_mode": _first_text(
                metadata.get("trivial_nonlinearity_penalty_mode"),
                symbolic.get("trivial_nonlinearity_penalty_mode"),
                _mapping(schema.get("interference_feature_handling")).get("trivial_nonlinearity_penalty_mode"),
            ),
            "environment_invariance_audit_mode": _first_text(
                metadata.get("environment_invariance_audit_mode"),
                symbolic.get("environment_invariance_audit_mode"),
                _mapping(schema.get("interference_feature_handling")).get("environment_invariance_audit_mode"),
            ),
            "periodic_equivalence_disambiguation_mode": _first_text(
                metadata.get("periodic_equivalence_disambiguation_mode"),
                symbolic.get("periodic_equivalence_disambiguation_mode"),
                _mapping(schema.get("periodic_equivalence_disambiguation")).get("mode"),
            ),
            "phase_spectrum_audit_mode": _first_text(
                metadata.get("phase_spectrum_audit_mode"),
                symbolic.get("phase_spectrum_audit_mode"),
                _mapping(schema.get("periodic_equivalence_disambiguation")).get("phase_spectrum_audit_mode"),
            ),
            "periodic_family_prior_mode": _first_text(
                metadata.get("periodic_family_prior_mode"),
                symbolic.get("periodic_family_prior_mode"),
                _mapping(schema.get("periodic_equivalence_disambiguation")).get("periodic_family_prior_mode"),
            ),
            "regional_correction_protocol": _first_text(
                metadata.get("regional_correction_protocol"),
                symbolic.get("regional_correction_protocol"),
                _mapping(schema.get("regional_correction_basis")).get("protocol"),
            ),
            "regional_correction_promotion_mode": _first_text(
                metadata.get("regional_correction_promotion_mode"),
                symbolic.get("regional_correction_promotion_mode"),
                _mapping(schema.get("regional_correction_basis")).get("regional_correction_promotion_mode"),
            ),
            "regional_correction_feature_scope": _first_text(
                metadata.get("regional_correction_feature_scope"),
                symbolic.get("regional_correction_feature_scope"),
                _mapping(schema.get("regional_correction_basis")).get("regional_correction_feature_scope"),
            ),
            "regional_correction_search_mode": _first_text(
                metadata.get("regional_correction_search_mode"),
                symbolic.get("regional_correction_search_mode"),
                _mapping(schema.get("regional_correction_basis")).get("regional_correction_search_mode"),
            ),
            "proxy_group_policy": _first_text(
                metadata.get("proxy_group_policy"),
                symbolic.get("proxy_group_policy"),
                _mapping(schema.get("interference_feature_handling")).get("proxy_group_policy"),
            ),
            "source_overlap_penalty_mode": _first_text(
                metadata.get("source_overlap_penalty_mode"),
                symbolic.get("source_overlap_penalty_mode"),
                _mapping(schema.get("interference_feature_handling")).get("source_overlap_penalty_mode"),
            ),
            "equivalence_expression_handling": _jsonable(schema.get("equivalence_expression_handling")),
            "interference_feature_handling": _jsonable(schema.get("interference_feature_handling")),
            "periodic_equivalence_disambiguation": _jsonable(schema.get("periodic_equivalence_disambiguation")),
            "regional_correction_basis": _jsonable(schema.get("regional_correction_basis")),
            "heterogeneous_multi_lane_protocol": _first_text(
                metadata.get("heterogeneous_multi_lane_protocol"),
                lane_context.get("protocol"),
                fit_context.get("heterogeneous_multi_lane_protocol"),
            ),
            "lane_id": _first_text(
                metadata.get("lane_id"),
                heterogeneous_lane_consensus.get("lane_id"),
                lane_context.get("lane_id"),
                lane_spec_payload.get("lane_id"),
            ),
            "lane_family": _first_text(
                metadata.get("lane_family"),
                heterogeneous_lane_consensus.get("lane_family"),
                lane_context.get("lane_family"),
                lane_spec_payload.get("lane_family"),
            ),
            "challenger_objective_protocol": _first_text(
                metadata.get("challenger_objective_protocol"),
                heterogeneous_lane_consensus.get("challenger_objective_protocol"),
                lane_context.get("challenger_objective_protocol"),
                lane_spec_payload.get("challenger_objective_protocol"),
            ),
            "pool_expansion_bias_protocol": _first_text(
                metadata.get("pool_expansion_bias_protocol"),
                heterogeneous_lane_consensus.get("pool_expansion_bias_protocol"),
                lane_context.get("pool_expansion_bias_protocol"),
                lane_spec_payload.get("pool_expansion_bias_protocol"),
            ),
            "representative_selection_rule": _first_text(
                metadata.get("representative_selection_rule"),
                heterogeneous_lane_consensus.get("representative_selection_rule"),
                lane_context.get("representative_selection_rule"),
                lane_spec_payload.get("representative_selection_rule"),
            ),
            "outer_search_unit": _first_text(
                metadata.get("outer_search_unit"),
                symbolic.get("outer_search_unit"),
                lane_context.get("outer_search_unit"),
                lane_spec_payload.get("outer_search_unit"),
            ),
            "consensus_prior_row_count": int(len(consensus_prior_rows)),
            "joint_core_score": None if not joint_core_scores else float(max(joint_core_scores)),
            "joint_core_score_mean": None
            if not joint_core_scores
            else float(sum(joint_core_scores) / float(len(joint_core_scores))),
            "cross_lane_stability": (
                heterogeneous_lane_consensus.get("cross_lane_stability")
                if heterogeneous_lane_consensus.get("cross_lane_stability") is not None
                else None if not cross_lane_scores else float(max(cross_lane_scores))
            ),
            "cross_lane_support_rate": (
                heterogeneous_lane_consensus.get("cross_lane_support_rate")
                if heterogeneous_lane_consensus.get("cross_lane_support_rate") is not None
                else None if not cross_lane_support_rates else float(max(cross_lane_support_rates))
            ),
            "cross_lane_family_support_rate": (
                heterogeneous_lane_consensus.get("cross_lane_family_support_rate")
                if heterogeneous_lane_consensus.get("cross_lane_family_support_rate") is not None
                else None
                if not cross_lane_family_support_rates
                else float(max(cross_lane_family_support_rates))
            ),
            "outer_objective_score": outer_objective.get("outer_score"),
            "inner_fit_score": outer_objective.get("inner_fit_score"),
            "periodic_equivalence_score": outer_objective.get("periodic_equivalence_score"),
            "periodic_equivalence_penalty": outer_objective.get("periodic_equivalence_penalty"),
            "regional_correction_score": outer_objective.get("regional_correction_score"),
            "exact_basis_hit_score": truth_recovery.get("exact_basis_hit_score"),
            "exact_term_recovery_score": truth_recovery.get("exact_term_recovery_score"),
            "phase_equivalent_term_recovery_score": truth_recovery.get(
                "phase_equivalent_term_recovery_score"
            ),
            "family_level_term_recovery_score": truth_recovery.get(
                "family_level_term_recovery_score"
            ),
            "truth_recovery": _jsonable(truth_recovery),
            "basis_context": _jsonable(basis_context),
            "basis_object_gradient_pool": _jsonable(basis_object_gradient_pool),
            "basis_rows": _jsonable(basis_rows),
            "basis_entries": _jsonable(basis_entries),
            "outer_basis_genome": _jsonable(outer_basis_genome),
            "search_summary": _jsonable(search_summary),
            "training_signature": _jsonable(training_signature),
            "heterogeneous_multi_lane_context": _jsonable(lane_context),
            "heterogeneous_lane_consensus": _jsonable(heterogeneous_lane_consensus),
            "tracker": _jsonable(dict(tracker)),
        }

    def _run_flow_once(
        self,
        *,
        bundle: Any,
        trainer_params: Mapping[str, Any],
        training_init: Any,
        run_name: str,
        output_dir: Path,
        db_path: str,
        namespace: str,
        tag: str,
        run_index: int,
        search_seed: int,
        phase: str,
        lane_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        CapabilitySpec = self._ml["CapabilitySpec"]
        FlowAssemblySpec = self._ml["FlowAssemblySpec"]
        NumericizerSpec = self._ml["NumericizerSpec"]
        TrainerAssemblySpec = self._ml["TrainerAssemblySpec"]
        SemanticTrainFlowSpec = self._ml["SemanticTrainFlowSpec"]
        run_semantic_train_flow = self._ml["run_semantic_train_flow"]

        capabilities: tuple[Any, ...] = tuple()
        if bool(self.cfg.enable_experiment_tracker) and str(db_path).strip():
            capabilities = (
                CapabilitySpec(
                    key="experiment_tracker",
                    params={
                        "db_path": str(db_path),
                        "namespace": str(namespace),
                        "tag": str(tag),
                        "io_mode": "batched",
                        "commit_interval": 0,
                    },
                ),
            )
        spec = SemanticTrainFlowSpec(
            assembly=FlowAssemblySpec(
                trainer=TrainerAssemblySpec(
                    trainer_key="symbolic",
                    trainer_params=dict(trainer_params),
                ),
                numericizer=NumericizerSpec(key="default", params={}),
                capabilities=capabilities,
            ),
            eval_splits=("train", "test"),
            output_dir=str(output_dir),
            save_artifact=bool(self.cfg.save_artifact),
            save_report=bool(self.cfg.save_report),
            capability_strict=bool(self.cfg.capability_strict),
            run_name=str(run_name),
            training_init=training_init,
        )
        result = run_semantic_train_flow(bundle, spec=spec)
        tracker = dict(result.report.get("experiment_tracker", {}) or {})
        return self._artifact_run_summary(
            artifact=result.artifact,
            metrics=dict(result.metrics),
            tracker=tracker,
            output_dir=Path(result.output_dir or output_dir),
            run_name=run_name,
            run_index=run_index,
            search_seed=search_seed,
            phase=phase,
            lane_payload=lane_payload,
        )

    def _comparison_row(
        self,
        *,
        scenario: str,
        vanilla_runs: Sequence[Mapping[str, Any]],
        locked_runs: Sequence[Mapping[str, Any]],
        core_selection: Mapping[str, Any],
    ) -> dict[str, Any]:
        vanilla_best = _best_run(vanilla_runs) or {}
        locked_best = _best_run(locked_runs) or {}
        return {
            "scenario": str(scenario),
            "core_equivalence_mode": str(core_selection.get("equivalence_mode") or ""),
            "core_basis_count": int(len(tuple(core_selection.get("selected_core_rows", ()) or ()))),
            "locked_seed_terms": int(len(tuple(core_selection.get("seed_genome", ()) or ()))),
            "vanilla_run_count": int(len(tuple(vanilla_runs))),
            "locked_run_count": int(len(tuple(locked_runs))),
            "vanilla_best_test_rmse": vanilla_best.get("test_rmse"),
            "locked_best_test_rmse": locked_best.get("test_rmse"),
            "vanilla_best_exact_term_recovery_score": vanilla_best.get("exact_term_recovery_score"),
            "locked_best_exact_term_recovery_score": locked_best.get("exact_term_recovery_score"),
            "vanilla_best_phase_term_recovery_score": vanilla_best.get(
                "phase_equivalent_term_recovery_score"
            ),
            "locked_best_phase_term_recovery_score": locked_best.get(
                "phase_equivalent_term_recovery_score"
            ),
            "vanilla_best_family_term_recovery_score": vanilla_best.get(
                "family_level_term_recovery_score"
            ),
            "locked_best_family_term_recovery_score": locked_best.get(
                "family_level_term_recovery_score"
            ),
            "vanilla_best_outer_objective_score": vanilla_best.get("outer_objective_score"),
            "locked_best_outer_objective_score": locked_best.get("outer_objective_score"),
            "vanilla_mean_test_rmse": _mean_metric(vanilla_runs, "test_rmse"),
            "locked_mean_test_rmse": _mean_metric(locked_runs, "test_rmse"),
            "vanilla_mean_exact_term_recovery_score": _mean_metric(
                vanilla_runs,
                "exact_term_recovery_score",
            ),
            "locked_mean_exact_term_recovery_score": _mean_metric(
                locked_runs,
                "exact_term_recovery_score",
            ),
            "vanilla_mean_outer_objective_score": _mean_metric(
                vanilla_runs,
                "outer_objective_score",
            ),
            "locked_mean_outer_objective_score": _mean_metric(
                locked_runs,
                "outer_objective_score",
            ),
        }

    @staticmethod
    def _surface_artifact_role(artifact_id: str) -> str:
        aid = str(artifact_id or "").strip().lower()
        if "summary" in aid or "report" in aid or aid.endswith("_json"):
            return "report"
        if "table" in aid or "selection" in aid or "evolution" in aid or "export" in aid:
            return "export"
        return "artifact"

    @staticmethod
    def _artifact_mapping(
        value: Any,
    ) -> tuple[str | None, str | None, str | None, dict[str, Any]]:
        if isinstance(value, Mapping):
            path = str(value.get("path") or "").strip() or None
            uri = str(value.get("uri") or "").strip() or None
            fmt = str(value.get("format") or "").strip() or None
            metadata = {
                str(key): _jsonable(raw)
                for key, raw in dict(value).items()
                if str(key) not in {"path", "uri", "format"}
            }
            return path, uri, fmt, metadata
        if isinstance(value, (str, Path)):
            path = str(Path(str(value)).expanduser().resolve())
            fmt = "dir" if Path(path).exists() and Path(path).is_dir() else (Path(path).suffix.lstrip(".") or None)
            return path, None, fmt, {}
        return None, None, None, {"value": _jsonable(value)}

    def _persist_surface_row(
        self,
        *,
        db_path: str,
        framework: str,
        namespace: str,
        run_id: str,
        status: str,
        surface_kind: str,
        surface_key: str,
        surface_label: str,
        driver_ref: str | None,
        family_ref: str | None,
        subject_kind: str | None,
        subject_key: str | None,
        params_json: Mapping[str, Any],
        result_payload: Mapping[str, Any],
        artifacts: Mapping[str, Any],
        output_dir: str | None,
        primary_metric_name: str | None,
        primary_metric_value: float | None,
        component_slots_json: Mapping[str, Any] | None = None,
        assembly_metadata_json: Mapping[str, Any] | None = None,
        run_metadata_json: Mapping[str, Any] | None = None,
        tags: Sequence[str] = (),
        mount_order: Sequence[str] = (),
        started_at_utc: str | None = None,
        finished_at_utc: str | None = None,
        duration_s: float | None = None,
        trainer_ref: str | None = None,
        solver_ref: str | None = None,
        component_refs: Sequence[str] = (),
    ) -> None:
        finished = str(finished_at_utc or _utc_now_iso())
        started = str(started_at_utc or finished)
        surface_record = make_surface_record(
            framework=str(framework),
            surface_kind=str(surface_kind),
            surface_key=str(surface_key),
            surface_label=str(surface_label),
            driver_ref=driver_ref,
            family_ref=family_ref,
            tags=tuple(tags),
            metadata_json={
                "protocol": "nsgablack_orchestrated_mlblack_symbolic_consensus_v2",
                "component_refs": list(tuple(component_refs)),
            },
        )
        assembly_record = make_assembly_record(
            framework=str(framework),
            surface_key=str(surface_key),
            assembly_key=str(surface_key),
            driver_ref=driver_ref,
            family_ref=family_ref,
            trainer_ref=trainer_ref,
            solver_ref=solver_ref,
            component_refs=tuple(component_refs),
            provider_refs=(),
            plugin_refs=(),
            pipeline_refs=(),
            mount_order=tuple(mount_order or component_refs),
            component_slots_json=dict(component_slots_json or {}),
            metadata_json=dict(assembly_metadata_json or {}),
        )
        artifact_records = []
        for artifact_id, artifact_value in dict(artifacts or {}).items():
            path, uri, fmt, metadata = self._artifact_mapping(artifact_value)
            artifact_records.append(
                make_artifact_record(
                    framework=str(framework),
                    run_id=str(run_id),
                    artifact_id=str(artifact_id),
                    artifact_kind=str(fmt or "artifact"),
                    artifact_role=self._surface_artifact_role(str(artifact_id)),
                    producer_ref=driver_ref,
                    surface_key=str(surface_key),
                    assembly_signature=assembly_record.assembly_signature,
                    path=path,
                    uri=uri,
                    format=fmt,
                    created_at_utc=finished,
                    metrics_json={
                        "primary_metric_name": primary_metric_name,
                        "primary_metric_value": primary_metric_value,
                    },
                    metadata_json=metadata,
                    tags=("artifact", self._surface_artifact_role(str(artifact_id))),
                )
            )
        run_record = make_run_record(
            framework=str(framework),
            run_id=str(run_id),
            namespace=str(namespace),
            tag=str(dict(result_payload).get("tag") or "") or None,
            status=str(status),
            started_at_utc=started,
            finished_at_utc=finished,
            duration_s=duration_s,
            surface_key=str(surface_key),
            surface_kind=str(surface_kind),
            surface_signature=surface_record.surface_signature,
            assembly_signature=assembly_record.assembly_signature,
            subject_kind=subject_kind,
            subject_key=subject_key,
            subject_json={
                "surface_key": surface_key,
                "family_ref": family_ref,
            },
            params_json=dict(_jsonable(params_json)),
            driver_ref=driver_ref,
            family_ref=family_ref,
            output_dir=output_dir,
            primary_metric_name=primary_metric_name,
            primary_metric_value=primary_metric_value,
            metric_summary_json={
                "primary_metric_name": primary_metric_name,
                "primary_metric_value": primary_metric_value,
            },
            result_json=dict(_jsonable(result_payload)),
            component_refs=tuple(component_refs),
            artifact_ids=tuple(str(key) for key in dict(artifacts or {}).keys()),
            metadata_json=dict(_jsonable(run_metadata_json or {})),
        )
        persist_runtime_surface_records(
            db_path,
            surface_record=surface_record,
            assembly_record=assembly_record,
            run_record=run_record,
            artifact_records=artifact_records,
            result_payload=result_payload,
        )

    def _core_basis_evolution_rows(
        self,
        *,
        cycle_index: int,
        cycle_key: str,
        core_tables: Mapping[str, Any],
        core_selection: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        selected_rows = tuple(core_selection.get("selected_core_rows", ()) or ())
        selected_sources = {
            _basis_identity(dict(row)): str(dict(row).get("selection_source") or "")
            for row in selected_rows
            if isinstance(row, Mapping)
        }
        rows: list[dict[str, Any]] = []
        for mode, raw_rows in dict(core_tables).items():
            for rank, raw_row in enumerate(tuple(raw_rows or ())):
                if not isinstance(raw_row, Mapping):
                    continue
                row = dict(raw_row)
                basis_key = _basis_identity(row)
                rows.append(
                    {
                        "cycle_index": int(cycle_index),
                        "cycle_key": str(cycle_key),
                        "equivalence_mode": str(mode),
                        "rank": int(rank),
                        "basis_key": basis_key,
                        "basis_class_id": row.get("basis_class_id"),
                        "representative_expression": row.get("representative_expression")
                        or row.get("expression"),
                        "representative_semantic_family": row.get("representative_semantic_family")
                        or row.get("semantic_family"),
                        "support_count": row.get("support_count"),
                        "support_rate": row.get("support_rate"),
                        "support_weight": row.get("support_weight"),
                        "support_weight_rate": row.get("support_weight_rate"),
                        "exact_stability": row.get("exact_stability"),
                        "multi_run_core_frequency": row.get("multi_run_core_frequency"),
                        "cross_lane_support_count": row.get("cross_lane_support_count"),
                        "cross_lane_support_rate": row.get("cross_lane_support_rate"),
                        "cross_lane_family_count": row.get("cross_lane_family_count"),
                        "cross_lane_family_support_rate": row.get("cross_lane_family_support_rate"),
                        "cross_lane_stability": row.get("cross_lane_stability"),
                        "joint_core_score": row.get("joint_core_score"),
                        "occurrence_count": row.get("occurrence_count"),
                        "run_ids": _jsonable(row.get("run_ids")),
                        "selected_as_core": bool(row.get("selected_as_core"))
                        or basis_key in selected_sources,
                        "selection_source": selected_sources.get(basis_key) or row.get("selection_source"),
                    }
                )
        return rows

    def _persist_inner_run_surface(
        self,
        *,
        db_path: str,
        plan: Mapping[str, Any],
        signature: str,
        run_summary: Mapping[str, Any],
    ) -> str:
        phase = str(run_summary.get("phase") or "orthogonal")
        cycle_index = int(run_summary.get("cycle_index", 0) or 0)
        output_dir = Path(str(run_summary.get("output_dir") or Path.cwd())).expanduser().resolve()
        summary_path = output_dir / "nsgablack_runtime_surface.inner_run_summary.json"
        _write_json(
            summary_path,
            {
                "protocol": "nsgablack_orchestrated_mlblack_symbolic_consensus_v2",
                "signature": str(signature),
                "run_summary": _jsonable(run_summary),
            },
        )
        run_id = str(run_summary.get("run_id") or f"{plan['namespace']}__{signature}__{phase}__cycle_{cycle_index:02d}")
        tag = str(
            run_summary.get("tracker", {}).get("tag")
            or f"{plan['tag_prefix']}:{plan['benchmark_key']}:{signature}:{phase}:cycle_{cycle_index:02d}"
        )
        result_payload = {
            "tag": tag,
            "phase": phase,
            "cycle_index": int(cycle_index),
            "stage_level": "L3",
            "heterogeneous_multi_lane_protocol": run_summary.get("heterogeneous_multi_lane_protocol"),
            "lane_id": run_summary.get("lane_id"),
            "lane_family": run_summary.get("lane_family"),
            "challenger_objective_protocol": run_summary.get("challenger_objective_protocol"),
            "pool_expansion_bias_protocol": run_summary.get("pool_expansion_bias_protocol"),
            "cross_lane_stability": run_summary.get("cross_lane_stability"),
            "heterogeneous_multi_lane_context": _jsonable(
                run_summary.get("heterogeneous_multi_lane_context")
            ),
            "heterogeneous_lane_consensus": _jsonable(
                run_summary.get("heterogeneous_lane_consensus")
            ),
            "run_summary": _jsonable(run_summary),
        }
        self._persist_surface_row(
            db_path=db_path,
            framework="mlblack",
            namespace=str(plan["namespace"]),
            run_id=run_id,
            status=str(run_summary.get("tracker", {}).get("status") or "completed"),
            surface_kind="flow",
            surface_key=f"flow:mlblack.symbolic_consensus.{phase}",
            surface_label=f"mlblack symbolic consensus {phase} run",
            driver_ref="trainer:symbolic_orthogonal",
            family_ref=f"benchmark:{plan['benchmark_key']}",
            subject_kind="benchmark",
            subject_key=str(plan["benchmark_key"]),
            params_json={
                "signature": signature,
                "phase": phase,
                "cycle_index": int(cycle_index),
                "stage_key": str(run_summary.get("stage_key") or ""),
                "search_seed": run_summary.get("search_seed"),
            },
            result_payload=result_payload,
            artifacts={
                "inner_run_summary_json": {
                    "path": str(summary_path),
                    "format": "json",
                    "title": "Inner run surface summary",
                },
                "mlblack_output_dir": {
                    "path": str(output_dir),
                    "format": "dir",
                    "title": "mlblack output directory",
                },
            },
            output_dir=str(output_dir),
            primary_metric_name="test_rmse",
            primary_metric_value=_metric_float(run_summary.get("test_rmse"), default=float("nan")),
            component_slots_json={
                "trainer": "symbolic_orthogonal",
                "phase": phase,
                "cycle_index": int(cycle_index),
                "lane_id": run_summary.get("lane_id"),
            },
            assembly_metadata_json={
                "stage_level": "L3",
                "run_name": run_summary.get("run_name"),
                "artifact_id": run_summary.get("artifact_id"),
            },
            run_metadata_json={
                "signature": signature,
                "tracker": _jsonable(run_summary.get("tracker")),
            },
            tags=("runtime_surface", "mlblack", phase),
            mount_order=("trainer:symbolic_orthogonal",),
            trainer_ref="trainer:symbolic_orthogonal",
            component_refs=("trainer:symbolic_orthogonal",),
        )
        return str(summary_path)

    def _persist_stage_surface(
        self,
        *,
        db_path: str,
        plan: Mapping[str, Any],
        signature: str,
        cycle_index: int,
        stage_report: Mapping[str, Any],
        payload: Mapping[str, Any],
        artifacts: Mapping[str, Any],
        primary_metric_name: str,
        primary_metric_value: float | None,
        output_dir: str | None,
    ) -> None:
        cycle_key = str(stage_report.get("cycle_key") or f"cycle_{cycle_index:02d}")
        stage_key = str(stage_report.get("stage_key") or "stage")
        self._persist_surface_row(
            db_path=db_path,
            framework="nsgablack",
            namespace=str(plan["namespace"]),
            run_id=f"{plan['namespace']}__{signature}__{cycle_key}__{stage_key}",
            status=str(stage_report.get("status") or "completed"),
            surface_kind="solver",
            surface_key=f"solver:nsgablack.mlblack_symbolic_consensus.{stage_key}",
            surface_label=f"nsgablack {stage_key} stage",
            driver_ref="backend:mlblack_symbolic_consensus",
            family_ref=f"benchmark:{plan['benchmark_key']}",
            subject_kind="benchmark",
            subject_key=str(plan["benchmark_key"]),
            params_json={
                "signature": signature,
                "cycle_index": int(cycle_index),
                "stage_key": stage_key,
                "stage_level": str(stage_report.get("level") or "L3"),
            },
            result_payload={"tag": "", **dict(_jsonable(payload))},
            artifacts=artifacts,
            output_dir=output_dir,
            primary_metric_name=primary_metric_name,
            primary_metric_value=primary_metric_value,
            component_slots_json={
                "stage_key": stage_key,
                "stage_level": str(stage_report.get("level") or "L3"),
                "cycle_index": int(cycle_index),
            },
            assembly_metadata_json={"stage_report": _jsonable(stage_report)},
            run_metadata_json={"signature": signature},
            tags=("runtime_surface", "nsgablack", "stage", stage_key),
            mount_order=("backend:mlblack_symbolic_consensus",),
            solver_ref="solver_backend:mlblack_symbolic_consensus",
            component_refs=("backend:mlblack_symbolic_consensus",),
        )

    def _persist_cycle_surface(
        self,
        *,
        db_path: str,
        plan: Mapping[str, Any],
        signature: str,
        cycle_report: Mapping[str, Any],
        output_dir: str | None,
    ) -> None:
        cycle_index = int(cycle_report.get("cycle_index", 0) or 0)
        cycle_key = str(cycle_report.get("cycle_key") or f"cycle_{cycle_index:02d}")
        comparison = dict(cycle_report.get("comparison") or {})
        primary_metric_value = _metric_float(
            comparison.get("locked_best_test_rmse", comparison.get("vanilla_best_test_rmse")),
            default=float("nan"),
        )
        self._persist_surface_row(
            db_path=db_path,
            framework="nsgablack",
            namespace=str(plan["namespace"]),
            run_id=f"{plan['namespace']}__{signature}__{cycle_key}",
            status="completed",
            surface_kind="solver",
            surface_key="solver:nsgablack.mlblack_symbolic_consensus.consensus_cycle",
            surface_label="nsgablack consensus cycle",
            driver_ref="backend:mlblack_symbolic_consensus",
            family_ref=f"benchmark:{plan['benchmark_key']}",
            subject_kind="benchmark",
            subject_key=str(plan["benchmark_key"]),
            params_json={
                "signature": signature,
                "cycle_index": int(cycle_index),
                "stage_level": "L2",
            },
            result_payload={"tag": "", **dict(_jsonable(cycle_report))},
            artifacts=dict(cycle_report.get("artifact_paths") or {}),
            output_dir=output_dir,
            primary_metric_name="cycle_best_test_rmse",
            primary_metric_value=primary_metric_value,
            component_slots_json={
                "cycle_index": int(cycle_index),
                "cycle_key": cycle_key,
                "stage_level": "L2",
            },
            assembly_metadata_json={"cycle_report": _jsonable(cycle_report)},
            run_metadata_json={"signature": signature},
            tags=("runtime_surface", "nsgablack", "cycle"),
            mount_order=("backend:mlblack_symbolic_consensus",),
            solver_ref="solver_backend:mlblack_symbolic_consensus",
            component_refs=("backend:mlblack_symbolic_consensus",),
        )

    def solve(self, request: BackendSolveRequest) -> Mapping[str, Any]:
        self._ensure_mlblack_imports()
        plan = self._resolve_plan(request)

        build_known_relation_bundle = self._ml["build_known_relation_bundle"]
        build_core_basis_tables = self._ml["build_core_basis_tables"]
        select_locked_core_seed_genome = self._ml["select_locked_core_seed_genome"]
        TrainingInit = self._ml["TrainingInit"]

        benchmark, bundle, truth_payload = build_known_relation_bundle(
            benchmark_key=str(plan["benchmark_key"]),
            n_total=int(plan["n_total"]),
            train_ratio=float(plan["train_ratio"]),
            noise_std=float(plan["noise_std"]),
            seed=int(plan["dataset_seed"]),
        )
        plan = self._apply_orchestrator_hints(plan=plan, bundle_metadata=dict(bundle.metadata or {}))
        search_hints = dict(bundle.metadata.get("search_hints", {}) or {})
        gate_feature_names = tuple(str(value) for value in tuple(search_hints.get("gate_feature_names", ()) or ()))
        enable_piecewise_basis = bool(search_hints.get("enable_piecewise_basis"))

        unlocked_runs_per_cycle = max(1, int(plan["unlocked_runs_per_cycle"]))
        locked_runs_per_cycle = max(0, int(plan["locked_runs_per_cycle"]))
        consensus_cycles = max(1, int(plan["consensus_cycles"]))
        support_count_threshold = (
            None if int(plan["core_min_support_count"]) <= 0 else int(plan["core_min_support_count"])
        )
        lane_specs = self._normalize_lane_specs(plan=plan)
        lane_summary = self._lane_summary(lane_specs)
        effective_unlocked_runs_per_cycle = (
            sum(int(spec.get("repeat_count", 1) or 1) for spec in lane_specs)
            if lane_specs
            else int(unlocked_runs_per_cycle)
        )
        effective_locked_runs_per_cycle = (
            sum(int(spec.get("locked_repeat_count", 0) or 0) for spec in lane_specs)
            if lane_specs
            else int(locked_runs_per_cycle)
        )
        plan = {
            **dict(plan),
            "lane_specs": [dict(spec) for spec in lane_specs],
            "multi_lane_enabled": bool(lane_summary.get("multi_lane_enabled")),
            "lane_count": int(lane_summary.get("lane_count", 0)),
            "unlocked_runs_per_cycle_effective": int(effective_unlocked_runs_per_cycle),
            "locked_runs_per_cycle_effective": int(effective_locked_runs_per_cycle),
        }
        signature = self._stable_signature(request, plan)
        use_cache = bool(self.cfg.cache_results) and not bool(plan.get("force_recompute"))
        if use_cache:
            with self._cache_lock:
                cached = self._cache.get(signature)
            if cached is not None:
                return dict(cached)
        base_output_root = Path(str(plan["output_root"])).expanduser().resolve()
        candidate_root = base_output_root / str(plan["benchmark_key"]) / signature
        candidate_root.mkdir(parents=True, exist_ok=True)
        db_path = str(plan["db_path"])

        seed_offset = int(signature[:6], 16) % 100000
        vanilla_runs: list[dict[str, Any]] = []
        locked_runs: list[dict[str, Any]] = []
        cycle_reports: list[dict[str, Any]] = []
        stage_reports: list[dict[str, Any]] = []
        core_basis_evolution: list[dict[str, Any]] = []

        for cycle_index in range(consensus_cycles):
            cycle_key = f"cycle_{cycle_index:02d}"
            cycle_root = candidate_root / "cycles" / cycle_key
            cycle_root.mkdir(parents=True, exist_ok=True)

            cycle_unlocked_runs: list[dict[str, Any]] = []
            if lane_specs:
                for lane_spec in lane_specs:
                    lane_plan = self._plan_with_lane_overrides(plan=plan, lane_spec=lane_spec)
                    lane_payload = {
                        **dict(lane_spec),
                        "protocol": str(plan.get("multi_lane_protocol") or ""),
                    }
                    repeat_count = max(1, int(lane_spec.get("repeat_count", 1) or 1))
                    for run_offset in range(repeat_count):
                        global_run_index = len(vanilla_runs)
                        search_seed = (
                            int(plan["search_seed_base"])
                            + int(seed_offset)
                            + (cycle_index * 1000)
                            + (int(lane_spec.get("lane_index", 0)) * 100)
                            + int(run_offset)
                        )
                        lane_id = str(lane_spec.get("lane_id") or f"lane_{int(lane_spec.get('lane_index', 0)):02d}")
                        run_name = (
                            f"{plan['namespace']}__{plan['benchmark_key']}__{cycle_key}__{lane_id}__orthogonal__{signature}__{run_offset:02d}"
                        )
                        training_metadata = self._lane_context_payload(
                            plan=plan,
                            lane_spec=lane_spec,
                            cycle_index=cycle_index,
                            cycle_key=str(cycle_key),
                            stage_key="unlocked_batch",
                            stage_level="L3",
                        )
                        run_summary = dict(
                            self._run_flow_once(
                                bundle=bundle,
                                trainer_params=self._orthogonal_params(
                                    plan=lane_plan,
                                    gate_feature_names=gate_feature_names,
                                    enable_piecewise_basis=enable_piecewise_basis,
                                    search_seed=search_seed,
                                    lock_seed_basis=False,
                                    artifact_id=(
                                        f"{plan['benchmark_key']}_{signature}_{cycle_key}_{lane_id}_orthogonal_{run_offset:02d}"
                                    ),
                                ),
                                training_init=TrainingInit(mode="fresh", metadata=training_metadata),
                                run_name=run_name,
                                output_dir=cycle_root / "orthogonal_runs" / lane_id / f"run_{run_offset:02d}",
                                db_path=db_path,
                                namespace=str(plan["namespace"]),
                                tag=(
                                    f"{plan['tag_prefix']}:{plan['benchmark_key']}:{signature}:{cycle_key}:{lane_id}:orthogonal:{run_offset:02d}"
                                ),
                                run_index=global_run_index,
                                search_seed=search_seed,
                                phase="orthogonal",
                                lane_payload=lane_payload,
                            )
                        )
                        run_summary["cycle_index"] = int(cycle_index)
                        run_summary["cycle_key"] = str(cycle_key)
                        run_summary["stage_key"] = "unlocked_batch"
                        run_summary["stage_level"] = "L3"
                        run_summary["runtime_surface_summary_path"] = self._persist_inner_run_surface(
                            db_path=db_path,
                            plan=plan,
                            signature=signature,
                            run_summary=run_summary,
                        )
                        cycle_unlocked_runs.append(run_summary)
                        vanilla_runs.append(run_summary)
            else:
                for run_offset in range(unlocked_runs_per_cycle):
                    global_run_index = len(vanilla_runs)
                    search_seed = (
                        int(plan["search_seed_base"])
                        + int(seed_offset)
                        + (cycle_index * 1000)
                        + int(run_offset)
                    )
                    run_name = (
                        f"{plan['namespace']}__{plan['benchmark_key']}__{cycle_key}__orthogonal__{signature}__{run_offset:02d}"
                    )
                    run_summary = dict(
                        self._run_flow_once(
                            bundle=bundle,
                            trainer_params=self._orthogonal_params(
                                plan=plan,
                                gate_feature_names=gate_feature_names,
                                enable_piecewise_basis=enable_piecewise_basis,
                                search_seed=search_seed,
                                lock_seed_basis=False,
                                artifact_id=(
                                    f"{plan['benchmark_key']}_{signature}_{cycle_key}_orthogonal_{run_offset:02d}"
                                ),
                            ),
                            training_init=TrainingInit(mode="fresh"),
                            run_name=run_name,
                            output_dir=cycle_root / "orthogonal_runs" / f"run_{run_offset:02d}",
                            db_path=db_path,
                            namespace=str(plan["namespace"]),
                            tag=(
                                f"{plan['tag_prefix']}:{plan['benchmark_key']}:{signature}:{cycle_key}:orthogonal:{run_offset:02d}"
                            ),
                            run_index=global_run_index,
                            search_seed=search_seed,
                            phase="orthogonal",
                        )
                    )
                    run_summary["cycle_index"] = int(cycle_index)
                    run_summary["cycle_key"] = str(cycle_key)
                    run_summary["stage_key"] = "unlocked_batch"
                    run_summary["stage_level"] = "L3"
                    run_summary["runtime_surface_summary_path"] = self._persist_inner_run_surface(
                        db_path=db_path,
                        plan=plan,
                        signature=signature,
                        run_summary=run_summary,
                    )
                    cycle_unlocked_runs.append(run_summary)
                    vanilla_runs.append(run_summary)

            unlocked_best_run = _best_run(cycle_unlocked_runs) or {}
            unlocked_runs_path = cycle_root / "unlocked_runs.json"
            _write_json(unlocked_runs_path, {"runs": list(cycle_unlocked_runs)})
            unlocked_stage_report = MlblackConsensusStageReport(
                level="L3",
                cycle_index=int(cycle_index),
                cycle_key=str(cycle_key),
                stage_key="unlocked_batch",
                stage_label="Unlocked batch",
                status="completed",
                run_count=int(len(cycle_unlocked_runs)),
                best_run_id=str(unlocked_best_run.get("run_id") or "") or None,
                best_phase=str(unlocked_best_run.get("phase") or "") or None,
                primary_metric_name="test_rmse",
                primary_metric_value=None
                if not math.isfinite(_metric_float(unlocked_best_run.get("test_rmse"), default=float("nan")))
                else float(_metric_float(unlocked_best_run.get("test_rmse"), default=float("nan"))),
                metrics={
                    "mean_test_rmse": _mean_metric(cycle_unlocked_runs, "test_rmse"),
                    "mean_exact_term_recovery_score": _mean_metric(
                        cycle_unlocked_runs,
                        "exact_term_recovery_score",
                    ),
                    "lane_count": int(lane_summary.get("lane_count", 0)),
                },
                metadata={
                    "stage_protocol": (
                        "heterogeneous_multi_lane_unlocked_batch"
                        if bool(lane_summary.get("multi_lane_enabled"))
                        else "dynamic_outer_search"
                    ),
                    "signature": signature,
                    "multi_lane_protocol": plan.get("multi_lane_protocol"),
                },
                artifact_paths={
                    "unlocked_runs_json": {
                        "path": str(unlocked_runs_path),
                        "format": "json",
                        "title": "Unlocked runs",
                    }
                },
            ).to_dict()
            unlocked_stage_path = cycle_root / "unlocked_stage.json"
            _write_json(unlocked_stage_path, unlocked_stage_report)
            unlocked_stage_report["artifact_paths"]["unlocked_stage_json"] = {
                "path": str(unlocked_stage_path),
                "format": "json",
                "title": "Unlocked stage report",
            }
            stage_reports.append(unlocked_stage_report)
            self._persist_stage_surface(
                db_path=db_path,
                plan=plan,
                signature=signature,
                cycle_index=cycle_index,
                stage_report=unlocked_stage_report,
                payload={
                    "stage_report": unlocked_stage_report,
                    "lane_summary": lane_summary,
                    "runs": list(cycle_unlocked_runs),
                    "best_run": unlocked_best_run,
                },
                artifacts=unlocked_stage_report["artifact_paths"],
                primary_metric_name="test_rmse",
                primary_metric_value=unlocked_stage_report.get("primary_metric_value"),
                output_dir=str(cycle_root),
            )

            cycle_core_tables = build_core_basis_tables(
                runs=cycle_unlocked_runs,
                min_support_count=support_count_threshold,
                min_support_rate=float(plan["core_min_support_rate"]),
                run_weight_field=str(plan.get("core_run_weight_field") or ""),
            )
            cycle_core_selection = select_locked_core_seed_genome(
                runs=cycle_unlocked_runs,
                equivalence_mode=str(plan["core_equivalence_mode"]),
                min_support_count=support_count_threshold,
                min_support_rate=float(plan["core_min_support_rate"]),
                max_terms=int(plan["core_max_terms"]),
                min_seed_terms=int(plan.get("core_min_seed_terms", 0) or 0),
                backfill_mode=str(plan.get("core_backfill_mode") or "none"),
                run_weight_field=str(plan.get("core_run_weight_field") or ""),
            )
            cycle_core_selection_path = cycle_root / "locked_core_selection.json"
            _write_json(cycle_core_selection_path, _mapping(cycle_core_selection))
            cycle_core_table_artifacts: dict[str, Any] = {
                "locked_core_selection_json": {
                    "path": str(cycle_core_selection_path),
                    "format": "json",
                    "title": "Locked core selection",
                }
            }
            for mode, rows in dict(cycle_core_tables).items():
                table_path = cycle_root / f"core_basis_table.{mode}.json"
                _write_json(table_path, {"rows": list(rows)})
                cycle_core_table_artifacts[f"core_basis_table_{mode}_json"] = {
                    "path": str(table_path),
                    "format": "json",
                    "title": f"Core basis table ({mode})",
                }
            cycle_evolution_rows = self._core_basis_evolution_rows(
                cycle_index=cycle_index,
                cycle_key=str(cycle_key),
                core_tables=cycle_core_tables,
                core_selection=cycle_core_selection,
            )
            core_basis_evolution.extend(cycle_evolution_rows)
            cycle_selected_core_rows = [
                dict(row)
                for row in tuple(cycle_core_selection.get("selected_core_rows", ()) or ())
                if isinstance(row, Mapping)
            ]
            cycle_cross_lane_scores = [
                float(row.get("cross_lane_stability"))
                for row in cycle_selected_core_rows
                if isinstance(row.get("cross_lane_stability"), (int, float))
            ]

            consensus_stage_report = MlblackConsensusStageReport(
                level="L3",
                cycle_index=int(cycle_index),
                cycle_key=str(cycle_key),
                stage_key="consensus",
                stage_label="Consensus selection",
                status="completed",
                run_count=int(len(cycle_unlocked_runs)),
                best_run_id=None,
                best_phase="consensus",
                primary_metric_name="core_basis_count",
                primary_metric_value=float(
                    len(tuple(cycle_core_selection.get("selected_core_rows", ()) or ()))
                ),
                metrics={
                    "locked_seed_terms": int(len(tuple(cycle_core_selection.get("seed_genome", ()) or ()))),
                    "selected_rows": int(len(tuple(cycle_core_selection.get("selected_core_rows", ()) or ()))),
                    "core_equivalence_mode": str(plan["core_equivalence_mode"]),
                    "selection_backfill_mode": str(plan.get("core_backfill_mode") or "none"),
                    "selection_run_weight_field": str(plan.get("core_run_weight_field") or ""),
                    "selected_backfill_rows": int(
                        sum(
                            1
                            for row in cycle_selected_core_rows
                            if str(dict(row).get("selection_source") or "") == "weighted_backfill"
                        )
                    ),
                    "lane_count": int(lane_summary.get("lane_count", 0)),
                    "cross_lane_stability_max": None
                    if not cycle_cross_lane_scores
                    else float(max(cycle_cross_lane_scores)),
                },
                metadata={
                    "stage_protocol": (
                        "heterogeneous_multi_lane_consensus_selection"
                        if bool(lane_summary.get("multi_lane_enabled"))
                        else "consensus_selection"
                    ),
                    "signature": signature,
                    "multi_lane_protocol": plan.get("multi_lane_protocol"),
                },
                artifact_paths=dict(cycle_core_table_artifacts),
            ).to_dict()
            consensus_stage_path = cycle_root / "consensus_stage.json"
            _write_json(consensus_stage_path, consensus_stage_report)
            consensus_stage_report["artifact_paths"]["consensus_stage_json"] = {
                "path": str(consensus_stage_path),
                "format": "json",
                "title": "Consensus stage report",
            }
            stage_reports.append(consensus_stage_report)
            self._persist_stage_surface(
                db_path=db_path,
                plan=plan,
                signature=signature,
                cycle_index=cycle_index,
                stage_report=consensus_stage_report,
                payload={
                    "stage_report": consensus_stage_report,
                    "lane_summary": lane_summary,
                    "heterogeneous_multi_lane_protocol": plan.get("multi_lane_protocol"),
                    "cross_lane_stability": None
                    if not cycle_cross_lane_scores
                    else float(max(cycle_cross_lane_scores)),
                    "core_selection": _mapping(cycle_core_selection),
                    "core_tables": _jsonable(cycle_core_tables),
                    "core_basis_evolution": list(cycle_evolution_rows),
                },
                artifacts=consensus_stage_report["artifact_paths"],
                primary_metric_name="core_basis_count",
                primary_metric_value=consensus_stage_report.get("primary_metric_value"),
                output_dir=str(cycle_root),
            )

            cycle_locked_runs: list[dict[str, Any]] = []
            cycle_seed_genome = tuple(cycle_core_selection.get("seed_genome", ()) or ())
            if cycle_seed_genome and effective_locked_runs_per_cycle > 0:
                unlocked_signature_source = _best_run(cycle_unlocked_runs) or cycle_unlocked_runs[0]
                parent_state = self._build_consensus_seed_state(
                    seed_genome=cycle_seed_genome,
                    selected_core_rows=tuple(cycle_core_selection.get("selected_core_rows", ()) or ()),
                    feature_names=bundle.train.feature_names,
                    target_names=bundle.train.target_names,
                    equivalence_mode=str(plan["core_equivalence_mode"]),
                    signature_fields=_mapping(unlocked_signature_source.get("training_signature")),
                )
                if lane_specs:
                    for lane_spec in lane_specs:
                        repeat_count = max(0, int(lane_spec.get("locked_repeat_count", 0) or 0))
                        if repeat_count <= 0:
                            continue
                        lane_plan = self._plan_with_lane_overrides(plan=plan, lane_spec=lane_spec)
                        lane_payload = {
                            **dict(lane_spec),
                            "protocol": str(plan.get("multi_lane_protocol") or ""),
                        }
                        lane_id = str(lane_spec.get("lane_id") or f"lane_{int(lane_spec.get('lane_index', 0)):02d}")
                        for run_offset in range(repeat_count):
                            global_locked_index = len(locked_runs)
                            search_seed = (
                                int(plan["locked_search_seed_base"])
                                + int(seed_offset)
                                + (cycle_index * 1000)
                                + (int(lane_spec.get("lane_index", 0)) * 100)
                                + int(run_offset)
                            )
                            run_name = (
                                f"{plan['namespace']}__{plan['benchmark_key']}__{cycle_key}__{lane_id}__locked__{signature}__{run_offset:02d}"
                            )
                            training_metadata = {
                                **self._lane_context_payload(
                                    plan=plan,
                                    lane_spec=lane_spec,
                                    cycle_index=cycle_index,
                                    cycle_key=str(cycle_key),
                                    stage_key="locked_core_refinement",
                                    stage_level="L3",
                                ),
                                "consensus_equivalence_mode": str(plan["core_equivalence_mode"]),
                                "locked_core_terms": int(len(cycle_seed_genome)),
                                "cycle_index": int(cycle_index),
                            }
                            run_summary = dict(
                                self._run_flow_once(
                                    bundle=bundle,
                                    trainer_params=self._orthogonal_params(
                                        plan=lane_plan,
                                        gate_feature_names=gate_feature_names,
                                        enable_piecewise_basis=enable_piecewise_basis,
                                        search_seed=search_seed,
                                        lock_seed_basis=True,
                                        artifact_id=(
                                            f"{plan['benchmark_key']}_{signature}_{cycle_key}_{lane_id}_locked_{run_offset:02d}"
                                        ),
                                    ),
                                    training_init=TrainingInit(
                                        mode="warm_start",
                                        parent_state=parent_state,
                                        metadata=training_metadata,
                                    ),
                                    run_name=run_name,
                                    output_dir=cycle_root / "locked_core_runs" / lane_id / f"run_{run_offset:02d}",
                                    db_path=db_path,
                                    namespace=str(plan["namespace"]),
                                    tag=(
                                        f"{plan['tag_prefix']}:{plan['benchmark_key']}:{signature}:{cycle_key}:{lane_id}:locked:{run_offset:02d}"
                                    ),
                                    run_index=global_locked_index,
                                    search_seed=search_seed,
                                    phase="locked_core",
                                    lane_payload=lane_payload,
                                )
                            )
                            run_summary["cycle_index"] = int(cycle_index)
                            run_summary["cycle_key"] = str(cycle_key)
                            run_summary["stage_key"] = "locked_core_refinement"
                            run_summary["stage_level"] = "L3"
                            run_summary["runtime_surface_summary_path"] = self._persist_inner_run_surface(
                                db_path=db_path,
                                plan=plan,
                                signature=signature,
                                run_summary=run_summary,
                            )
                            cycle_locked_runs.append(run_summary)
                            locked_runs.append(run_summary)
                else:
                    for run_offset in range(locked_runs_per_cycle):
                        global_locked_index = len(locked_runs)
                        search_seed = (
                            int(plan["locked_search_seed_base"])
                            + int(seed_offset)
                            + (cycle_index * 1000)
                            + int(run_offset)
                        )
                        run_name = (
                            f"{plan['namespace']}__{plan['benchmark_key']}__{cycle_key}__locked__{signature}__{run_offset:02d}"
                        )
                        run_summary = dict(
                            self._run_flow_once(
                                bundle=bundle,
                                trainer_params=self._orthogonal_params(
                                    plan=plan,
                                    gate_feature_names=gate_feature_names,
                                    enable_piecewise_basis=enable_piecewise_basis,
                                    search_seed=search_seed,
                                    lock_seed_basis=True,
                                    artifact_id=(
                                        f"{plan['benchmark_key']}_{signature}_{cycle_key}_locked_{run_offset:02d}"
                                    ),
                                ),
                                training_init=TrainingInit(
                                    mode="warm_start",
                                    parent_state=parent_state,
                                    metadata={
                                        "consensus_equivalence_mode": str(plan["core_equivalence_mode"]),
                                        "locked_core_terms": int(len(cycle_seed_genome)),
                                        "cycle_index": int(cycle_index),
                                    },
                                ),
                                run_name=run_name,
                                output_dir=cycle_root / "locked_core_runs" / f"run_{run_offset:02d}",
                                db_path=db_path,
                                namespace=str(plan["namespace"]),
                                tag=(
                                    f"{plan['tag_prefix']}:{plan['benchmark_key']}:{signature}:{cycle_key}:locked:{run_offset:02d}"
                                ),
                                run_index=global_locked_index,
                                search_seed=search_seed,
                                phase="locked_core",
                            )
                        )
                        run_summary["cycle_index"] = int(cycle_index)
                        run_summary["cycle_key"] = str(cycle_key)
                        run_summary["stage_key"] = "locked_core_refinement"
                        run_summary["stage_level"] = "L3"
                        run_summary["runtime_surface_summary_path"] = self._persist_inner_run_surface(
                            db_path=db_path,
                            plan=plan,
                            signature=signature,
                            run_summary=run_summary,
                        )
                        cycle_locked_runs.append(run_summary)
                        locked_runs.append(run_summary)

            locked_best_run = _best_run(cycle_locked_runs) or {}
            locked_runs_path = cycle_root / "locked_runs.json"
            _write_json(locked_runs_path, {"runs": list(cycle_locked_runs)})
            locked_stage_report = MlblackConsensusStageReport(
                level="L3",
                cycle_index=int(cycle_index),
                cycle_key=str(cycle_key),
                stage_key="locked_core_refinement",
                stage_label="Locked-core refinement",
                status="completed" if cycle_locked_runs else "skipped",
                run_count=int(len(cycle_locked_runs)),
                best_run_id=str(locked_best_run.get("run_id") or "") or None,
                best_phase=str(locked_best_run.get("phase") or "") or None,
                primary_metric_name="test_rmse",
                primary_metric_value=None
                if not math.isfinite(_metric_float(locked_best_run.get("test_rmse"), default=float("nan")))
                else float(_metric_float(locked_best_run.get("test_rmse"), default=float("nan"))),
                metrics={
                    "mean_test_rmse": _mean_metric(cycle_locked_runs, "test_rmse"),
                    "mean_exact_term_recovery_score": _mean_metric(
                        cycle_locked_runs,
                        "exact_term_recovery_score",
                    ),
                    "seed_terms": int(len(cycle_seed_genome)),
                    "lane_count": int(lane_summary.get("lane_count", 0)),
                },
                metadata={
                    "stage_protocol": (
                        "heterogeneous_multi_lane_locked_core_refinement"
                        if bool(lane_summary.get("multi_lane_enabled"))
                        else "locked_core_refinement"
                    ),
                    "signature": signature,
                    "multi_lane_protocol": plan.get("multi_lane_protocol"),
                },
                artifact_paths={
                    "locked_runs_json": {
                        "path": str(locked_runs_path),
                        "format": "json",
                        "title": "Locked refinement runs",
                    }
                },
            ).to_dict()
            locked_stage_path = cycle_root / "locked_stage.json"
            _write_json(locked_stage_path, locked_stage_report)
            locked_stage_report["artifact_paths"]["locked_stage_json"] = {
                "path": str(locked_stage_path),
                "format": "json",
                "title": "Locked stage report",
            }
            stage_reports.append(locked_stage_report)
            self._persist_stage_surface(
                db_path=db_path,
                plan=plan,
                signature=signature,
                cycle_index=cycle_index,
                stage_report=locked_stage_report,
                payload={
                    "stage_report": locked_stage_report,
                    "lane_summary": lane_summary,
                    "heterogeneous_multi_lane_protocol": plan.get("multi_lane_protocol"),
                    "runs": list(cycle_locked_runs),
                    "best_run": locked_best_run,
                },
                artifacts=locked_stage_report["artifact_paths"],
                primary_metric_name="test_rmse",
                primary_metric_value=locked_stage_report.get("primary_metric_value"),
                output_dir=str(cycle_root),
            )

            cycle_comparison = self._comparison_row(
                scenario=f"{plan['benchmark_key']}:{cycle_key}",
                vanilla_runs=cycle_unlocked_runs,
                locked_runs=cycle_locked_runs,
                core_selection=cycle_core_selection,
            )
            cycle_report = MlblackConsensusCycleReport(
                cycle_index=int(cycle_index),
                cycle_key=str(cycle_key),
                unlocked_run_count=int(len(cycle_unlocked_runs)),
                locked_run_count=int(len(cycle_locked_runs)),
                core_basis_count=int(len(tuple(cycle_core_selection.get("selected_core_rows", ()) or ()))),
                locked_seed_terms=int(len(cycle_seed_genome)),
                comparison=dict(_jsonable(cycle_comparison)),
                unlocked_best_run=None if not unlocked_best_run else dict(_jsonable(unlocked_best_run)),
                locked_best_run=None if not locked_best_run else dict(_jsonable(locked_best_run)),
                core_selection=dict(_jsonable(cycle_core_selection)),
                core_tables=dict(_jsonable(cycle_core_tables)),
                stage_reports=(
                    dict(_jsonable(unlocked_stage_report)),
                    dict(_jsonable(consensus_stage_report)),
                    dict(_jsonable(locked_stage_report)),
                ),
                artifact_paths={},
            ).to_dict()
            cycle_report["lane_summary"] = _jsonable(lane_summary)
            cycle_report["heterogeneous_multi_lane_protocol"] = plan.get("multi_lane_protocol")
            cycle_report["cross_lane_stability"] = (
                None if not cycle_cross_lane_scores else float(max(cycle_cross_lane_scores))
            )
            cycle_summary_path = cycle_root / "cycle_summary.json"
            _write_json(cycle_summary_path, cycle_report)
            cycle_report["artifact_paths"] = {
                "cycle_summary_json": {
                    "path": str(cycle_summary_path),
                    "format": "json",
                    "title": "Cycle summary",
                },
                **dict(_jsonable(cycle_core_table_artifacts)),
                "unlocked_stage_json": {
                    "path": str(unlocked_stage_path),
                    "format": "json",
                    "title": "Unlocked stage report",
                },
                "consensus_stage_json": {
                    "path": str(consensus_stage_path),
                    "format": "json",
                    "title": "Consensus stage report",
                },
                "locked_stage_json": {
                    "path": str(locked_stage_path),
                    "format": "json",
                    "title": "Locked stage report",
                },
            }
            _write_json(cycle_summary_path, cycle_report)
            self._persist_cycle_surface(
                db_path=db_path,
                plan=plan,
                signature=signature,
                cycle_report=cycle_report,
                output_dir=str(cycle_root),
            )
            cycle_reports.append(cycle_report)

        global_core_tables = build_core_basis_tables(
            runs=vanilla_runs,
            min_support_count=support_count_threshold,
            min_support_rate=float(plan["core_min_support_rate"]),
            run_weight_field=str(plan.get("core_run_weight_field") or ""),
        )
        global_core_selection = select_locked_core_seed_genome(
            runs=vanilla_runs,
            equivalence_mode=str(plan["core_equivalence_mode"]),
            min_support_count=support_count_threshold,
            min_support_rate=float(plan["core_min_support_rate"]),
            max_terms=int(plan["core_max_terms"]),
            min_seed_terms=int(plan.get("core_min_seed_terms", 0) or 0),
            backfill_mode=str(plan.get("core_backfill_mode") or "none"),
            run_weight_field=str(plan.get("core_run_weight_field") or ""),
        )
        comparison = self._comparison_row(
            scenario=str(plan["benchmark_key"]),
            vanilla_runs=vanilla_runs,
            locked_runs=locked_runs,
            core_selection=global_core_selection,
        )
        global_joint_core_scores = [
            float(row.get("joint_core_score"))
            for row in tuple(global_core_selection.get("selected_core_rows", ()) or ())
            if isinstance(row, Mapping) and isinstance(row.get("joint_core_score"), (int, float))
        ]
        global_cross_lane_scores = [
            float(row.get("cross_lane_stability"))
            for row in tuple(global_core_selection.get("selected_core_rows", ()) or ())
            if isinstance(row, Mapping) and isinstance(row.get("cross_lane_stability"), (int, float))
        ]
        all_runs = tuple(vanilla_runs) + tuple(locked_runs)
        leaderboards = _build_run_leaderboards(all_runs)
        best_run = dict(leaderboards.get("best_exact") or {})
        best_rmse_run = dict(leaderboards.get("best_rmse") or {})
        best_balanced_run = dict(leaderboards.get("best_balanced") or {})
        best_cycle_index = int(best_run.get("cycle_index", 0) or 0)
        best_cycle_report = next(
            (dict(report) for report in cycle_reports if int(report.get("cycle_index", -1)) == best_cycle_index),
            {},
        )
        global_seed_genome = tuple(global_core_selection.get("seed_genome", ()) or ())
        orchestration_report = {
            "protocol": "nsgablack_orchestrated_mlblack_symbolic_consensus_v2",
            "levels": {
                "L2": {
                    "unit": "consensus_cycle",
                    "cycles": int(consensus_cycles),
                },
                "L3": {
                    "unit": "stage",
                    "stages": (
                        "unlocked_batch",
                        "consensus",
                        "locked_core_refinement",
                    ),
                },
            },
            "benchmark": {
                "key": str(benchmark.key),
                "description": str(benchmark.description),
            },
            "signature": str(signature),
            "plan": _jsonable(plan),
            "heterogeneous_multi_lane_protocol": plan.get("multi_lane_protocol"),
            "lane_summary": _jsonable(lane_summary),
            "best_cycle_index": int(best_cycle_index),
            "best_cycle_key": str(best_cycle_report.get("cycle_key") or f"cycle_{best_cycle_index:02d}"),
            "leaderboards": _jsonable(leaderboards),
            "cycle_count": int(len(cycle_reports)),
            "stage_count": int(len(stage_reports)),
            "total_unlocked_runs": int(len(vanilla_runs)),
            "total_locked_runs": int(len(locked_runs)),
            "total_inner_runs": int(len(all_runs)),
            "global_core_basis_count": int(len(tuple(global_core_selection.get("selected_core_rows", ()) or ()))),
            "global_locked_seed_terms": int(len(global_seed_genome)),
            "core_selection_strategy": _jsonable(global_core_selection.get("selection_strategy")),
            "core_basis_evolution_rows": int(len(core_basis_evolution)),
            "cross_lane_stability": None
            if not global_cross_lane_scores
            else float(max(global_cross_lane_scores)),
        }
        summary = {
            "protocol": "nsgablack_orchestrated_mlblack_symbolic_consensus_v2",
            "benchmark": {
                "key": str(benchmark.key),
                "description": str(benchmark.description),
            },
            "plan": _jsonable(plan),
            "signature": str(signature),
            "heterogeneous_multi_lane_protocol": plan.get("multi_lane_protocol"),
            "lane_summary": _jsonable(lane_summary),
            "truth": _jsonable(truth_payload),
            "comparison": _jsonable(comparison),
            "best_run": _jsonable(best_run),
            "best_rmse_run": _jsonable(best_rmse_run),
            "best_exact_run": _jsonable(best_run),
            "best_balanced_run": _jsonable(best_balanced_run),
            "leaderboards": _jsonable(leaderboards),
            "best_cycle": _jsonable(best_cycle_report),
            "orchestration_report": _jsonable(orchestration_report),
            "core_tables": _jsonable(global_core_tables),
            "core_selection": _jsonable(global_core_selection),
            "cycle_reports": _jsonable(cycle_reports),
            "stage_reports": _jsonable(stage_reports),
            "core_basis_evolution": _jsonable(core_basis_evolution),
            "vanilla_runs": _jsonable(vanilla_runs),
            "locked_runs": _jsonable(locked_runs),
        }
        summary_path = candidate_root / "summary.json"
        orchestration_summary_path = candidate_root / "orchestration_summary.json"
        cycle_reports_path = candidate_root / "cycle_reports.json"
        stage_reports_path = candidate_root / "stage_reports.json"
        core_basis_evolution_path = candidate_root / "core_basis_evolution.json"
        core_selection_path = candidate_root / "locked_core_selection.json"
        comparison_path = candidate_root / "comparison.json"
        _write_json(summary_path, summary)
        _write_json(orchestration_summary_path, orchestration_report)
        _write_json(cycle_reports_path, {"cycles": list(cycle_reports)})
        _write_json(stage_reports_path, {"stages": list(stage_reports)})
        _write_json(core_basis_evolution_path, {"rows": list(core_basis_evolution)})
        _write_json(core_selection_path, _mapping(global_core_selection))
        _write_json(comparison_path, _mapping(comparison))
        for mode, rows in dict(global_core_tables).items():
            _write_json(candidate_root / f"core_basis_table.{mode}.json", {"rows": list(rows)})

        exact_score = _metric_float(best_run.get("exact_term_recovery_score"), default=0.0)
        phase_score = _metric_float(best_run.get("phase_equivalent_term_recovery_score"), default=0.0)
        family_score = _metric_float(best_run.get("family_level_term_recovery_score"), default=0.0)
        best_rmse = _metric_float(best_run.get("test_rmse"), default=self.cfg.fallback_objective)
        best_outer = _metric_float(best_run.get("outer_objective_score"), default=float("nan"))
        best_inner_fit = _metric_float(best_run.get("inner_fit_score"), default=float("nan"))
        best_rmse_only_value = _metric_float(best_rmse_run.get("test_rmse"), default=self.cfg.fallback_objective)
        best_rmse_only_exact = _metric_float(best_rmse_run.get("exact_term_recovery_score"), default=0.0)
        best_rmse_only_phase = _metric_float(
            best_rmse_run.get("phase_equivalent_term_recovery_score"),
            default=0.0,
        )
        best_rmse_only_family = _metric_float(
            best_rmse_run.get("family_level_term_recovery_score"),
            default=0.0,
        )
        best_balanced_score = _metric_float(best_balanced_run.get("balanced_score"), default=0.0)
        best_balanced_rmse = _metric_float(best_balanced_run.get("test_rmse"), default=self.cfg.fallback_objective)
        best_balanced_exact = _metric_float(best_balanced_run.get("exact_term_recovery_score"), default=0.0)
        best_balanced_phase = _metric_float(
            best_balanced_run.get("phase_equivalent_term_recovery_score"),
            default=0.0,
        )
        best_balanced_family = _metric_float(
            best_balanced_run.get("family_level_term_recovery_score"),
            default=0.0,
        )
        best_cycle_core_basis_count = int(
            best_cycle_report.get(
                "core_basis_count",
                len(tuple(global_core_selection.get("selected_core_rows", ()) or ())),
            )
            or 0
        )
        best_cycle_locked_seed_terms = int(
            best_cycle_report.get("locked_seed_terms", len(global_seed_genome)) or 0
        )
        result = {
            "status": "ok",
            "objective": float(best_rmse),
            "violation": 0.0,
            "metrics": {
                "mlblack.backend": "symbolic_consensus",
                "mlblack.benchmark_key": str(plan["benchmark_key"]),
                "mlblack.consensus_cycles": int(consensus_cycles),
                "mlblack.unlocked_runs_per_cycle": int(unlocked_runs_per_cycle),
                "mlblack.locked_runs_per_cycle": int(locked_runs_per_cycle),
                "mlblack.unlocked_runs_per_cycle_effective": int(effective_unlocked_runs_per_cycle),
                "mlblack.locked_runs_per_cycle_effective": int(effective_locked_runs_per_cycle),
                "mlblack.multi_lane_enabled": int(bool(lane_summary.get("multi_lane_enabled"))),
                "mlblack.lane_count": int(lane_summary.get("lane_count", 0)),
                "mlblack.vanilla_runs": int(len(vanilla_runs)),
                "mlblack.locked_runs": int(len(locked_runs)),
                "mlblack.total_inner_runs": int(len(all_runs)),
                "mlblack.best_cycle_index": int(best_cycle_index),
                "mlblack.best_phase": str(best_run.get("phase") or ""),
                "mlblack.best_test_rmse": float(best_rmse),
                "mlblack.best_exact_term_recovery_score": float(exact_score),
                "mlblack.best_phase_equivalent_term_recovery_score": float(phase_score),
                "mlblack.best_family_level_term_recovery_score": float(family_score),
                "mlblack.best_rmse_test_rmse": float(best_rmse_only_value),
                "mlblack.best_rmse_exact_term_recovery_score": float(best_rmse_only_exact),
                "mlblack.best_balanced_score": float(best_balanced_score),
                "mlblack.best_balanced_test_rmse": float(best_balanced_rmse),
                "mlblack.best_balanced_exact_term_recovery_score": float(best_balanced_exact),
            },
            "benchmark_key": str(plan["benchmark_key"]),
            "signature": str(signature),
            "best_phase": str(best_run.get("phase") or ""),
            "best_cycle_index": int(best_cycle_index),
            "best_cycle_key": str(best_cycle_report.get("cycle_key") or f"cycle_{best_cycle_index:02d}"),
            "best_run_id": str(best_run.get("run_id") or ""),
            "best_artifact_id": str(best_run.get("artifact_id") or ""),
            "best_expression": str(best_run.get("final_expression") or ""),
            "best_test_rmse": float(best_rmse),
            "best_test_r2": _metric_float(best_run.get("test_r2"), default=float("nan")),
            "best_exact_term_recovery_score": float(exact_score),
            "best_phase_equivalent_term_recovery_score": float(phase_score),
            "best_family_level_term_recovery_score": float(family_score),
            "best_outer_objective_score": None if not math.isfinite(best_outer) else float(best_outer),
            "best_inner_fit_score": None if not math.isfinite(best_inner_fit) else float(best_inner_fit),
            "search_driver": best_run.get("search_driver"),
            "screening_protocol": best_run.get("screening_protocol"),
            "outer_search_protocol": best_run.get("outer_search_protocol"),
            "heterogeneous_multi_lane_protocol": plan.get("multi_lane_protocol"),
            "lane_summary": _jsonable(lane_summary),
            "lane_id": best_run.get("lane_id"),
            "lane_family": best_run.get("lane_family"),
            "challenger_objective_protocol": best_run.get("challenger_objective_protocol"),
            "pool_expansion_bias_protocol": best_run.get("pool_expansion_bias_protocol"),
            "structure_head": best_run.get("structure_head"),
            "search_input_space": best_run.get("search_input_space"),
            "pool_expansion_unit": best_run.get("pool_expansion_unit"),
            "gradient_guidance_mode": best_run.get("gradient_guidance_mode"),
            "basis_binding_mode": best_run.get("basis_binding_mode"),
            "escape_policy": best_run.get("escape_policy"),
            "basis_context": _jsonable(best_run.get("basis_context")),
            "basis_object_gradient_pool": _jsonable(best_run.get("basis_object_gradient_pool")),
            "heterogeneous_multi_lane_context": _jsonable(
                best_run.get("heterogeneous_multi_lane_context")
            ),
            "heterogeneous_lane_consensus": _jsonable(
                best_run.get("heterogeneous_lane_consensus")
            ),
            "consensus_prior_row_count": best_run.get("consensus_prior_row_count"),
            "joint_core_score": (
                None if not global_joint_core_scores else float(max(global_joint_core_scores))
            ),
            "cross_lane_stability": (
                None if not global_cross_lane_scores else float(max(global_cross_lane_scores))
            ),
            "best_rmse_run_id": str(best_rmse_run.get("run_id") or ""),
            "best_rmse_artifact_id": str(best_rmse_run.get("artifact_id") or ""),
            "best_rmse_phase": str(best_rmse_run.get("phase") or ""),
            "best_rmse_cycle_index": int(best_rmse_run.get("cycle_index", 0) or 0),
            "best_rmse_cycle_key": str(best_rmse_run.get("cycle_key") or ""),
            "best_rmse_expression": str(best_rmse_run.get("final_expression") or ""),
            "best_rmse_test_rmse": float(best_rmse_only_value),
            "best_rmse_test_r2": _metric_float(best_rmse_run.get("test_r2"), default=float("nan")),
            "best_rmse_exact_term_recovery_score": float(best_rmse_only_exact),
            "best_rmse_phase_equivalent_term_recovery_score": float(best_rmse_only_phase),
            "best_rmse_family_level_term_recovery_score": float(best_rmse_only_family),
            "best_exact_run_id": str(best_run.get("run_id") or ""),
            "best_exact_artifact_id": str(best_run.get("artifact_id") or ""),
            "best_exact_phase": str(best_run.get("phase") or ""),
            "best_exact_cycle_index": int(best_run.get("cycle_index", 0) or 0),
            "best_exact_cycle_key": str(best_run.get("cycle_key") or ""),
            "best_exact_expression": str(best_run.get("final_expression") or ""),
            "best_exact_test_rmse": float(best_rmse),
            "best_exact_test_r2": _metric_float(best_run.get("test_r2"), default=float("nan")),
            "best_exact_term_recovery_score": float(exact_score),
            "best_exact_phase_equivalent_term_recovery_score": float(phase_score),
            "best_exact_family_level_term_recovery_score": float(family_score),
            "best_balanced_run_id": str(best_balanced_run.get("run_id") or ""),
            "best_balanced_artifact_id": str(best_balanced_run.get("artifact_id") or ""),
            "best_balanced_phase": str(best_balanced_run.get("phase") or ""),
            "best_balanced_cycle_index": int(best_balanced_run.get("cycle_index", 0) or 0),
            "best_balanced_cycle_key": str(best_balanced_run.get("cycle_key") or ""),
            "best_balanced_expression": str(best_balanced_run.get("final_expression") or ""),
            "best_balanced_score": float(best_balanced_score),
            "best_balanced_test_rmse": float(best_balanced_rmse),
            "best_balanced_test_r2": _metric_float(best_balanced_run.get("test_r2"), default=float("nan")),
            "best_balanced_exact_term_recovery_score": float(best_balanced_exact),
            "best_balanced_phase_equivalent_term_recovery_score": float(best_balanced_phase),
            "best_balanced_family_level_term_recovery_score": float(best_balanced_family),
            "leaderboards": _jsonable(leaderboards),
            "core_basis_count": int(best_cycle_core_basis_count),
            "locked_seed_terms": int(best_cycle_locked_seed_terms),
            "global_core_basis_count": int(len(tuple(global_core_selection.get("selected_core_rows", ()) or ()))),
            "global_locked_seed_terms": int(len(global_seed_genome)),
            "core_selection_strategy": _jsonable(global_core_selection.get("selection_strategy")),
            "core_equivalence_mode": str(plan["core_equivalence_mode"]),
            "consensus_cycles": int(consensus_cycles),
            "unlocked_runs_per_cycle": int(unlocked_runs_per_cycle),
            "unlocked_runs_per_cycle_effective": int(effective_unlocked_runs_per_cycle),
            "locked_runs_per_cycle": int(locked_runs_per_cycle),
            "locked_runs_per_cycle_effective": int(effective_locked_runs_per_cycle),
            "lane_count": int(lane_summary.get("lane_count", 0)),
            "total_cycle_rows": int(len(cycle_reports)),
            "total_stage_rows": int(len(stage_reports)),
            "total_inner_runs": int(len(all_runs)),
            "summary_path": str(summary_path),
            "orchestration_summary_path": str(orchestration_summary_path),
            "cycle_reports_path": str(cycle_reports_path),
            "stage_reports_path": str(stage_reports_path),
            "core_basis_evolution_path": str(core_basis_evolution_path),
            "comparison_path": str(comparison_path),
            "core_selection_path": str(core_selection_path),
            "artifacts": {
                "orchestration_summary_json": {
                    "path": str(orchestration_summary_path),
                    "format": "json",
                    "title": "Orchestration summary",
                },
                "cycle_reports_json": {
                    "path": str(cycle_reports_path),
                    "format": "json",
                    "title": "Cycle reports",
                },
                "stage_reports_json": {
                    "path": str(stage_reports_path),
                    "format": "json",
                    "title": "Stage reports",
                },
                "core_basis_evolution_json": {
                    "path": str(core_basis_evolution_path),
                    "format": "json",
                    "title": "Core basis evolution",
                },
                "comparison_json": {
                    "path": str(comparison_path),
                    "format": "json",
                    "title": "Comparison summary",
                },
                "locked_core_selection_json": {
                    "path": str(core_selection_path),
                    "format": "json",
                    "title": "Global locked core selection",
                },
                "summary_json": {
                    "path": str(summary_path),
                    "format": "json",
                    "title": "Full consensus summary",
                },
            },
            "orchestration_report": _jsonable(orchestration_report),
            "cycle_reports": _jsonable(cycle_reports),
            "stage_reports": _jsonable(stage_reports),
            "core_basis_evolution": _jsonable(core_basis_evolution),
            "payload": {
                "plan": _jsonable(plan),
                "comparison": _jsonable(comparison),
                "best_run": _jsonable(best_run),
                "best_rmse_run": _jsonable(best_rmse_run),
                "best_exact_run": _jsonable(best_run),
                "best_balanced_run": _jsonable(best_balanced_run),
                "leaderboards": _jsonable(leaderboards),
                "best_cycle": _jsonable(best_cycle_report),
                "orchestration_report": _jsonable(orchestration_report),
                "core_tables": _jsonable(global_core_tables),
                "core_selection": _jsonable(global_core_selection),
                "truth": _jsonable(truth_payload),
                "cycle_reports": _jsonable(cycle_reports),
                "stage_reports": _jsonable(stage_reports),
                "core_basis_evolution": _jsonable(core_basis_evolution),
                "vanilla_runs": _jsonable(vanilla_runs),
                "locked_runs": _jsonable(locked_runs),
            },
        }
        if use_cache:
            with self._cache_lock:
                self._cache[signature] = dict(result)
        return result
