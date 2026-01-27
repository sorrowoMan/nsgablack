from __future__ import annotations

"""Numba 加速用的可选辅助函数集合。

若未安装 numba，本模块会优雅退化为普通 Python/numpy 实现，不影响功能。
"""

import numpy as np

try:
    from numba import njit  # type: ignore
    NUMBA_AVAILABLE = True
except Exception:  # 包含 ImportError 等
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):  # type: ignore
        """占位装饰器：在未安装 numba 时原样返回函数。"""

        def wrapper(f):
            return f

        return wrapper


@njit(cache=True)
def fast_is_dominated(obj: np.ndarray) -> np.ndarray:
    """Numba 加速的非支配判定实现。

    参数
    ------
    obj : ndarray, shape (N, M)
        N 个个体、M 个目标的目标值矩阵，按“越小越好”假设。

    返回
    ------
    dominated : ndarray[bool], shape (N,)
        dominated[i] 为 True 表示个体 i 被至少一个其他个体支配。
    """
    N = obj.shape[0]
    M = obj.shape[1]
    dominated = np.zeros(N, dtype=np.bool_)

    for i in range(N):
        if dominated[i]:
            continue
        for j in range(N):
            if i == j:
                continue
            less_equal = True
            strictly_less = False
            for k in range(M):
                vij = obj[j, k]
                vii = obj[i, k]
                if vij > vii:
                    less_equal = False
                    break
                elif vij < vii:
                    strictly_less = True
            if less_equal and strictly_less:
                dominated[i] = True
                break

    return dominated
