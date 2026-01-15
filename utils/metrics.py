"""Lightweight metrics for multi-objective benchmarking."""

from __future__ import annotations

import numpy as np
from typing import Optional, Sequence, Tuple


def pareto_filter(objectives: Sequence[Sequence[float]]) -> np.ndarray:
    """Return non-dominated objectives (minimization)."""
    obj = np.asarray(objectives, dtype=float)
    if obj.size == 0:
        return obj.reshape((0, 0))
    if obj.ndim == 1:
        obj = obj.reshape(-1, 1)

    n = obj.shape[0]
    dominated = np.zeros(n, dtype=bool)
    for i in range(n):
        if dominated[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            if np.all(obj[j] <= obj[i]) and np.any(obj[j] < obj[i]):
                dominated[i] = True
                break
    return obj[~dominated]


def hypervolume_2d(objectives: Sequence[Sequence[float]],
                   reference_point: Optional[np.ndarray] = None) -> float:
    """Compute 2D hypervolume (minimization)."""
    obj = pareto_filter(objectives)
    if obj.size == 0:
        return 0.0
    if obj.ndim == 1:
        obj = obj.reshape(-1, 1)
    if obj.shape[1] != 2:
        raise ValueError("hypervolume_2d only supports 2 objectives.")

    if reference_point is None:
        reference_point = np.max(obj, axis=0) * 1.1

    sorted_idx = np.argsort(obj[:, 0])
    sorted_obj = obj[sorted_idx]

    volume = 0.0
    for i in range(len(sorted_obj)):
        f1, f2 = sorted_obj[i]
        if i == 0:
            volume += max(0.0, reference_point[0] - f1) * max(0.0, reference_point[1] - f2)
        else:
            prev_f2 = sorted_obj[i - 1, 1]
            volume += max(0.0, reference_point[0] - f1) * max(0.0, prev_f2 - f2)
    return float(volume)


def igd(obtained: Sequence[Sequence[float]],
        reference: Sequence[Sequence[float]]) -> float:
    """Compute inverted generational distance."""
    ref = np.asarray(reference, dtype=float)
    obt = np.asarray(obtained, dtype=float)
    if ref.size == 0 or obt.size == 0:
        return float("inf")
    if ref.ndim == 1:
        ref = ref.reshape(-1, 1)
    if obt.ndim == 1:
        obt = obt.reshape(-1, 1)

    diff = ref[:, None, :] - obt[None, :, :]
    distances = np.linalg.norm(diff, axis=2)
    return float(np.mean(np.min(distances, axis=1)))


def reference_front_zdt1(n_points: int = 1000) -> np.ndarray:
    """Sample reference front for ZDT1."""
    f1 = np.linspace(0.0, 1.0, n_points)
    f2 = 1.0 - np.sqrt(f1)
    return np.column_stack([f1, f2])


def reference_front_zdt3(n_points: int = 1000) -> np.ndarray:
    """Sample reference front for ZDT3 (discontinuous)."""
    segments = [
        (0.0, 0.0830015349),
        (0.1822287280, 0.2577623634),
        (0.4093136748, 0.4538821041),
        (0.6183967944, 0.6525117038),
        (0.8233317983, 0.8518328654),
    ]
    per_segment = max(1, n_points // len(segments))
    points = []
    for lo, hi in segments:
        f1 = np.linspace(lo, hi, per_segment)
        f2 = 1.0 - np.sqrt(f1) - f1 * np.sin(10.0 * np.pi * f1)
        points.append(np.column_stack([f1, f2]))
    front = np.vstack(points)
    return front[:n_points]


def reference_front_dtlz2(n_points: int = 1000,
                          n_objectives: int = 2,
                          seed: Optional[int] = 0) -> np.ndarray:
    """Sample reference front for DTLZ2 (positive orthant of unit hypersphere)."""
    rng = np.random.default_rng(seed)
    samples = rng.normal(size=(n_points, n_objectives))
    samples = np.abs(samples)
    norm = np.linalg.norm(samples, axis=1, keepdims=True)
    norm = np.where(norm == 0.0, 1.0, norm)
    return samples / norm

