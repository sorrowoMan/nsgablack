from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class MinimalEvaluationContext:
    """并行/串行共用的最小评估上下文（可序列化、可扩展）。

    设计目标：让 bias 在并行评估时只依赖最小可获得信息。

    约束：
    - 不保证包含 solver 全局状态（population/history 等）。
    - 如需全局信息，应在主线程构造完整 context，避免并行路径语义漂移。
    """

    generation: Optional[int]
    individual_id: int
    constraints: List[float]
    constraint_violation: float
    seed: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "generation": self.generation,
            "individual_id": int(self.individual_id),
            "constraints": list(self.constraints),
            "constraint_violation": float(self.constraint_violation),
        }
        if self.seed is not None:
            out["seed"] = int(self.seed)
        if self.metadata is not None:
            out["metadata"] = dict(self.metadata)
        return out


def build_minimal_context(
    *,
    generation: Optional[int],
    individual_id: int,
    constraints: Any,
    constraint_violation: float,
    seed: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """构造最小 schema 的 context，并允许追加 extra 字段。"""
    try:
        constraints_list = [float(x) for x in (constraints if constraints is not None else [])]
    except Exception:
        constraints_list = []

    ctx = MinimalEvaluationContext(
        generation=None if generation is None else int(generation),
        individual_id=int(individual_id),
        constraints=constraints_list,
        constraint_violation=float(constraint_violation),
        seed=None if seed is None else int(seed),
        metadata=None if metadata is None else dict(metadata),
    ).to_dict()

    if extra:
        ctx.update(dict(extra))
    return ctx


def validate_minimal_context(ctx: Mapping[str, Any]) -> None:
    """浅校验最小上下文：字段存在且类型可转换。"""
    required = ["individual_id", "constraints", "constraint_violation"]
    for k in required:
        if k not in ctx:
            raise ValueError(f"Context missing required key: {k}")

    int(ctx["individual_id"])
    float(ctx["constraint_violation"])
    _ = [float(x) for x in (ctx.get("constraints") or [])]

    if "generation" in ctx and ctx["generation"] is not None:
        int(ctx["generation"])
    if "seed" in ctx and ctx["seed"] is not None:
        int(ctx["seed"])
    if "metadata" in ctx and ctx["metadata"] is not None and not isinstance(ctx["metadata"], Mapping):
        raise ValueError("Context 'metadata' must be a mapping when provided")


# ---------------------------------------------------------------------------
# Full context schema (lifecycle + replay)
# ---------------------------------------------------------------------------

CATEGORY_INPUT = "input"      # stable input (problem/user provided)
CATEGORY_RUNTIME = "runtime"  # runtime state (generation/step/phase)
CATEGORY_DERIVED = "derived"  # derived metrics/statistics
CATEGORY_CACHE = "cache"      # cache-only, not replayable
CATEGORY_OUTPUT = "output"    # output artifacts
CATEGORY_EVENT = "event"      # event/log records


@dataclass(frozen=True)
class ContextField:
    key: str
    category: str
    description: str
    required: bool = False
    replayable: bool = True
    type_hint: Optional[str] = None


@dataclass(frozen=True)
class ContextSchema:
    name: str
    fields: Sequence[ContextField]
    allow_extra: bool = True

    def required_keys(self) -> List[str]:
        return [f.key for f in self.fields if f.required]

    def field_map(self) -> Dict[str, ContextField]:
        return {f.key: f for f in self.fields}


RUNTIME_CONTEXT_SCHEMA = ContextSchema(
    name="runtime_context",
    fields=[
        ContextField("problem", CATEGORY_INPUT, "problem instance handle", replayable=False),
        ContextField("bounds", CATEGORY_INPUT, "variable bounds (optional)"),
        ContextField("constraints", CATEGORY_INPUT, "constraint values (optional)"),
        ContextField("constraint_violation", CATEGORY_INPUT, "constraint violation scalar (optional)"),
        ContextField("individual", CATEGORY_CACHE, "current individual snapshot", replayable=False),
        ContextField("generation", CATEGORY_RUNTIME, "current generation/iteration"),
        ContextField("step", CATEGORY_RUNTIME, "current step (optional)"),
        ContextField("running", CATEGORY_RUNTIME, "solver running flag (optional)"),
        ContextField("phase_id", CATEGORY_RUNTIME, "dynamic phase id (optional)"),
        ContextField("dynamic", CATEGORY_RUNTIME, "dynamic signals/state (optional)"),
        ContextField("mutation_rate", CATEGORY_RUNTIME, "current mutation rate (optional)"),
        ContextField("crossover_rate", CATEGORY_RUNTIME, "current crossover rate (optional)"),
        ContextField("snapshot_key", CATEGORY_OUTPUT, "snapshot store key (optional)"),
        ContextField("snapshot_backend", CATEGORY_OUTPUT, "snapshot backend id (optional)"),
        ContextField("snapshot_schema", CATEGORY_OUTPUT, "snapshot schema version (optional)"),
        ContextField("snapshot_meta", CATEGORY_OUTPUT, "snapshot metadata summary (optional)"),
        ContextField("population_ref", CATEGORY_OUTPUT, "population snapshot reference (optional)"),
        ContextField("objectives_ref", CATEGORY_OUTPUT, "objective snapshot reference (optional)"),
        ContextField("best_x", CATEGORY_RUNTIME, "current best candidate snapshot (optional)"),
        ContextField("best_objective", CATEGORY_RUNTIME, "current best scalar objective (optional)"),
        ContextField("constraint_violations_ref", CATEGORY_OUTPUT, "violation snapshot reference (optional)"),
        ContextField("pareto_solutions_ref", CATEGORY_OUTPUT, "pareto solutions reference (optional)"),
        ContextField("pareto_objectives_ref", CATEGORY_OUTPUT, "pareto objectives reference (optional)"),
        ContextField("history_ref", CATEGORY_OUTPUT, "history reference (optional)"),
        ContextField("decision_trace_ref", CATEGORY_OUTPUT, "decision trace reference (optional)"),
        ContextField("sequence_graph_ref", CATEGORY_OUTPUT, "sequence graph reference (optional)"),
        ContextField(
            "population",
            CATEGORY_CACHE,
            "legacy population snapshot (deprecated; use population_ref/snapshot_key)",
            replayable=False,
        ),
        ContextField(
            "objectives",
            CATEGORY_CACHE,
            "legacy objectives snapshot (deprecated; use objectives_ref/snapshot_key)",
            replayable=False,
        ),
        ContextField(
            "constraint_violations",
            CATEGORY_CACHE,
            "legacy violations snapshot (deprecated; use constraint_violations_ref/snapshot_key)",
            replayable=False,
        ),
        ContextField(
            "pareto_solutions",
            CATEGORY_CACHE,
            "legacy pareto solutions (deprecated; use pareto_solutions_ref)",
            replayable=False,
        ),
        ContextField(
            "pareto_objectives",
            CATEGORY_CACHE,
            "legacy pareto objectives (deprecated; use pareto_objectives_ref)",
            replayable=False,
        ),
        ContextField("candidate_roles", CATEGORY_RUNTIME, "controller candidate role mapping (optional)"),
        ContextField("candidate_units", CATEGORY_RUNTIME, "controller candidate unit mapping (optional)"),
        ContextField("unit_tasks", CATEGORY_RUNTIME, "controller task map per unit (optional)"),
        ContextField("evaluation_count", CATEGORY_RUNTIME, "evaluation counter (optional)"),
        ContextField("metrics", CATEGORY_DERIVED, "metrics dict (optional)"),
        ContextField("history", CATEGORY_EVENT, "legacy runtime history/log (deprecated)", replayable=False),
        ContextField("metadata", CATEGORY_INPUT, "user/experiment metadata (optional)"),
    ],
    allow_extra=True,
)


def validate_context(
    ctx: Mapping[str, Any],
    schema: ContextSchema = RUNTIME_CONTEXT_SCHEMA,
    *,
    strict: bool = False,
) -> List[str]:
    """根据 schema 做弱校验，返回 warning 列表。"""
    warnings: List[str] = []
    field_map = schema.field_map()

    for key in schema.required_keys():
        if key not in ctx:
            msg = f"Context missing required key: {key}"
            if strict:
                raise ValueError(msg)
            warnings.append(msg)

    if not schema.allow_extra:
        for key in ctx.keys():
            if key not in field_map:
                msg = f"Context contains unknown key: {key}"
                if strict:
                    raise ValueError(msg)
                warnings.append(msg)

    for key, value in ctx.items():
        field = field_map.get(key)
        if field is None or value is None:
            continue
        if field.type_hint is None:
            continue
        # type_hint 目前仅用于提示，不做强制类型断言。

    return warnings


def get_context_lifecycle(
    ctx: Mapping[str, Any],
    schema: ContextSchema = RUNTIME_CONTEXT_SCHEMA,
) -> Dict[str, str]:
    """返回 {key: category} 映射，用于标注字段生命周期。"""
    field_map = schema.field_map()
    lifecycle: Dict[str, str] = {}
    for key in ctx.keys():
        field = field_map.get(key)
        lifecycle[key] = field.category if field is not None else "custom"
    return lifecycle


def is_replayable_context(
    ctx: Mapping[str, Any],
    schema: ContextSchema = RUNTIME_CONTEXT_SCHEMA,
) -> bool:
    """判断 context 是否仅包含可重放字段。"""
    field_map = schema.field_map()
    for key in ctx.keys():
        field = field_map.get(key)
        if field is not None and not field.replayable:
            return False
    return True


def strip_context_for_replay(
    ctx: Mapping[str, Any],
    schema: ContextSchema = RUNTIME_CONTEXT_SCHEMA,
) -> Dict[str, Any]:
    """移除不可重放字段，得到用于重放的最小上下文。"""
    field_map = schema.field_map()
    out: Dict[str, Any] = {}
    for key, value in ctx.items():
        field = field_map.get(key)
        if field is None or field.replayable:
            out[key] = value
    return out
