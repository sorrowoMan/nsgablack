"""
Canonical context keys used across adapters/plugins/biases.

The goal is consistency: different modules can interoperate by reading/writing
the same keys. This file is intentionally small and stable.
"""

from __future__ import annotations

from typing import Dict

# Generic
KEY_TEMPERATURE = "temperature"
KEY_GENERATION = "generation"
KEY_STEP = "step"
KEY_PROBLEM = "problem"
KEY_POPULATION = "population"
KEY_OBJECTIVES = "objectives"
KEY_INDIVIDUAL = "individual"
KEY_BEST_X = "best_x"
KEY_BEST_OBJECTIVE = "best_objective"
KEY_HISTORY = "history"
KEY_METADATA = "metadata"
KEY_METADATA_LAYERS = "metadata.layers"
KEY_PROBLEM_DATA = "problem_data"
KEY_CONSTRAINT_VIOLATION = "constraint_violation"
KEY_CONSTRAINT_VIOLATIONS = "constraint_violations"
KEY_CONSTRAINTS = "constraints"
KEY_INDIVIDUAL_ID = "individual_id"
KEY_BOUNDS = "bounds"
KEY_CAPACITY = "capacity"
KEY_SHAPE = "shape"
KEY_NUM_NODES = "num_nodes"
KEY_DISTANCE_MATRIX = "distance_matrix"
KEY_ROW_SUMS = "row_sums"
KEY_COL_SUMS = "col_sums"
KEY_K_NONZERO = "k_nonzero"
KEY_DENSITY = "density"
KEY_BLOCK_MIN = "block_min"
KEY_BLOCK_MAX = "block_max"

# Representation-coupling
KEY_MUTATION_SIGMA = "mutation_sigma"

# Variable Neighborhood Search (VNS)
KEY_VNS_K = "vns_k"

# Multi-strategy cooperation
KEY_STRATEGY = "strategy"
KEY_STRATEGY_ID = "strategy_id"
KEY_SHARED = "shared"

# Role orchestration (multi-role / multi-strategy)
KEY_ROLE = "role"
KEY_ROLE_INDEX = "role_index"
KEY_ROLE_ADAPTER = "role_adapter"

# Optional "task/report" schema for controller-driven cooperation.
KEY_TASK = "task"
KEY_REPORT = "report"
KEY_ROLE_REPORTS = "role_reports"
KEY_CANDIDATE_ROLES = "candidate_roles"
KEY_CANDIDATE_UNITS = "candidate_units"
KEY_UNIT_TASKS = "unit_tasks"
KEY_ADAPTER_NAME = "adapter_name"
KEY_ADAPTER_CURRENT_SCORE = "adapter_current_score"
KEY_ADAPTER_BEST_SCORE = "adapter_best_score"

# Dynamic runtime switching
KEY_DYNAMIC = "dynamic"
KEY_PHASE_ID = "phase_id"
KEY_COMPANION_PHASE_INDEX = "companion_phase_index"
KEY_COMPANION_TRIGGER_REASON = "companion_trigger_reason"
KEY_COMPANION_NEXT_ELIGIBLE_GENERATION = "companion_next_eligible_generation"
KEY_COMPANION_PHASE_COUNT_USED = "companion_phase_count_used"

# Advanced cooperation: phase + region + seeding
KEY_PHASE = "phase"
KEY_REGION_ID = "region_id"
KEY_REGION_BOUNDS = "region_bounds"
KEY_SEEDS = "seeds"
KEY_RUNNING = "running"

# Async event-driven orchestration
KEY_EVENT_QUEUE = "event_queue"
KEY_EVENT_INFLIGHT = "event_inflight"
KEY_EVENT_ARCHIVE = "event_archive"
KEY_EVENT_HISTORY = "event_history"
KEY_EVENT_SHARED = "event_shared"

# Single trajectory adaptive search
KEY_SINGLE_TRAJ_STATE = "single_traj_state"
KEY_SINGLE_TRAJ_SIGMA = "single_traj_sigma"

# MOEA/D decomposition metadata
KEY_MOEAD_SUBPROBLEM = "moead_subproblem"
KEY_MOEAD_WEIGHT = "moead_weight"
KEY_MOEAD_NEIGHBOR_MODE = "moead_neighbor_mode"
KEY_MO_WEIGHTS = "mo_weights"

# Model-assisted search
KEY_MAS_MODEL = "mas_model"
KEY_SUBSPACE_BASIS = "subspace_basis"

