"""
MOEA/D as an AlgorithmAdapter (decomposition-based multi-objective optimization).

Design goals (framework-aligned):
- Strategy + state live in the adapter (weights / neighborhood / ideal point / replacement).
- RepresentationPipeline provides operators (mutation/repair/crossover if available).
- Plugins provide engineering capabilities (archive/logging/parallel evaluation) without polluting bases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import warnings

import numpy as np

from .algorithm_adapter import AlgorithmAdapter


@dataclass
class MOEADConfig:
    # number of subproblems (population size)
    population_size: int = 100

    # neighborhood size in weight space
    neighborhood_size: int = 20

    # number of subproblems processed per solver step (<= population_size)
    batch_size: int = 50

    # parent selection: probability to sample parents from neighborhood (else global)
    delta: float = 0.9

    # maximum number of solutions replaced per offspring
    nr: int = 2

    # decomposition method
    decomposition: str = "tchebycheff"  # "tchebycheff" | "weighted_sum"

    # weight generation
    weight_generation: str = "simplex_lattice"  # "simplex_lattice" | "random_dirichlet"
    lattice_h: Optional[int] = None  # if None, chosen automatically
    random_seed: Optional[int] = 0

    # variation
    variation: str = "pipeline"  # "pipeline" | "de"
    de_F: float = 0.5
    de_CR: float = 0.9


class MOEADAdapter(AlgorithmAdapter):
    """MOEA/D adapter for ComposableSolver."""

    # Soft partner contracts (informational; no hard dependency).
    requires_context_keys = {"moead_subproblem", "moead_weight", "moead_neighbor_mode"}
    recommended_plugins = ["ParetoArchivePlugin"]

    def __init__(self, config: Optional[MOEADConfig] = None, name: str = "moead", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or MOEADConfig()
        self._rng = np.random.default_rng(self.cfg.random_seed)

        self._m: int = 0
        self._n: int = 0

        self.weights: Optional[np.ndarray] = None  # (N, M)
        self.neighbors: Optional[np.ndarray] = None  # (N, T)
        self.ideal: Optional[np.ndarray] = None  # (M,)

        self.pop_X: Optional[np.ndarray] = None  # (N, D)
        self.pop_F: Optional[np.ndarray] = None  # (N, M)
        self.pop_V: Optional[np.ndarray] = None  # (N,)

        self._pending_indices: List[int] = []
        self._warned_archive = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def setup(self, solver: Any) -> None:
        self._m = int(getattr(solver, "num_objectives", 1) or 1)
        if self._m < 2:
            raise ValueError("MOEADAdapter requires a multi-objective problem (num_objectives >= 2)")

        self._n = max(2, int(self.cfg.population_size))
        self.weights = self._generate_weights(self._n, self._m)
        self._n = int(self.weights.shape[0])

        t = max(1, min(int(self.cfg.neighborhood_size), self._n))
        self.neighbors = self._compute_neighbors(self.weights, t)
        self.ideal = np.full((self._m,), np.inf, dtype=float)

        # initialize population
        pop = []
        for _ in range(self._n):
            pop.append(np.asarray(solver.init_candidate({"generation": int(getattr(solver, "generation", 0) or 0)})))
        self.pop_X = np.stack(pop, axis=0)

        # evaluate initial population using the solver's evaluation path (plugins may short-circuit)
        F, V = solver.evaluate_population(self.pop_X)
        self.pop_F = np.asarray(F, dtype=float)
        self.pop_V = np.asarray(V, dtype=float).reshape(-1)
        self._update_ideal(self.pop_F)

        # expose current population to solver for context/bias/plugins
        self._sync_solver_population(solver)

        # Optional: warn if user did not attach any archive/recording plugin.
        self._warn_if_no_archive_plugin(solver)

    def teardown(self, solver: Any) -> None:
        return None

    # ------------------------------------------------------------------
    # Adapter API
    # ------------------------------------------------------------------
    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            self.setup(solver)

        assert self.pop_X is not None
        assert self.weights is not None
        assert self.neighbors is not None

        batch = max(1, min(int(self.cfg.batch_size), self._n))
        indices = self._rng.choice(self._n, size=batch, replace=False) if batch < self._n else np.arange(self._n)

        self._pending_indices = [int(i) for i in indices]
        out: List[np.ndarray] = []
        for idx in self._pending_indices:
            ctx = dict(context)
            ctx["moead_subproblem"] = int(idx)
            ctx["moead_weight"] = np.asarray(self.weights[idx], dtype=float)
            ctx["moead_neighbor_mode"] = "neighborhood" if (self._rng.random() < float(self.cfg.delta)) else "global"
            cand = self._variation(solver, idx, ctx)
            cand = solver.repair_candidate(cand, ctx)
            out.append(np.asarray(cand))
        return out

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            return
        if self.weights is None or self.neighbors is None or self.ideal is None:
            return

        cand_X = np.asarray(candidates, dtype=float)
        cand_F = np.asarray(objectives, dtype=float)
        cand_V = np.asarray(violations, dtype=float).reshape(-1)
        if cand_X.ndim == 1:
            cand_X = cand_X.reshape(1, -1)
        if cand_F.ndim == 1:
            cand_F = cand_F.reshape(-1, 1)

        # update ideal point with feasible solutions only (common MOEA/D practice)
        self._update_ideal(cand_F, cand_V)

        # replace in neighborhoods
        for k, i in enumerate(self._pending_indices[: int(cand_X.shape[0])]):
            yx = cand_X[k]
            yf = cand_F[k]
            yv = float(cand_V[k]) if k < cand_V.shape[0] else 0.0

            # choose update set
            mode = "neighborhood"
            try:
                mode = str(context.get("moead_neighbor_mode", "neighborhood"))
            except Exception:
                mode = "neighborhood"
            if mode == "global":
                P = np.arange(self._n, dtype=int)
            else:
                P = np.asarray(self.neighbors[int(i)], dtype=int)

            # random order + limited replacements
            P = np.asarray(P, dtype=int)
            self._rng.shuffle(P)
            replaced = 0
            for j in P:
                if replaced >= int(self.cfg.nr):
                    break
                if self._is_better_for_subproblem(yf, yv, int(j)):
                    self.pop_X[int(j)] = yx
                    self.pop_F[int(j)] = yf
                    self.pop_V[int(j)] = yv
                    replaced += 1

        self._sync_solver_population(solver)

    # ------------------------------------------------------------------
    # Public helpers for plugins
    # ------------------------------------------------------------------
    def get_population(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            return np.zeros((0, 0)), np.zeros((0, 0)), np.zeros((0,))
        return np.asarray(self.pop_X), np.asarray(self.pop_F), np.asarray(self.pop_V)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _warn_if_no_archive_plugin(self, solver: Any) -> None:
        if self._warned_archive:
            return
        pm = getattr(solver, "plugin_manager", None)
        if pm is None or getattr(pm, "list_plugins", None) is None:
            return
        plugins = pm.list_plugins(enabled_only=False)
        names = [getattr(p, "name", "") for p in plugins]
        if not any("archive" in str(n).lower() for n in names):
            warnings.warn(
                "MOEADAdapter 未检测到 archive 类插件。MOEA/D 内部维护的是分解子问题解集；"
                "如需输出 Pareto 前沿，建议添加 ParetoArchivePlugin（能力层，不污染底座）。",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_archive = True

    def _sync_solver_population(self, solver: Any) -> None:
        try:
            solver.population = np.asarray(self.pop_X, dtype=float) if self.pop_X is not None else None
            solver.objectives = np.asarray(self.pop_F, dtype=float) if self.pop_F is not None else None
            solver.constraint_violations = np.asarray(self.pop_V, dtype=float) if self.pop_V is not None else None
        except Exception:
            pass

    def _variation(self, solver: Any, idx: int, ctx: Dict[str, Any]) -> np.ndarray:
        if self.pop_X is None or self.neighbors is None:
            return np.asarray(solver.init_candidate(ctx))

        mode = str(ctx.get("moead_neighbor_mode", "neighborhood"))
        if mode == "global":
            pool = np.arange(self._n, dtype=int)
        else:
            pool = np.asarray(self.neighbors[idx], dtype=int)

        if str(self.cfg.variation).lower().strip() == "de":
            return self._de_variation(idx, pool)

        # pipeline variation fallback: mutate the current solution
        base = np.asarray(self.pop_X[idx])
        return np.asarray(solver.mutate_candidate(base, ctx))

    def _de_variation(self, idx: int, pool: np.ndarray) -> np.ndarray:
        # Differential Evolution style operator (continuous).
        # Uses x_r1 + F*(x_r2-x_r3) and binomial crossover with x_i.
        assert self.pop_X is not None
        x_i = np.asarray(self.pop_X[idx], dtype=float)

        pool = np.asarray(pool, dtype=int).reshape(-1)
        if pool.size < 3:
            pool = np.arange(self._n, dtype=int)
        r = self._rng.choice(pool, size=3, replace=False) if pool.size >= 3 else self._rng.choice(self._n, size=3, replace=False)
        r1, r2, r3 = int(r[0]), int(r[1]), int(r[2])
        x1 = np.asarray(self.pop_X[r1], dtype=float)
        x2 = np.asarray(self.pop_X[r2], dtype=float)
        x3 = np.asarray(self.pop_X[r3], dtype=float)

        F = float(self.cfg.de_F)
        CR = float(self.cfg.de_CR)
        v = x1 + F * (x2 - x3)

        # binomial crossover
        u = x_i.copy()
        j_rand = int(self._rng.integers(0, u.size))
        mask = self._rng.random(u.size) < CR
        mask[j_rand] = True
        u[mask] = v[mask]
        return u

    def _update_ideal(self, F: np.ndarray, V: Optional[np.ndarray] = None) -> None:
        if self.ideal is None:
            return
        obj = np.asarray(F, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        if V is None:
            self.ideal = np.minimum(self.ideal, np.min(obj, axis=0))
            return
        vio = np.asarray(V, dtype=float).reshape(-1)
        feasible = (vio <= 0.0)
        if np.any(feasible):
            self.ideal = np.minimum(self.ideal, np.min(obj[feasible], axis=0))

    def _is_better_for_subproblem(self, y_f: np.ndarray, y_v: float, j: int) -> bool:
        assert self.pop_F is not None and self.pop_V is not None and self.weights is not None and self.ideal is not None

        x_f = np.asarray(self.pop_F[j], dtype=float)
        x_v = float(self.pop_V[j])

        # feasibility first
        if (y_v <= 0.0) and (x_v > 0.0):
            return True
        if (y_v > 0.0) and (x_v <= 0.0):
            return False
        if (y_v > 0.0) and (x_v > 0.0):
            return y_v < x_v

        w = np.asarray(self.weights[j], dtype=float)
        return self._g(y_f, w) <= self._g(x_f, w)

    def _g(self, f: np.ndarray, w: np.ndarray) -> float:
        f = np.asarray(f, dtype=float).reshape(-1)
        w = np.asarray(w, dtype=float).reshape(-1)
        if str(self.cfg.decomposition).lower().strip() == "weighted_sum":
            return float(np.sum(w * f))
        # tchebycheff (default)
        assert self.ideal is not None
        return float(np.max(w * np.abs(f - self.ideal)))

    def _generate_weights(self, n: int, m: int) -> np.ndarray:
        mode = str(self.cfg.weight_generation).lower().strip()
        if mode == "random_dirichlet":
            W = self._rng.random((n, m))
            W = W / np.sum(W, axis=1, keepdims=True)
            return W
        # simplex lattice (uniform-ish)
        H = int(self.cfg.lattice_h) if self.cfg.lattice_h is not None else self._auto_lattice_h(n, m)
        W = self._simplex_lattice(m=m, H=H)
        # If too many, downsample; if too few, pad with dirichlet.
        if W.shape[0] > n:
            idx = self._rng.choice(W.shape[0], size=n, replace=False)
            W = W[idx]
        elif W.shape[0] < n:
            extra = n - W.shape[0]
            E = self._rng.random((extra, m))
            E = E / np.sum(E, axis=1, keepdims=True)
            W = np.vstack([W, E])
        return W

    @staticmethod
    def _auto_lattice_h(n: int, m: int) -> int:
        # Find smallest H such that C(H+m-1, m-1) >= n
        H = 1
        while True:
            if MOEADAdapter._n_simplex_lattice(m, H) >= n:
                return H
            H += 1

    @staticmethod
    def _n_simplex_lattice(m: int, H: int) -> int:
        # combinations with repetition: C(H+m-1, m-1)
        from math import comb
        return int(comb(H + m - 1, m - 1))

    @staticmethod
    def _simplex_lattice(m: int, H: int) -> np.ndarray:
        # Generate all integer vectors (h1..hm) s.t. sum=H, then normalize by H.
        out: List[List[float]] = []

        def rec(prefix: List[int], remaining: int, dim: int) -> None:
            if dim == m - 1:
                out.append([*(prefix), remaining])
                return
            for v in range(remaining + 1):
                rec([*(prefix), v], remaining - v, dim + 1)

        rec([], H, 0)
        W = np.asarray(out, dtype=float)
        if H > 0:
            W = W / float(H)
        # avoid exact zeros causing numerical issues in tchebycheff
        eps = 1e-12
        W = np.clip(W, eps, None)
        W = W / np.sum(W, axis=1, keepdims=True)
        return W

    @staticmethod
    def _compute_neighbors(W: np.ndarray, T: int) -> np.ndarray:
        W = np.asarray(W, dtype=float)
        # pairwise distances in weight space
        # (N,N) but N is usually moderate; keep simple to avoid extra deps
        diff = W[:, None, :] - W[None, :, :]
        dist = np.sqrt(np.sum(diff * diff, axis=2))
        idx = np.argsort(dist, axis=1)[:, :T]
        return np.asarray(idx, dtype=int)

