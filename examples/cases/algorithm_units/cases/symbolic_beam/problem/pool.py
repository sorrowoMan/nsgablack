"""符号特征池、目标与领域计算工具。"""
from __future__ import annotations
from typing import Any, Dict, Iterable, Sequence
import numpy as np
from dataclasses import dataclass
import pandas as pd
from nsgablack.core.base import BlackBoxProblem

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



def build_problem(args):
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
    return problem