# Metrics namespace
KEY_METRICS = "metrics"
KEY_METRICS_MC_SAMPLES = "metrics.mc_samples"
KEY_METRICS_MC_MEAN = "metrics.mc_mean"
KEY_METRICS_MC_STD = "metrics.mc_std"
KEY_METRICS_MC_MIN = "metrics.mc_min"
KEY_METRICS_MC_MAX = "metrics.mc_max"
KEY_METRICS_SURROGATE_STD = "metrics.surrogate_std"
KEY_METRICS_IMPLICIT_RESIDUAL = "metrics.implicit_residual"
KEY_METRICS_IMPLICIT_ITERS = "metrics.implicit_iters"
KEY_METRICS_IMPLICIT_SUCCESS = "metrics.implicit_success"
KEY_METRICS_INNER_ELAPSED_MS = "metrics.inner_elapsed_ms"
KEY_METRICS_INNER_STATUS = "metrics.inner_status"
KEY_METRICS_INNER_CALLS = "metrics.inner_calls"
KEY_METRICS_SOFT_ERROR_COUNT = "metrics.soft_error_count"
KEY_METRICS_SOFT_ERROR_LAST = "metrics.soft_error_last"

# Context meta
KEY_EVALUATION_COUNT = "evaluation_count"
KEY_PARETO_SOLUTIONS = "pareto_solutions"
KEY_PARETO_OBJECTIVES = "pareto_objectives"
KEY_MUTATION_RATE = "mutation_rate"
KEY_CROSSOVER_RATE = "crossover_rate"
KEY_CONTEXT_SCHEMA = "context_schema"
KEY_CONTEXT_EVENTS = "context_events"
KEY_CONTEXT_CACHE = "context_cache"
KEY_DECISION_TRACE = "decision_trace"
KEY_CHECKPOINT_LATEST_PATH = "checkpoint.latest_path"
KEY_CHECKPOINT_LAST_LOADED_PATH = "checkpoint.last_loaded_path"
KEY_BIAS_CACHE_FINGERPRINT = "bias_cache_fingerprint"
KEY_SNAPSHOT_KEY = "snapshot_key"
KEY_SNAPSHOT_BACKEND = "snapshot_backend"
KEY_SNAPSHOT_SCHEMA = "snapshot_schema"
KEY_SNAPSHOT_META = "snapshot_meta"
KEY_POPULATION_REF = "population_ref"
KEY_OBJECTIVES_REF = "objectives_ref"
KEY_CONSTRAINT_VIOLATIONS_REF = "constraint_violations_ref"
KEY_PARETO_SOLUTIONS_REF = "pareto_solutions_ref"
KEY_PARETO_OBJECTIVES_REF = "pareto_objectives_ref"
KEY_HISTORY_REF = "history_ref"
KEY_DECISION_TRACE_REF = "decision_trace_ref"
KEY_SEQUENCE_GRAPH_REF = "sequence_graph_ref"

CANONICAL_CONTEXT_KEYS = {
    KEY_TEMPERATURE,
    KEY_GENERATION,
    KEY_STEP,
    KEY_PROBLEM,
    KEY_POPULATION,
    KEY_OBJECTIVES,
    KEY_INDIVIDUAL,
    KEY_BEST_X,
    KEY_BEST_OBJECTIVE,
    KEY_HISTORY,
    KEY_METADATA,
    KEY_METADATA_LAYERS,
    KEY_PROBLEM_DATA,
    KEY_CONSTRAINT_VIOLATION,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_CONSTRAINTS,
    KEY_INDIVIDUAL_ID,
    KEY_BOUNDS,
    KEY_CAPACITY,
    KEY_SHAPE,
    KEY_NUM_NODES,
    KEY_DISTANCE_MATRIX,
    KEY_ROW_SUMS,
    KEY_COL_SUMS,
    KEY_K_NONZERO,
    KEY_DENSITY,
    KEY_BLOCK_MIN,
    KEY_BLOCK_MAX,
    KEY_MUTATION_SIGMA,
    KEY_VNS_K,
    KEY_STRATEGY,
    KEY_STRATEGY_ID,
    KEY_SHARED,
    KEY_ROLE,
    KEY_ROLE_INDEX,
    KEY_ROLE_ADAPTER,
    KEY_TASK,
    KEY_REPORT,
    KEY_ROLE_REPORTS,
    KEY_CANDIDATE_ROLES,
    KEY_CANDIDATE_UNITS,
    KEY_UNIT_TASKS,
    KEY_ADAPTER_NAME,
    KEY_ADAPTER_CURRENT_SCORE,
    KEY_ADAPTER_BEST_SCORE,
    KEY_DYNAMIC,
    KEY_PHASE_ID,
    KEY_COMPANION_PHASE_INDEX,
    KEY_COMPANION_TRIGGER_REASON,
    KEY_COMPANION_NEXT_ELIGIBLE_GENERATION,
    KEY_COMPANION_PHASE_COUNT_USED,
    KEY_PHASE,
    KEY_REGION_ID,
    KEY_REGION_BOUNDS,
    KEY_SEEDS,
    KEY_RUNNING,
    KEY_EVENT_QUEUE,
    KEY_EVENT_INFLIGHT,
    KEY_EVENT_ARCHIVE,
    KEY_EVENT_HISTORY,
    KEY_EVENT_SHARED,
    KEY_SINGLE_TRAJ_STATE,
    KEY_SINGLE_TRAJ_SIGMA,
    KEY_MOEAD_SUBPROBLEM,
    KEY_MOEAD_WEIGHT,
    KEY_MOEAD_NEIGHBOR_MODE,
    KEY_MO_WEIGHTS,
    KEY_MAS_MODEL,
    KEY_SUBSPACE_BASIS,
    KEY_METRICS,
    KEY_METRICS_MC_SAMPLES,
    KEY_METRICS_MC_MEAN,
    KEY_METRICS_MC_STD,
    KEY_METRICS_MC_MIN,
    KEY_METRICS_MC_MAX,
    KEY_METRICS_SURROGATE_STD,
    KEY_METRICS_IMPLICIT_RESIDUAL,
    KEY_METRICS_IMPLICIT_ITERS,
    KEY_METRICS_IMPLICIT_SUCCESS,
    KEY_METRICS_INNER_ELAPSED_MS,
    KEY_METRICS_INNER_STATUS,
    KEY_METRICS_INNER_CALLS,
    KEY_METRICS_SOFT_ERROR_COUNT,
    KEY_METRICS_SOFT_ERROR_LAST,
    KEY_EVALUATION_COUNT,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_OBJECTIVES,
    KEY_MUTATION_RATE,
    KEY_CROSSOVER_RATE,
    KEY_CONTEXT_SCHEMA,
    KEY_CONTEXT_EVENTS,
    KEY_CONTEXT_CACHE,
    KEY_DECISION_TRACE,
    KEY_CHECKPOINT_LATEST_PATH,
    KEY_CHECKPOINT_LAST_LOADED_PATH,
    KEY_BIAS_CACHE_FINGERPRINT,
    KEY_SNAPSHOT_KEY,
    KEY_SNAPSHOT_BACKEND,
    KEY_SNAPSHOT_SCHEMA,
    KEY_SNAPSHOT_META,
    KEY_POPULATION_REF,
    KEY_OBJECTIVES_REF,
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_PARETO_SOLUTIONS_REF,
    KEY_PARETO_OBJECTIVES_REF,
    KEY_HISTORY_REF,
    KEY_DECISION_TRACE_REF,
    KEY_SEQUENCE_GRAPH_REF,
}

