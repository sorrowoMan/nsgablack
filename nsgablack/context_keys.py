"""nsgablack context vocabulary; wire names are stable."""
from blackbase.context.context_keys import (
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
    KEY_RUNTIME_PROJECTION_AUDIT,
    KEY_STAGE_INDEX,
    KEY_STAGE_NAME,
    KEY_STAGE_TOTAL,
    KEY_STAGE_ARTIFACTS,
    KEY_STAGE_ARTIFACT_PREFIX,
    KEY_STAGE_STATUS,
    KEY_STAGE_INPUT_ARTIFACTS,
    KEY_STAGE_OUTPUT_ARTIFACTS,
    KEY_BACKEND_CAPABILITY,
    KEY_BACKEND_CONTRACT,
    KEY_BACKEND_DEVICE,
    KEY_BACKEND_DEVICE_POLICY,
    KEY_BACKEND_NAME,
    KEY_BACKEND_REQUESTED_NAME,
    KEY_BACKEND_SESSION,
    KEY_CHECKPOINT_REF,
    KEY_PIPELINE_SLOT_CONTEXT,
    KEY_RESOURCE_AUDIT,
    KEY_RESOURCE_CONTEXT,
    KEY_RESOURCE_DEVICE,
    KEY_RESOURCE_LEASE,
    KEY_RESOURCE_CONTEXT_SHORT,
    KEY_SNAPSHOT_REF,
    KEY_STAGE_AUDIT,
    KEY_STAGE_ID,
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
    KEY_METRICS_GPU_BACKEND,
    KEY_METRICS_GPU_CALLS,
    KEY_METRICS_GPU_FALLBACKS,
    KEY_EVALUATION_COUNT,
    KEY_CONTEXT_SCHEMA,
    KEY_CONTEXT_EVENTS,
    KEY_CONTEXT_CACHE,
    KEY_DECISION_TRACE,
    KEY_CHECKPOINT_LATEST_PATH,
    KEY_CHECKPOINT_LAST_LOADED_PATH,
    KEY_SNAPSHOT_KEY,
    KEY_SNAPSHOT_BACKEND,
    KEY_SNAPSHOT_SCHEMA,
    KEY_SNAPSHOT_META,
    KEY_BEST_CANDIDATE_REF,
    KEY_POPULATION_REF,
    KEY_OBJECTIVES_REF,
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_HISTORY_REF,
    KEY_DECISION_TRACE_REF,
    KEY_SEQUENCE_GRAPH_REF,
    KEY_BACKEND_WARM_START_REF,
    KEY_BACKEND_SOLUTION_POOL_REF,
    KEY_BACKEND_DIAGNOSTIC_REF,
    KEY_BACKEND_CALLBACK_REF,
    CANONICAL_CONTEXT_KEYS,
    CONTEXT_KEY_SET,
    METRIC_FALLBACKS,
    METRIC_KEYS,
    normalize_context_key,
    normalize_context_keys,
    register_context_keys,
    unknown_context_keys,
    validate_context_keys,
    register_context_namespace,
    context_key_scope,
    current_context_registry,
    ContextKeyRegistry,
)

KEY_TEMPERATURE = "temperature"
KEY_NUM_NODES = "num_nodes"
KEY_DISTANCE_MATRIX = "distance_matrix"
KEY_ROW_SUMS = "row_sums"
KEY_COL_SUMS = "col_sums"
KEY_K_NONZERO = "k_nonzero"
KEY_DENSITY = "density"
KEY_BLOCK_MIN = "block_min"
KEY_BLOCK_MAX = "block_max"
KEY_MUTATION_SIGMA = "mutation_sigma"
KEY_VNS_K = "vns_k"
KEY_STRATEGY = "strategy"
KEY_STRATEGY_ID = "strategy_id"
KEY_SHARED = "shared"
KEY_ROLE = "role"
KEY_ROLE_INDEX = "role_index"
KEY_ROLE_ADAPTER = "role_adapter"
KEY_TASK = "task"
KEY_REPORT = "report"
KEY_ROLE_REPORTS = "role_reports"
KEY_CANDIDATE_ROLES = "candidate_roles"
KEY_CANDIDATE_UNITS = "candidate_units"
KEY_UNIT_TASKS = "unit_tasks"
KEY_STRATEGY_INSTANCES = "strategy_instances"
KEY_ADAPTER_NAME = "adapter_name"
KEY_ADAPTER_CURRENT_SCORE = "adapter_current_score"
KEY_ADAPTER_BEST_SCORE = "adapter_best_score"
KEY_ADAPTER_BEST_X = "adapter_best_x"
KEY_ADAPTER_BEST_OBJECTIVES = "adapter_best_objectives"
KEY_ADAPTER_COMMIT_REPORT_REF = "adapter.commit_report_ref"
KEY_SOLUTION_POOL_REF = "solution_pool_ref"
KEY_CANDIDATE_TOKEN = "candidate_token"
KEY_SOLUTION_POOL_TIME = "solution_pool_time"
KEY_SOLUTION_INPUT_REF = "solution_input_ref"
KEY_SOLUTION_INPUT_MODE = "solution_input_mode"
KEY_DYNAMIC = "dynamic"
KEY_PHASE_ID = "phase_id"
KEY_COMPANION_PHASE_INDEX = "companion_phase_index"
KEY_COMPANION_TRIGGER_REASON = "companion_trigger_reason"
KEY_COMPANION_NEXT_ELIGIBLE_GENERATION = "companion_next_eligible_generation"
KEY_COMPANION_PHASE_COUNT_USED = "companion_phase_count_used"
KEY_PHASE = "phase"
KEY_REGION_ID = "region_id"
KEY_REGION_BOUNDS = "region_bounds"
KEY_SEEDS = "seeds"
KEY_RUNNING = "running"
KEY_EVENT_QUEUE = "event_queue"
KEY_EVENT_INFLIGHT = "event_inflight"
KEY_EVENT_ARCHIVE = "event_archive"
KEY_EVENT_HISTORY = "event_history"
KEY_EVENT_SHARED = "event_shared"
KEY_SINGLE_TRAJ_STATE = "single_traj_state"
KEY_SINGLE_TRAJ_SIGMA = "single_traj_sigma"
KEY_MOEAD_SUBPROBLEM = "moead_subproblem"
KEY_MOEAD_WEIGHT = "moead_weight"
KEY_MOEAD_NEIGHBOR_MODE = "moead_neighbor_mode"
KEY_MO_WEIGHTS = "mo_weights"
KEY_MAS_MODEL = "mas_model"
KEY_SUBSPACE_BASIS = "subspace_basis"
KEY_PARETO_SOLUTIONS = "pareto_solutions"
KEY_PARETO_OBJECTIVES = "pareto_objectives"
KEY_MUTATION_RATE = "mutation_rate"
KEY_CROSSOVER_RATE = "crossover_rate"
KEY_BIAS_CACHE_FINGERPRINT = "bias_cache_fingerprint"
KEY_PARETO_SOLUTIONS_REF = "pareto_solutions_ref"
KEY_PARETO_OBJECTIVES_REF = "pareto_objectives_ref"

KEY_METRICS_EVAL_MODEL_CALLS = "metrics.eval_model_calls"
KEY_METRICS_EVAL_MODEL_FAILURES = "metrics.eval_model_failures"

register_context_namespace("nsgablack", tuple(v for k, v in globals().copy().items() if k.startswith("KEY_")))
