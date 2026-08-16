"""Standalone symbolic structure demo: joint bundle + beam search.

This script is intentionally self-contained and does NOT modify project
registries or default build pipelines.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Sequence

import numpy as np
import pandas as pd

try:
    from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.base import RepresentationComponentContract
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.base import RepresentationComponentContract


_EPS = 1e-12


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    diff = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean(diff * diff)))


@dataclass(frozen=True)
class SyntheticPoolData:
    phi_train: np.ndarray
    y_train: np.ndarray
    phi_valid: np.ndarray
    y_valid: np.ndarray
    feature_names: tuple[str, ...]

    @staticmethod
    def make(
        *,
        n_train: int,
        n_valid: int,
        n_candidates: int,
        true_terms: int,
        noise: float,
        seed: int,
    ) -> "SyntheticPoolData":
        rng = np.random.default_rng(int(seed))
        phi_train = rng.normal(size=(int(n_train), int(n_candidates)))
        phi_valid = rng.normal(size=(int(n_valid), int(n_candidates)))
        k_true = max(1, min(int(true_terms), int(n_candidates)))
        hidden = rng.choice(int(n_candidates), size=k_true, replace=False)
        coef = rng.normal(loc=0.0, scale=1.0, size=k_true)
        y_train = phi_train[:, hidden] @ coef + float(noise) * rng.normal(size=int(n_train))
        y_valid = phi_valid[:, hidden] @ coef + float(noise) * rng.normal(size=int(n_valid))
        names = tuple(f"op_{i}" for i in range(int(n_candidates)))
        return SyntheticPoolData(
            phi_train=np.asarray(phi_train, dtype=float),
            y_train=np.asarray(y_train, dtype=float).reshape(-1),
            phi_valid=np.asarray(phi_valid, dtype=float),
            y_valid=np.asarray(y_valid, dtype=float).reshape(-1),
            feature_names=names,
        )


def _safe_log1p_abs(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.abs(x))


def _safe_sqrt_abs(x: np.ndarray) -> np.ndarray:
    return np.sqrt(np.abs(x))


def _safe_tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


def _zscore(x: np.ndarray) -> np.ndarray:
    mean = float(np.mean(x))
    std = float(np.std(x))
    if std < 1e-12:
        return np.zeros_like(x, dtype=float)
    return (x - mean) / std


def build_pool_from_dataframe(
    df: pd.DataFrame,
    *,
    target_col: str,
    test_mask: np.ndarray,
    max_pairwise: int = 64,
) -> SyntheticPoolData:
    """Build cached candidate matrix from a real traffic dataframe."""
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    ignored = {target_col}
    ignored.update({c for c in df.columns if c.startswith("test_fold_")})
    ignored.add("date")
    feature_cols = [c for c in numeric_cols if c not in ignored]
    if not feature_cols:
        raise ValueError("No numeric feature columns available after filtering")

    base = df[feature_cols].to_numpy(dtype=float)
    y = df[target_col].to_numpy(dtype=float).reshape(-1)

    feat_list: list[np.ndarray] = []
    names: list[str] = []
    for i, col in enumerate(feature_cols):
        x = _zscore(base[:, i])
        feat_list.append(x)
        names.append(col)
        feat_list.append(_safe_tanh(x))
        names.append(f"tanh({col})")
        feat_list.append(np.square(x))
        names.append(f"square({col})")
        feat_list.append(_safe_log1p_abs(x))
        names.append(f"log1p_abs({col})")
        feat_list.append(_safe_sqrt_abs(x))
        names.append(f"sqrt_abs({col})")

    pair_budget = max(0, int(max_pairwise))
    pair_count = 0
    for i in range(len(feature_cols)):
        if pair_count >= pair_budget:
            break
        for j in range(i + 1, len(feature_cols)):
            xi = _zscore(base[:, i])
            xj = _zscore(base[:, j])
            feat_list.append(xi * xj)
            names.append(f"{feature_cols[i]}*{feature_cols[j]}")
            pair_count += 1
            if pair_count >= pair_budget:
                break

    phi = np.column_stack(feat_list).astype(float)
    train_mask = ~np.asarray(test_mask, dtype=bool)
    if np.sum(train_mask) < 16 or np.sum(test_mask) < 8:
        raise ValueError("Split too small; check fold mask")

    return SyntheticPoolData(
        phi_train=phi[train_mask],
        y_train=y[train_mask],
        phi_valid=phi[test_mask],
        y_valid=y[test_mask],
        feature_names=tuple(names),
    )


class SymbolicPoolProblem(BlackBoxProblem):
    """Candidate DB lookup + closed-form ridge evaluation."""

    def __init__(
        self,
        data: SyntheticPoolData,
        *,
        max_terms: int = 8,
        ridge_alpha: float = 1e-3,
        cache_limit: int = 20_000,
    ) -> None:
        n_candidates = int(data.phi_train.shape[1])
        bounds = {f"x{i}": [0.0, 1.0] for i in range(n_candidates)}
        super().__init__(
            name="SymbolicPoolProblem",
            dimension=n_candidates,
            bounds=bounds,
            objectives=["rmse_valid", "complexity"],
        )
        self.phi_train = np.asarray(data.phi_train, dtype=float)
        self.y_train = np.asarray(data.y_train, dtype=float).reshape(-1)
        self.phi_valid = np.asarray(data.phi_valid, dtype=float)
        self.y_valid = np.asarray(data.y_valid, dtype=float).reshape(-1)
        self.feature_names = tuple(data.feature_names)
        self.max_terms = max(1, min(int(max_terms), n_candidates))
        self.ridge_alpha = max(0.0, float(ridge_alpha))
        self.cache_limit = max(100, int(cache_limit))
        self._train_col_norm = np.linalg.norm(self.phi_train, axis=0) + _EPS
        self._cache: dict[bytes, dict[str, np.ndarray | float]] = {}

    def decode_mask(self, x: np.ndarray | Sequence[float]) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(-1)
        if arr.size < self.dimension:
            arr = np.pad(arr, (0, self.dimension - arr.size))
        elif arr.size > self.dimension:
            arr = arr[: self.dimension]
        arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)
        arr = np.clip(arr, 0.0, 1.0)
        mask = arr >= 0.5
        if int(np.sum(mask)) <= self.max_terms:
            return mask.astype(bool)
        keep = np.argpartition(arr, -self.max_terms)[-self.max_terms :]
        out = np.zeros(self.dimension, dtype=bool)
        out[keep] = True
        return out

    def encode_mask(self, mask: np.ndarray | Sequence[bool]) -> np.ndarray:
        return np.asarray(mask, dtype=bool).astype(float)

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        mask = self.decode_mask(candidate)
        payload = self._evaluate_mask(mask)
        return np.array([float(payload["rmse_valid"]), float(np.sum(mask))], dtype=float)

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        mask = self.decode_mask(candidate)
        overflow = max(0.0, float(np.sum(mask)) - float(self.max_terms))
        return np.array([overflow], dtype=float)

    def residual_from_mask(self, mask: np.ndarray | Sequence[bool]) -> np.ndarray:
        safe = self.decode_mask(np.asarray(mask, dtype=float))
        payload = self._evaluate_mask(safe)
        return np.asarray(payload["residual_train"], dtype=float).reshape(-1)

    def rank_candidates_by_residual(
        self,
        residual: np.ndarray,
        *,
        exclude_mask: np.ndarray | Sequence[bool] | None = None,
        top_n: int = 64,
    ) -> np.ndarray:
        r = np.asarray(residual, dtype=float).reshape(-1)
        denom = self._train_col_norm * (np.linalg.norm(r) + _EPS)
        score = np.abs(self.phi_train.T @ r) / denom
        if exclude_mask is not None:
            ex = np.asarray(exclude_mask, dtype=bool).reshape(-1)
            if ex.size == self.dimension:
                score[ex] = -np.inf
        order = np.argsort(-score)
        k = max(1, min(int(top_n), self.dimension))
        return np.asarray(order[:k], dtype=int)

    def omp_bundle_from_shortlist(
        self,
        base_mask: np.ndarray | Sequence[bool],
        shortlist: Sequence[int],
        *,
        bundle_size: int = 3,
    ) -> tuple[int, ...]:
        mask = np.asarray(base_mask, dtype=bool).reshape(-1).copy()
        picked: list[int] = []
        for _ in range(max(0, int(bundle_size))):
            if int(np.sum(mask)) >= self.max_terms:
                break
            residual = self.residual_from_mask(mask)
            candidates = [int(i) for i in shortlist if 0 <= int(i) < self.dimension and not mask[int(i)]]
            if not candidates:
                break
            idx = np.asarray(candidates, dtype=int)
            cols = self.phi_train[:, idx]
            norms = np.linalg.norm(cols, axis=0) + _EPS
            score = np.abs(cols.T @ residual) / (norms * (np.linalg.norm(residual) + _EPS))
            best = int(idx[int(np.argmax(score))])
            mask[best] = True
            picked.append(best)
        return tuple(picked)

    def selected_feature_names(self, mask: np.ndarray | Sequence[bool], limit: int = 12) -> list[str]:
        idx = np.flatnonzero(np.asarray(mask, dtype=bool))
        return [self.feature_names[int(i)] for i in idx[: max(1, int(limit))]]

    def _mask_key(self, mask: np.ndarray) -> bytes:
        packed = np.packbits(mask.astype(np.uint8), bitorder="little")
        return bytes(packed.tolist())

    def _evaluate_mask(self, mask: np.ndarray) -> dict[str, np.ndarray | float]:
        key = self._mask_key(mask)
        got = self._cache.get(key)
        if got is not None:
            return got
        payload = self._fit(mask)
        if len(self._cache) >= self.cache_limit:
            first = next(iter(self._cache))
            self._cache.pop(first, None)
        self._cache[key] = payload
        return payload

    def _fit(self, mask: np.ndarray) -> dict[str, np.ndarray | float]:
        selected = np.flatnonzero(mask)
        n_train = int(self.phi_train.shape[0])
        n_valid = int(self.phi_valid.shape[0])
        if selected.size == 0:
            bias = float(np.mean(self.y_train))
            pred_train = np.full((n_train,), bias, dtype=float)
            pred_valid = np.full((n_valid,), bias, dtype=float)
            residual = self.y_train - pred_train
            return {
                "rmse_valid": _rmse(self.y_valid, pred_valid),
                "residual_train": residual,
            }
        d_train = np.column_stack([np.ones((n_train, 1), dtype=float), self.phi_train[:, selected]])
        d_valid = np.column_stack([np.ones((n_valid, 1), dtype=float), self.phi_valid[:, selected]])
        reg = np.eye(d_train.shape[1], dtype=float)
        reg[0, 0] = 0.0
        lhs = d_train.T @ d_train + self.ridge_alpha * reg
        rhs = d_train.T @ self.y_train
        try:
            coef = np.linalg.solve(lhs, rhs)
        except np.linalg.LinAlgError:
            coef = np.linalg.lstsq(lhs, rhs, rcond=None)[0]
        pred_train = d_train @ coef
        pred_valid = d_valid @ coef
        residual = self.y_train - pred_train
        return {
            "rmse_valid": _rmse(self.y_valid, pred_valid),
            "residual_train": residual,
        }


class SparseBinaryInitializer(RepresentationComponentContract):
    def __init__(self, max_active: int = 8, seed: int = 7) -> None:
        self.max_active = max(1, int(max_active))
        self._rng = np.random.default_rng(int(seed))

    def initialize(self, problem, context: Dict[str, Any] | None = None) -> np.ndarray:
        _ = context
        dim = int(getattr(problem, "dimension", 1))
        cap = max(1, min(self.max_active, dim))
        k = int(self._rng.integers(1, cap + 1))
        idx = self._rng.choice(dim, size=k, replace=False)
        out = np.zeros((dim,), dtype=float)
        out[idx] = 1.0
        return out


class SparseBinaryMutation(RepresentationComponentContract):
    def __init__(self, flip_prob: float = 0.05, seed: int = 11) -> None:
        self.flip_prob = max(0.0, min(1.0, float(flip_prob)))
        self._rng = np.random.default_rng(int(seed))

    def mutate(self, x: np.ndarray, context: Dict[str, Any] | None = None) -> np.ndarray:
        _ = context
        arr = np.asarray(x, dtype=float).reshape(-1)
        if arr.size == 0:
            return arr
        bits = arr >= 0.5
        flips = self._rng.random(arr.size) < self.flip_prob
        bits[flips] = ~bits[flips]
        return bits.astype(float)


class SparseBinaryRepair(RepresentationComponentContract):
    def __init__(self, max_active: int = 8) -> None:
        self.max_active = max(1, int(max_active))

    def repair(self, x: np.ndarray, context: Dict[str, Any] | None = None) -> np.ndarray:
        _ = context
        arr = np.asarray(x, dtype=float).reshape(-1)
        arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)
        arr = np.clip(arr, 0.0, 1.0)
        mask = arr >= 0.5
        if int(np.sum(mask)) <= self.max_active:
            return mask.astype(float)
        keep = np.argpartition(arr, -self.max_active)[-self.max_active :]
        out = np.zeros_like(arr, dtype=float)
        out[keep] = 1.0
        return out


class JointBeamAdapter(AlgorithmAdapter):
    """Joint bundle expansion and beam selection."""

    def __init__(
        self,
        *,
        beam_width: int = 16,
        shortlist_size: int = 64,
        expansions_per_state: int = 6,
        bundle_size: int = 3,
        max_candidates: int = 320,
        objective1_weight: float = 0.02,
        violation_weight: float = 1e6,
    ) -> None:
        super().__init__(name="joint_beam_demo")
        self.beam_width = max(1, int(beam_width))
        self.shortlist_size = max(4, int(shortlist_size))
        self.expansions_per_state = max(1, int(expansions_per_state))
        self.bundle_size = max(1, int(bundle_size))
        self.max_candidates = max(self.beam_width, int(max_candidates))
        self.objective1_weight = float(objective1_weight)
        self.violation_weight = float(violation_weight)
        self._beam_masks: list[np.ndarray] = []

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        problem = getattr(control, "problem", None)
        if problem is None:
            return []
        if not self._beam_masks:
            self._beam_masks = self._bootstrap(problem)
        out: list[np.ndarray] = []
        seen: set[bytes] = set()
        for parent in self._beam_masks[: self.beam_width]:
            residual = np.asarray(problem.residual_from_mask(parent), dtype=float).reshape(-1)
            shortlist = np.asarray(
                problem.rank_candidates_by_residual(
                    residual,
                    exclude_mask=parent,
                    top_n=self.shortlist_size,
                ),
                dtype=int,
            )
            produced = 0
            for anchor in shortlist:
                if produced >= self.expansions_per_state:
                    break
                child = np.asarray(parent, dtype=bool).copy()
                child[int(anchor)] = True
                if self.bundle_size > 1:
                    follow = [int(v) for v in shortlist if int(v) != int(anchor)]
                    bundle = problem.omp_bundle_from_shortlist(
                        child,
                        follow,
                        bundle_size=self.bundle_size - 1,
                    )
                    for idx in bundle:
                        child[int(idx)] = True
                safe = np.asarray(problem.decode_mask(problem.encode_mask(child)), dtype=bool)
                key = self._mask_key(safe)
                if key in seen:
                    continue
                seen.add(key)
                out.append(np.asarray(problem.encode_mask(safe), dtype=float))
                produced += 1
                if len(out) >= self.max_candidates:
                    break
            if len(out) >= self.max_candidates:
                break
        if not out:
            out = [np.asarray(problem.encode_mask(mask), dtype=float) for mask in self._beam_masks[: self.beam_width]]
        return out

    def update(self, control: Any, candidates: Sequence[np.ndarray], feedback, context: Dict[str, Any]) -> None:
        objectives, violations = feedback
        _ = control
        _ = context
        if candidates is None or len(candidates) == 0:
            return
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if vio.shape[0] != obj.shape[0]:
            vio = np.zeros((obj.shape[0],), dtype=float)
        score = obj[:, 0].copy()
        if obj.shape[1] > 1:
            score += self.objective1_weight * obj[:, 1]
        score += self.violation_weight * np.maximum(vio, 0.0)
        order = np.argsort(score)
        problem = getattr(control, "problem", None)
        if problem is None:
            return
        beam: list[np.ndarray] = []
        seen: set[bytes] = set()
        for i in order:
            safe = np.asarray(problem.decode_mask(candidates[int(i)]), dtype=bool)
            key = self._mask_key(safe)
            if key in seen:
                continue
            seen.add(key)
            beam.append(safe)
            if len(beam) >= self.beam_width:
                break
        if beam:
            self._beam_masks = beam

    def _bootstrap(self, problem: SymbolicPoolProblem) -> list[np.ndarray]:
        base = np.zeros(int(problem.dimension), dtype=bool)
        residual = np.asarray(problem.residual_from_mask(base), dtype=float).reshape(-1)
        shortlist = np.asarray(
            problem.rank_candidates_by_residual(
                residual,
                exclude_mask=base,
                top_n=max(self.shortlist_size, self.beam_width),
            ),
            dtype=int,
        )
        beam: list[np.ndarray] = []
        seen: set[bytes] = set()
        for anchor in shortlist:
            child = base.copy()
            child[int(anchor)] = True
            if self.bundle_size > 1:
                follow = [int(v) for v in shortlist if int(v) != int(anchor)]
                bundle = problem.omp_bundle_from_shortlist(
                    child,
                    follow,
                    bundle_size=self.bundle_size - 1,
                )
                for idx in bundle:
                    child[int(idx)] = True
            safe = np.asarray(problem.decode_mask(problem.encode_mask(child)), dtype=bool)
            key = self._mask_key(safe)
            if key in seen:
                continue
            seen.add(key)
            beam.append(safe)
            if len(beam) >= self.beam_width:
                break
        return beam or [base]

    @staticmethod
    def _mask_key(mask: np.ndarray) -> bytes:
        packed = np.packbits(np.asarray(mask, dtype=np.uint8), bitorder="little")
        return bytes(packed.tolist())


def build_solver(args: argparse.Namespace) -> tuple[EvolutionSolver, SymbolicPoolProblem]:
    if args.csv:
        df = pd.read_csv(str(args.csv))
        if str(args.target_col) not in df.columns:
            raise ValueError(f"target_col not found: {args.target_col}")
        fold_col = str(args.fold_col)
        if fold_col not in df.columns:
            raise ValueError(f"fold_col not found: {fold_col}")
        test_mask = df[fold_col].astype(int).to_numpy() == 1
        data = build_pool_from_dataframe(
            df,
            target_col=str(args.target_col),
            test_mask=test_mask,
            max_pairwise=int(args.max_pairwise),
        )
    else:
        data = SyntheticPoolData.make(
            n_train=int(args.n_train),
            n_valid=int(args.n_valid),
            n_candidates=int(args.n_candidates),
            true_terms=int(args.true_terms),
            noise=float(args.noise),
            seed=int(args.seed),
        )
    problem = SymbolicPoolProblem(
        data,
        max_terms=int(args.max_terms),
        ridge_alpha=float(args.ridge_alpha),
    )
    pipeline = RepresentationPipeline(
        initializer=SparseBinaryInitializer(max_active=int(args.max_terms), seed=int(args.seed)),
        mutator=SparseBinaryMutation(flip_prob=float(args.flip_prob), seed=int(args.seed) + 1),
        repair=SparseBinaryRepair(max_active=int(args.max_terms)),
        encoder=None,
    )
    adapter = JointBeamAdapter(
        beam_width=int(args.beam_width),
        shortlist_size=int(args.shortlist_size),
        expansions_per_state=int(args.expansions_per_state),
        bundle_size=int(args.bundle_size),
        max_candidates=int(args.max_candidates),
        objective1_weight=float(args.objective1_weight),
    )
    solver = EvolutionSolver(
        problem,
        adapter=adapter,
        pop_size=max(16, int(args.beam_width) * 4),
        max_generations=int(args.generations),
        enable_progress_log=bool(args.progress),
        report_interval=max(1, int(args.report_interval)),
    )
    solver.set_representation_pipeline(pipeline)
    return solver, problem


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Standalone symbolic demo: joint bundle + beam search",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--n-train", type=int, default=256)
    p.add_argument("--n-valid", type=int, default=128)
    p.add_argument("--n-candidates", type=int, default=192)
    p.add_argument("--true-terms", type=int, default=6)
    p.add_argument("--noise", type=float, default=0.05)
    p.add_argument("--max-terms", type=int, default=8)
    p.add_argument("--ridge-alpha", type=float, default=1e-3)
    p.add_argument("--generations", type=int, default=25)
    p.add_argument("--beam-width", type=int, default=16)
    p.add_argument("--shortlist-size", type=int, default=64)
    p.add_argument("--expansions-per-state", type=int, default=6)
    p.add_argument("--bundle-size", type=int, default=3)
    p.add_argument("--max-candidates", type=int, default=320)
    p.add_argument("--flip-prob", type=float, default=0.04)
    p.add_argument("--objective1-weight", type=float, default=0.02)
    p.add_argument("--report-interval", type=int, default=5)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--show-top", type=int, default=10)
    p.add_argument("--progress", action="store_true")
    p.add_argument("--csv", type=str, default="")
    p.add_argument("--target-col", type=str, default="ci")
    p.add_argument("--fold-col", type=str, default="test_fold_1")
    p.add_argument("--max-pairwise", type=int, default=64)
    return p


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    solver, problem = build_solver(args)
    result = solver.run(return_dict=True)
    print(
        f"[demo] status={result.get('status')} steps={result.get('steps')} "
        f"elapsed={float(result.get('elapsed_sec', 0.0)):.3f}s"
    )

    best_x = getattr(solver, "best_x", None)
    if best_x is None:
        print("[demo] no best_x available")
        return
    mask = problem.decode_mask(best_x)
    obj = problem.evaluate(problem.encode_mask(mask))
    selected = problem.selected_feature_names(mask, limit=int(args.show_top))
    print(f"[demo] best_rmse_valid={float(obj[0]):.6f} active_terms={int(np.sum(mask))}")
    print("[demo] selected_ops:", ", ".join(selected) if selected else "<none>")


if __name__ == "__main__":
    main()