_ALIASES: Dict[str, str] = {
    "bestx": KEY_BEST_X,
    "bestobjective": KEY_BEST_OBJECTIVE,
    "best-objective": KEY_BEST_OBJECTIVE,
    "bestobj": KEY_BEST_OBJECTIVE,
    "bestf": KEY_BEST_OBJECTIVE,
    "mutationsigma": KEY_MUTATION_SIGMA,
    "mutation-sigma": KEY_MUTATION_SIGMA,
    "vnsk": KEY_VNS_K,
    "vns-k": KEY_VNS_K,
    "vns.k": KEY_VNS_K,
    "moeadsubproblem": KEY_MOEAD_SUBPROBLEM,
    "moead_weight": KEY_MOEAD_WEIGHT,
    "moead-neighbor-mode": KEY_MOEAD_NEIGHBOR_MODE,
    "singletrajstate": KEY_SINGLE_TRAJ_STATE,
    "singletrajsigma": KEY_SINGLE_TRAJ_SIGMA,
    "adaptername": KEY_ADAPTER_NAME,
    "adaptercurrentscore": KEY_ADAPTER_CURRENT_SCORE,
    "adapterbestscore": KEY_ADAPTER_BEST_SCORE,
    "eventqueue": KEY_EVENT_QUEUE,
    "eventinflight": KEY_EVENT_INFLIGHT,
    "biascachefingerprint": KEY_BIAS_CACHE_FINGERPRINT,
    "snapshotkey": KEY_SNAPSHOT_KEY,
    "snapshotbackend": KEY_SNAPSHOT_BACKEND,
    "snapshotschema": KEY_SNAPSHOT_SCHEMA,
    "snapshotmeta": KEY_SNAPSHOT_META,
    "populationref": KEY_POPULATION_REF,
    "objectivesref": KEY_OBJECTIVES_REF,
    "constraintviolationsref": KEY_CONSTRAINT_VIOLATIONS_REF,
    "paretosolutionsref": KEY_PARETO_SOLUTIONS_REF,
    "paretoobjectivesref": KEY_PARETO_OBJECTIVES_REF,
    "historyref": KEY_HISTORY_REF,
    "decisiontraceref": KEY_DECISION_TRACE_REF,
    "sequencegraphref": KEY_SEQUENCE_GRAPH_REF,
}


def normalize_context_key(key: str) -> str:
    text = str(key).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in CANONICAL_CONTEXT_KEYS:
        return lowered
    normalized = lowered.replace(" ", "").replace("_", "").replace("-", "")
    return _ALIASES.get(normalized, lowered)
