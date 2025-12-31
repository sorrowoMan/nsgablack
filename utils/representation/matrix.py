"""
Matrix-shaped integer representations and repairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Tuple

import numpy as np


def _shape_from_context(problem: Any, context: Optional[dict]) -> Tuple[int, int]:
    if context and "shape" in context:
        return tuple(context["shape"])
    if hasattr(problem, "matrix_shape"):
        return tuple(problem.matrix_shape)
    if hasattr(problem, "dimension"):
        n = int(np.sqrt(problem.dimension))
        return (n, n)
    raise ValueError("matrix shape is required in context or problem")


@dataclass
class IntegerMatrixInitializer:
    rows: Optional[int] = None
    cols: Optional[int] = None
    low: int = 0
    high: int = 10

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        if self.rows is not None and self.cols is not None:
            shape = (self.rows, self.cols)
        else:
            shape = _shape_from_context(problem, context)
        mat = np.random.randint(self.low, self.high + 1, size=shape)
        return mat.reshape(-1)


@dataclass
class IntegerMatrixMutation:
    sigma: float = 0.5
    low: int = 0
    high: int = 10

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = x + np.random.normal(0.0, self.sigma, size=x.shape)
        mutated = np.clip(np.round(mutated), self.low, self.high).astype(int)
        return mutated


@dataclass
class MatrixRowColSumRepair:
    row_sums: Optional[np.ndarray] = None
    col_sums: Optional[np.ndarray] = None
    max_passes: int = 5

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if context and "shape" in context:
            rows, cols = context["shape"]
        else:
            rows, cols = int(np.sqrt(len(x))), int(np.sqrt(len(x)))
        mat = np.array(x, copy=True).reshape(rows, cols)

        target_rows = self.row_sums
        target_cols = self.col_sums
        if context:
            target_rows = context.get("row_sums", target_rows)
            target_cols = context.get("col_sums", target_cols)

        if target_rows is None and target_cols is None:
            return mat.reshape(-1)

        for _ in range(self.max_passes):
            if target_rows is not None:
                for i in range(rows):
                    diff = int(target_rows[i] - np.sum(mat[i]))
                    if diff != 0:
                        j = np.random.randint(0, cols)
                        mat[i, j] += diff
            if target_cols is not None:
                for j in range(cols):
                    diff = int(target_cols[j] - np.sum(mat[:, j]))
                    if diff != 0:
                        i = np.random.randint(0, rows)
                        mat[i, j] += diff

        return mat.reshape(-1)


@dataclass
class MatrixSparsityRepair:
    density: Optional[float] = None
    k_nonzero: Optional[int] = None

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        vec = np.array(x, copy=True)
        n = len(vec)
        k = self.k_nonzero
        if context and "k_nonzero" in context:
            k = context["k_nonzero"]
        if k is None:
            density = self.density if self.density is not None else context.get("density", 0.1) if context else 0.1
            k = max(1, int(n * density))

        if k >= n:
            return vec

        idx = np.argsort(np.abs(vec))[::-1]
        keep = idx[:k]
        out = np.zeros_like(vec)
        out[keep] = vec[keep]
        return out


@dataclass
class MatrixBlockSumRepair:
    block_shape: Tuple[int, int] = (2, 2)
    block_min: Optional[float] = None
    block_max: Optional[float] = None
    low: int = 0
    high: int = 10

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if context and "shape" in context:
            rows, cols = context["shape"]
        else:
            rows, cols = int(np.sqrt(len(x))), int(np.sqrt(len(x)))
        mat = np.array(x, copy=True).reshape(rows, cols)
        br, bc = self.block_shape

        block_min = self.block_min if self.block_min is not None else (context.get("block_min") if context else None)
        block_max = self.block_max if self.block_max is not None else (context.get("block_max") if context else None)
        if block_min is None and block_max is None:
            return mat.reshape(-1)

        for i in range(0, rows, br):
            for j in range(0, cols, bc):
                block = mat[i:i + br, j:j + bc]
                s = np.sum(block)
                if block_max is not None and s > block_max:
                    delta = s - block_max
                    block.flat[np.random.randint(0, block.size)] -= delta
                if block_min is not None and s < block_min:
                    delta = block_min - s
                    block.flat[np.random.randint(0, block.size)] += delta
                block = np.clip(block, self.low, self.high)
                mat[i:i + br, j:j + bc] = block

        return mat.reshape(-1)
