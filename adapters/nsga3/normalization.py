"""Deb--Jain hyperplane normalization and reference-line association (NumPy).

Degenerate intercepts fall back to observed maxima; historic worst-point
clamping follows pymoo's documented numerical safeguard. No pymoo dependency.
"""
import numpy as np


def update_normalization(state, objectives, nondominated):
    f = np.asarray(objectives, dtype=float)
    if f.ndim != 2 or not len(f) or not np.isfinite(f).all():
        raise ValueError("NSGA-III normalization requires finite objective rows")
    ideal = np.minimum(np.asarray(state.get("ideal", np.full(f.shape[1], np.inf))), f.min(axis=0))
    worst = np.maximum(np.asarray(state.get("worst", np.full(f.shape[1], -np.inf))), f.max(axis=0))
    front = f[np.asarray(nondominated, dtype=int)]
    old = state.get("extremes")
    points = front if old is None else np.vstack((np.asarray(old), front))
    translated = points - ideal
    translated[translated < 1e-3] = 0.
    extremes = []
    for axis in range(f.shape[1]):
        weights = np.full(f.shape[1], 1e6)
        weights[axis] = 1.
        extremes.append(points[np.argmin(np.max(translated * weights, axis=1))])
    extremes = np.asarray(extremes)
    try:
        plane = np.linalg.solve(extremes - ideal, np.ones(f.shape[1]))
        with np.errstate(divide="ignore", invalid="ignore"):
            intercepts = 1. / plane
        if (not np.isfinite(intercepts).all() or np.any(intercepts <= 1e-6)
                or not np.allclose((extremes - ideal) @ plane, np.ones(f.shape[1]))):
            raise np.linalg.LinAlgError("degenerate intercepts")
        nadir = np.minimum(ideal + intercepts, worst)
    except np.linalg.LinAlgError:
        nadir = front.max(axis=0)
    nadir = np.where(nadir - ideal <= 1e-6, f.max(axis=0), nadir)
    return {"ideal": ideal, "worst": worst, "extremes": extremes, "nadir": nadir}


def associate(objectives, references, normalization):
    refs = np.asarray(references, dtype=float)
    lengths = np.linalg.norm(refs, axis=1)
    if not np.isfinite(refs).all() or np.any(lengths <= 0):
        raise ValueError("NSGA-III requires finite nonzero reference directions")
    denominator = normalization["nadir"] - normalization["ideal"]
    denominator = np.where(denominator == 0, 1e-12, denominator)
    points = (np.asarray(objectives) - normalization["ideal"]) / denominator
    unit_refs = refs / lengths[:, None]
    projection = points @ unit_refs.T
    # Explicit residual avoids cancellation for points lying on a reference line.
    residual = points[:, None, :] - projection[:, :, None] * unit_refs[None, :, :]
    distances = np.linalg.norm(residual, axis=2)
    assignment = distances.argmin(axis=1)
    return assignment, distances[np.arange(len(points)), assignment]


def niche_select(front, remaining, counts, assignment, distance, rng):
    available = np.ones(len(front), dtype=bool)
    chosen = []
    while len(chosen) < remaining:
        niches = np.unique(assignment[available])
        least = niches[counts[niches] == counts[niches].min()]
        for niche in least[rng.permutation(len(least))[:remaining-len(chosen)]]:
            candidates = np.flatnonzero(available & (assignment == niche))
            rng.shuffle(candidates)
            selected = candidates[np.argmin(distance[candidates])] if counts[niche] == 0 else candidates[0]
            available[selected] = False
            chosen.append(int(front[selected]))
            counts[niche] += 1
    return np.asarray(chosen, dtype=int)
