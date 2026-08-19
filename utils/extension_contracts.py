"""
扩展点“接口级护栏”（可执行约定）

目标：不限制用户如何拆解算法（Bias/Pipeline/Adapter/Plugin 都可自由组合），
但在关键边界处做最小、明确、可执行的检查，避免把框架用“拆坏”。

该模块只提供轻量校验与标准化函数：
- 不引入第三方依赖
- 默认不改变 dtype（避免把 permutation/int 表示强行转成 float）
"""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple
import math

import numpy as np

from blackbase.types import CandidateBatch, UnknownState


class ContractError(ValueError):
    """扩展点契约违反（输入/输出/shape/语义不符合）。"""


def _as_1d_array(x: Any, *, name: str) -> np.ndarray:
    # ``UnknownState`` is the shared cross-framework candidate protocol.  The
    # NSG control plane remains ndarray-native internally, but its public
    # candidate boundary must consume the protocol returned by Providers and
    # cross-framework Adapters without turning it into an object array.
    if isinstance(x, UnknownState):
        x = x.as_array()
    try:
        arr = np.asarray(x)
    except Exception as exc:  # pragma: no cover
        raise ContractError(f"{name} 必须可转换为 numpy array: {exc}") from exc

    if arr.dtype == object:
        raise ContractError(f"{name} dtype=object（通常意味着形状不一致或包含不可序列化对象）")

    return arr.ravel()


def normalize_candidate(x: Any, *, dimension: int, name: str = "candidate") -> np.ndarray:
    """候选解边界：必须是一维向量且长度等于 dimension。"""
    arr = _as_1d_array(x, name=name)
    if int(arr.size) != int(dimension):
        raise ContractError(f"{name} 长度不匹配: got {int(arr.size)} != expected {int(dimension)}")
    return arr


def normalize_candidates(
    candidates: Sequence[Any],
    *,
    dimension: int,
    owner: str = "adapter/plugin",
) -> List[np.ndarray]:
    if candidates is None:
        return []
    out: List[np.ndarray] = []
    for i, cand in enumerate(list(candidates)):
        out.append(normalize_candidate(cand, dimension=dimension, name=f"{owner}.candidates[{i}]"))
    return out


def normalize_candidate_batch(
    candidates: Sequence[Any],
    *,
    dimension: int,
    owner: str = "adapter/plugin",
    candidate_tokens: Sequence[str | None] = (),
) -> CandidateBatch:
    """Build aligned semantic/numeric views without object-array control state."""

    values = list(candidates or ())
    states: list[UnknownState] = []
    rows: list[np.ndarray] = []
    for index, candidate in enumerate(values):
        state = (
            candidate
            if isinstance(candidate, UnknownState)
            else UnknownState(values=candidate)
        )
        row = normalize_candidate(
            state,
            dimension=dimension,
            name=f"{owner}.candidates[{index}]",
        )
        states.append(UnknownState(values=row.copy(), metadata=dict(state.metadata)))
        rows.append(row)
    matrix = (
        np.stack(rows, axis=0)
        if rows
        else np.empty((0, int(dimension)), dtype=float)
    )
    return CandidateBatch(
        semantic_states=tuple(states),
        numeric_matrix=matrix,
        candidate_tokens=tuple(candidate_tokens),
    )


def stack_population(candidates: Sequence[np.ndarray], *, name: str = "population") -> np.ndarray:
    """将候选解堆叠为 (N, D)；严格要求 shape 一致，避免 object array。"""
    if candidates is None:
        raise ContractError(f"{name} 不能为空")
    if len(candidates) == 0:
        return np.empty((0, 0))
    try:
        pop = np.stack([np.asarray(c) for c in candidates], axis=0)
    except Exception as exc:
        raise ContractError(f"{name} 无法堆叠为二维数组（候选解 shape 不一致）: {exc}") from exc
    if pop.dtype == object:
        raise ContractError(f"{name} dtype=object（候选解 shape 或 dtype 不一致）")
    return pop


def normalize_objectives(value: Any, *, num_objectives: int, name: str = "objectives") -> np.ndarray:
    """目标边界：返回 1D float 数组（长度 <= num_objectives 会被上层补齐/截断）。"""
    arr = np.asarray(value, dtype=float).ravel()
    if arr.size == 0:
        raise ContractError(f"{name} 不能为空")
    if arr.size > int(num_objectives):
        return arr[: int(num_objectives)]
    return arr


def normalize_violation(value: Any, *, name: str = "constraint_violation") -> float:
    try:
        vio = float(value)
    except Exception as exc:
        raise ContractError(f"{name} 必须可转为 float: {exc}") from exc
    if not math.isfinite(vio):
        raise ContractError(f"{name} 必须为有限值: {vio!r}")
    return vio


def normalize_bias_output(value: Any, *, name: str = "bias_output") -> float:
    """偏置输出边界：必须是有限 float。"""
    out = normalize_violation(value, name=name)
    return out


# ---------------------------------------------------------------------------
# Extension-point contract declaration verification
# ---------------------------------------------------------------------------

_CORE_CONTRACT_ATTRS = ("context_requires", "context_provides", "context_mutates", "context_cache")


def verify_component_contract(
    component: Any,
    *,
    strict: bool = False,
    component_name: str | None = None,
) -> List[str]:
    """Check that *component* has declared all four core context contract fields.

    Parameters
    ----------
    component:
        Any adapter, plugin, representation, or bias object.
    strict:
        If True, raise ContractError when any field is missing.
        If False (default), return the list of missing field names.
    component_name:
        Optional display name used in the error message.

    Returns
    -------
    List[str]
        Names of the missing core contract fields (empty = fully declared).
    """
    name = component_name or getattr(component, "name", None) or type(component).__name__
    missing: List[str] = []
    for attr in _CORE_CONTRACT_ATTRS:
        if getattr(component, attr, None) is None:
            missing.append(attr)
    if missing and strict:
        raise ContractError(
            f"Component '{name}' is missing core context contract fields: "
            + ", ".join(missing)
            + ". Declare them as class-level tuples (may be empty: `() `)."
        )
    return missing


def verify_solver_contracts(
    solver: Any,
    *,
    strict: bool = False,
) -> List[Tuple[str, List[str]]]:
    """Walk *solver* components and collect missing contract fields.

    Returns
    -------
    List[Tuple[str, List[str]]]
        List of (component_name, missing_fields) for every component that
        is missing at least one core contract attribute. Empty list = all OK.
    """
    issues: List[Tuple[str, List[str]]] = []

    def _check(label: str, obj: Any) -> None:
        if obj is None:
            return
        m = verify_component_contract(obj, strict=strict, component_name=label)
        if m:
            issues.append((label, m))

    _check("adapter", getattr(solver, "adapter", None))
    adapter = getattr(solver, "adapter", None)
    if adapter is not None:
        for i, spec in enumerate(getattr(adapter, "strategies", ()) or ()):
            sub = getattr(spec, "adapter", None)
            _check(f"adapter.strategy[{i}]", sub)
        for i, role in enumerate(getattr(adapter, "roles", ()) or ()):
            role_adapter = getattr(role, "adapter", None)
            if not callable(role_adapter):
                _check(f"adapter.role[{i}]", role_adapter)

    _check("representation_pipeline", getattr(solver, "representation_pipeline", None))
    _check("bias_module", getattr(solver, "bias_module", None))

    plugin_manager = getattr(solver, "plugin_manager", None)
    if plugin_manager is not None:
        for plugin in getattr(plugin_manager, "plugins", None) or []:
            pname = getattr(plugin, "name", type(plugin).__name__)
            _check(f"plugin.{pname}", plugin)

    return issues

