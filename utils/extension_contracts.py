"""
扩展点“接口级护栏”（可执行约定）

目标：不限制用户如何拆解算法（Bias/Pipeline/Adapter/Plugin 都可自由组合），
但在关键边界处做最小、明确、可执行的检查，避免把框架用“拆坏”。

该模块只提供轻量校验与标准化函数：
- 不引入第三方依赖
- 默认不改变 dtype（避免把 permutation/int 表示强行转成 float）
"""

from __future__ import annotations

from typing import Any, Iterable, List, Sequence, Tuple
import math

import numpy as np


class ContractError(ValueError):
    """扩展点契约违反（输入/输出/shape/语义不符合）。"""


def _as_1d_array(x: Any, *, name: str) -> np.ndarray:
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

