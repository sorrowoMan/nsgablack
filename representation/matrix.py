"""
Matrix-shaped integer representations and repairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Tuple

import numpy as np

from .base import RepresentationComponentContract
from ..core.state.context_keys import (
    KEY_BLOCK_MAX,
    KEY_BLOCK_MIN,
    KEY_COL_SUMS,
    KEY_DENSITY,
    KEY_K_NONZERO,
    KEY_ROW_SUMS,
    KEY_SHAPE,
)


def _shape_from_context(problem: Any, context: Optional[dict]) -> Tuple[int, int]:
    if context and KEY_SHAPE in context:
        return tuple(context[KEY_SHAPE])
    if hasattr(problem, "matrix_shape"):
        return tuple(problem.matrix_shape)
    if hasattr(problem, "dimension"):
        n = int(np.sqrt(problem.dimension))
        return (n, n)
    raise ValueError("matrix shape is required in context or problem")


@dataclass
class IntegerMatrixInitializer(RepresentationComponentContract):
    rows: Optional[int] = None
    cols: Optional[int] = None
    low: int = 0
    high: int = 10
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Optionally reads matrix shape from context when rows/cols are not explicitly set.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        if self.rows is not None and self.cols is not None:
            shape = (self.rows, self.cols)
        else:
            shape = _shape_from_context(problem, context)
        mat = self._rng.integers(self.low, self.high + 1, size=shape)
        return mat.reshape(-1)


@dataclass
class IntegerMatrixMutation(RepresentationComponentContract):
    sigma: float = 0.5
    low: int = 0
    high: int = 10
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Matrix mutation uses local sigma/limits; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = x + self._rng.normal(0.0, self.sigma, size=x.shape)
        mutated = np.clip(np.round(mutated), self.low, self.high).astype(int)
        return mutated


@dataclass
class MatrixRowColSumRepair(RepresentationComponentContract):
    row_sums: Optional[np.ndarray] = None
    col_sums: Optional[np.ndarray] = None
    max_passes: int = 5
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Repairs row/col totals using optional targets from context with deterministic balancing.",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if context and KEY_SHAPE in context:
            rows, cols = context[KEY_SHAPE]
        else:
            rows, cols = int(np.sqrt(len(x))), int(np.sqrt(len(x)))
        mat = np.array(x, copy=True).reshape(rows, cols)

        target_rows = self.row_sums
        target_cols = self.col_sums
        if context:
            target_rows = context.get(KEY_ROW_SUMS, target_rows)
            target_cols = context.get(KEY_COL_SUMS, target_cols)

        if target_rows is None and target_cols is None:
            return mat.reshape(-1)

        if target_rows is not None:
            target_rows = np.asarray(target_rows, dtype=int).reshape(rows)
            for i in range(rows):
                diff = int(target_rows[i] - np.sum(mat[i]))
                if diff != 0:
                    mat[i, 0] += diff

        if target_cols is not None:
            target_cols = np.asarray(target_cols, dtype=int).reshape(cols)
            if target_rows is None:
                for j in range(cols):
                    diff = int(target_cols[j] - np.sum(mat[:, j]))
                    if diff != 0:
                        mat[0, j] += diff
            else:
                # Keep row sums fixed by moving quantity between columns within rows.
                col_diff = target_cols - np.sum(mat, axis=0)
                for _ in range(max(1, int(self.max_passes) * rows * cols)):
                    deficits = np.where(col_diff > 0)[0]
                    surpluses = np.where(col_diff < 0)[0]
                    if deficits.size == 0 or surpluses.size == 0:
                        break
                    d = int(deficits[0])
                    s = int(surpluses[0])
                    move = int(min(col_diff[d], -col_diff[s]))
                    if move <= 0:
                        break
                    mat[0, d] += move
                    mat[0, s] -= move
                    col_diff[d] -= move
                    col_diff[s] += move

        return mat.reshape(-1)


@dataclass
class MatrixSparsityRepair(RepresentationComponentContract):
    density: Optional[float] = None
    k_nonzero: Optional[int] = None
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Optionally repairs sparsity using k_nonzero/density from context.",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        vec = np.array(x, copy=True)
        n = len(vec)
        k = self.k_nonzero
        if context and KEY_K_NONZERO in context:
            k = context[KEY_K_NONZERO]
        if k is None:
            density = self.density if self.density is not None else context.get(KEY_DENSITY, 0.1) if context else 0.1
            k = max(1, int(n * density))

        if k >= n:
            return vec

        idx = np.argsort(np.abs(vec))[::-1]
        keep = idx[:k]
        out = np.zeros_like(vec)
        out[keep] = vec[keep]
        return out


@dataclass
class MatrixBlockSumRepair(RepresentationComponentContract):
    block_shape: Tuple[int, int] = (2, 2)
    block_min: Optional[float] = None
    block_max: Optional[float] = None
    low: int = 0
    high: int = 10
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Optionally repairs block-level sum bounds using context targets.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if context and KEY_SHAPE in context:
            rows, cols = context[KEY_SHAPE]
        else:
            rows, cols = int(np.sqrt(len(x))), int(np.sqrt(len(x)))
        mat = np.array(x, copy=True).reshape(rows, cols)
        br, bc = self.block_shape

        block_min = self.block_min if self.block_min is not None else (context.get(KEY_BLOCK_MIN) if context else None)
        block_max = self.block_max if self.block_max is not None else (context.get(KEY_BLOCK_MAX) if context else None)
        if block_min is None and block_max is None:
            return mat.reshape(-1)

        for i in range(0, rows, br):
            for j in range(0, cols, bc):
                block = mat[i:i + br, j:j + bc]
                s = np.sum(block)
                if block_max is not None and s > block_max:
                    delta = s - block_max
                    block.flat[self._rng.integers(0, block.size)] -= delta
                if block_min is not None and s < block_min:
                    delta = block_min - s
                    block.flat[self._rng.integers(0, block.size)] += delta
                block = np.clip(block, self.low, self.high)
                mat[i:i + br, j:j + bc] = block

        return mat.reshape(-1)
