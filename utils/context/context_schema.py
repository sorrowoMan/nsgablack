from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class MinimalEvaluationContext:
    """骞惰/涓茶鍏辩敤鐨勬渶灏忚瘎浼颁笂涓嬫枃锛堝彲搴忓垪鍖栥€佸彲鎵╁睍锛夈€?
    璁捐鐩爣锛氳 bias 鍦ㄥ苟琛岃瘎浼版椂鍙緷璧栧彲鑾峰緱鐨勬渶灏忎俊鎭€?
    绾︽潫锛?    - 涓嶄繚璇佸寘鍚?solver 鐨勫叏灞€鐘舵€侊紙population/history 绛夛級銆?    - 濡傞渶鍏ㄥ眬淇℃伅锛屽簲鍦ㄤ富绾跨▼/涓茶璺緞鏋勯€犲畬鏁?context 骞剁鐢ㄥ苟琛屻€?    """

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
    """鏋勯€犳渶灏?schema 鐨?context锛屽苟鍏佽杩藉姞 extra 瀛楁銆?"""
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
    """娴呮牎楠岋細瀛楁瀛樺湪涓旂被鍨嬪彲杞崲锛堝伐绋嬪寲鎶ゆ爮锛屼笉淇濊瘉涓氬姟姝ｇ‘鎬э級銆?"""
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
        ContextField("phase_id", CATEGORY_RUNTIME, "dynamic phase id (optional)"),
        ContextField("dynamic", CATEGORY_RUNTIME, "dynamic signals/state (optional)"),
        ContextField("population", CATEGORY_CACHE, "population snapshot (optional)", replayable=False),
        ContextField("objectives", CATEGORY_CACHE, "objective snapshot (optional)", replayable=False),
        ContextField("constraint_violations", CATEGORY_CACHE, "violation snapshot (optional)", replayable=False),
        ContextField("pareto_solutions", CATEGORY_CACHE, "pareto solutions snapshot (optional)", replayable=False),
        ContextField("pareto_objectives", CATEGORY_CACHE, "pareto objectives snapshot (optional)", replayable=False),
        ContextField("evaluation_count", CATEGORY_RUNTIME, "evaluation counter (optional)"),
        ContextField("metrics", CATEGORY_DERIVED, "metrics dict (optional)"),
        ContextField("history", CATEGORY_EVENT, "runtime history/log (optional)", replayable=False),
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
    """鏍规嵁 schema 鏍￠獙瀛楁瀛樺湪鎬т笌绫诲瀷鎻愮ず锛堝急鏍￠獙锛岄粯璁ゅ鏉撅級銆?"""
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
        # 绫诲瀷鎻愮ず浠呯敤浜庢彁绀猴紝涓嶅己鍒舵墽琛屽叿浣撶被鍨嬪垽鏂€?        # 杩欓噷淇濇寔瀹芥澗锛岄伩鍏嶇牬鍧忕幇鏈夋ā鍧椼€?    return warnings


def get_context_lifecycle(
    ctx: Mapping[str, Any],
    schema: ContextSchema = RUNTIME_CONTEXT_SCHEMA,
) -> Dict[str, str]:
    """杩斿洖 {key: category} 鏄犲皠锛岀敤浜庢爣娉ㄥ瓧娈电敓鍛藉懆鏈熴€?"""
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
    """鍒ゆ柇 context 鏄惁浠呭寘鍚彲閲嶆斁瀛楁銆?"""
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
    """绉婚櫎涓嶅彲閲嶆斁瀛楁锛屽緱鍒板彲鐢ㄤ簬閲嶆斁鐨勬渶灏忎笂涓嬫枃銆?"""
    field_map = schema.field_map()
    out: Dict[str, Any] = {}
    for key, value in ctx.items():
        field = field_map.get(key)
        if field is None or field.replayable:
            out[key] = value
    return out

