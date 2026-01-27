from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class MinimalEvaluationContext:
    """并行/串行共用的最小评估上下文（可序列化、可扩展）。

    设计目标：让 bias 在并行评估时只依赖可获得的最小信息。

    约束：
    - 不保证包含 solver 的全局状态（population/history 等）。
    - 如需全局信息，应在主线程/串行路径构造完整 context 并禁用并行。
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
    """浅校验：字段存在且类型可转换（工程化护栏，不保证业务正确性）。"""
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
