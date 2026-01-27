"""
约束评估工具函数。
"""

from __future__ import annotations

import logging
from typing import Any, Tuple
import numpy as np

logger = logging.getLogger(__name__)


def evaluate_constraints_safe(problem: Any, x: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    安全地评估约束。

    Returns:
        (constraint_array, violation_value)
    """
    try:
        cons = problem.evaluate_constraints(x)
        cons_arr = np.asarray(cons, dtype=float).flatten()
        violation = float(np.sum(np.maximum(cons_arr, 0.0))) if cons_arr.size > 0 else 0.0
        return cons_arr, violation
    except AttributeError:
        # 无约束接口，视为可行
        return np.zeros(0, dtype=float), 0.0
    except Exception as e:
        logger.warning("约束评估失败: %s", e, exc_info=True)
        return np.zeros(0, dtype=float), float('inf')


def evaluate_constraints_batch_safe(
    problem: Any,
    population: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Safely evaluate constraints for a population."""
    pop = np.asarray(population, dtype=float)
    if pop.ndim == 1:
        pop = pop.reshape(1, -1)
    pop_size = pop.shape[0]

    constraints_list = []
    violations = np.zeros(pop_size, dtype=float)

    for idx in range(pop_size):
        cons_arr, violation = evaluate_constraints_safe(problem, pop[idx])
        constraints_list.append(cons_arr)
        violations[idx] = violation

    max_len = max((len(cons) for cons in constraints_list), default=0)
    constraints = np.zeros((pop_size, max_len), dtype=float)
    for i, cons in enumerate(constraints_list):
        if cons.size > 0:
            constraints[i, : cons.size] = cons

    return constraints, violations
