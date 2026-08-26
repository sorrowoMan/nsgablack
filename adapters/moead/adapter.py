"""
MOEA/D as an AlgorithmAdapter (decomposition-based multi-objective optimization).

Design goals (framework-aligned):
- Strategy + state live in the adapter (weights / neighborhood / ideal point / replacement).
- RepresentationPipeline provides operators (mutation/repair/crossover if available).
- Plugins provide engineering capabilities (archive/logging/parallel evaluation) without polluting bases.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import warnings

import numpy as np

from blackbase.contracts import BatchDisposition

from ..algorithm_adapter import AlgorithmAdapter
from blackbase.context.context_keys import (
    KEY_MOEAD_NEIGHBOR_MODE,
    KEY_MOEAD_SUBPROBLEM,
    KEY_MOEAD_WEIGHT,
)


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
    context_requires = ("generation",)
    context_provides = (
        KEY_MOEAD_SUBPROBLEM,
        KEY_MOEAD_WEIGHT,
        KEY_MOEAD_NEIGHBOR_MODE,
    )
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "MOEA/D writes decomposition subproblem metadata into context for variation/repair plugins.",
    )
    state_recovery_level = "L2"
    population_state_mode = "single"
    state_recovery_notes = (
        "Restores decomposition population (pop_X/pop_F/pop_V), ideal point, weights and neighborhood. "
        "get_state()/set_state() cover scalar parameters; "
        "get_population_snapshot()/set_population_snapshot() handle the full solution array."
    )

    # Soft partner contracts (informational; no hard dependency).
    recommended_plugins = ["ParetoArchivePlugin"]

    def __init__(
        self,
        config: Optional[MOEADConfig] = None,
        name: str = "moead",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=MOEADConfig,
            config_kwargs=config_kwargs,
            adapter_name="MOEADAdapter",
        )
        self.cfg = self.config
        self._rng = np.random.default_rng(self.cfg.random_seed)

        self._m: int = 0
        self._n: int = 0

        self.weights: Optional[np.ndarray] = None  # (N, M)
        self.neighbors: Optional[np.ndarray] = None  # (N, T)
        self.ideal: Optional[np.ndarray] = None  # (M,)

        self.pop_X: Optional[np.ndarray] = None  # (N, D)
        self.pop_F: Optional[np.ndarray] = None  # (N, M)
        self.pop_V: Optional[np.ndarray] = None  # (N,)
        self._population_candidate_tokens: tuple[str | None, ...] = ()

        self._pending_indices: List[int] = []
        self._pending_modes: List[str] = []
        self._warned_archive = False
        self._last_context_projection: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def setup(self, control: Any) -> None:
        self._population_candidate_tokens = ()
        missing = [
            name
            for name in ("init_candidate", "evaluate_population")
            if not callable(getattr(control, name, None))
        ]
        if missing:
            raise TypeError(
                "MOEADAdapter requires a composable solver control surface; "
                f"missing: {', '.join(missing)}"
            )
        # MOEA/D is intended for composable/blank solver runtimes.
        # On EvolutionSolver, NSGA2 methods exist but are unused when MOEAD is set.
        import warnings
        if hasattr(control, "selection") and hasattr(control, "environmental_selection"):
            warnings.warn(
                "MOEADAdapter on EvolutionSolver: NSGA2 selection present but unused. "
                "Use ComposableSolver for lighter runtime.",
                RuntimeWarning, stacklevel=2,
            )

        self._m = int(getattr(control, "num_objectives", 1) or 1)
        if self._m < 2:
            raise ValueError("MOEADAdapter requires a multi-objective problem (num_objectives >= 2)")

        requested_population_size = max(2, int(self.cfg.population_size))
        allowance = getattr(control, "evaluation_batch_allowance", None)
        if callable(allowance):
            self._n = int(allowance(requested_population_size))
        else:
            self._n = requested_population_size
        if self._n < 2:
            self._n = 0
            self.weights = np.empty((0, self._m), dtype=float)
            self.neighbors = np.empty((0, 0), dtype=int)
            self.ideal = np.full((self._m,), np.inf, dtype=float)
            self.pop_X = np.empty((0, int(getattr(control, "dimension", 0) or 0)), dtype=float)
            self.pop_F = np.empty((0, self._m), dtype=float)
            self.pop_V = np.empty((0,), dtype=float)
            self._population_candidate_tokens = ()
            self._pending_indices = []
            self._pending_modes = []
            request_stop = getattr(control, "request_stop", None)
            if callable(request_stop):
                request_stop()
            self._refresh_runtime_projection()
            return
        self.weights = self._generate_weights(self._n, self._m)
        self._n = int(self.weights.shape[0])

        t = max(1, min(int(self.cfg.neighborhood_size), self._n))
        self.neighbors = self._compute_neighbors(self.weights, t)
        self.ideal = np.full((self._m,), np.inf, dtype=float)

        # initialize population
        pop = []
        for _ in range(self._n):
            pop.append(control.init_candidate({"generation": int(getattr(control, "generation", 0) or 0)}))
        self._population_candidate_tokens = self.candidate_tokens_for(control, pop)
        self.pop_X = np.stack(pop, axis=0)
        provenance_getter = getattr(control, "candidate_provenance_for", None)
        provenance_binder = getattr(control, "bind_candidate_provenance", None)
        if callable(provenance_getter) and callable(provenance_binder):
            records = tuple(provenance_getter(candidate) for candidate in pop)
            if all(record is not None for record in records):
                provenance_binder(self.pop_X, records, activate=True)

        # evaluate initial population using the solver's evaluation path (plugins may short-circuit)
        F, V = control.evaluate_population(self.pop_X)
        self.pop_F = np.asarray(F, dtype=float)
        self.pop_V = np.asarray(V, dtype=float).reshape(-1)
        self._update_ideal(self.pop_F)
        self._pending_indices = []
        self._pending_modes = []
        self._refresh_runtime_projection()
        self._sync_population_snapshot(control)

        # Optional: warn if user did not attach any archive/recording plugin.
        self._warn_if_no_archive_plugin(control)

    def teardown(self, control: Any) -> None:
        return None

    # ------------------------------------------------------------------
    # Adapter API
    # ------------------------------------------------------------------
    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            self.setup(control)

        assert self.pop_X is not None
        assert self.weights is not None
        assert self.neighbors is not None

        batch = max(1, min(int(self.cfg.batch_size), self._n))
        indices = self._rng.choice(self._n, size=batch, replace=False) if batch < self._n else np.arange(self._n)

        self._pending_indices = [int(i) for i in indices]
        self._pending_modes = []
        out: List[np.ndarray] = []
        for idx in self._pending_indices:
            ctx = dict(context)
            mode = "neighborhood" if (self._rng.random() < float(self.cfg.delta)) else "global"
            self._pending_modes.append(str(mode))
            ctx[KEY_MOEAD_SUBPROBLEM] = int(idx)
            ctx[KEY_MOEAD_WEIGHT] = np.asarray(self.weights[idx], dtype=float)
            ctx[KEY_MOEAD_NEIGHBOR_MODE] = mode
            cand = self._variation(control, idx, ctx)
            cand = control.repair_candidate(cand, ctx)
            out.append(np.asarray(cand))
        self._refresh_runtime_projection()
        return out

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        del control, context
        pending_count = len(self._pending_indices)
        if disposition.proposed_count != pending_count:
            raise ValueError(
                "MOEA/D proposal disposition does not match pending subproblems: "
                f"proposed_count={disposition.proposed_count}, "
                f"pending_count={pending_count}"
            )
        if len(self._pending_modes) != pending_count:
            raise ValueError(
                "MOEA/D pending subproblem indices and modes must have the same length"
            )
        accepted = disposition.accepted_indices
        self._pending_indices = [self._pending_indices[index] for index in accepted]
        self._pending_modes = [self._pending_modes[index] for index in accepted]
        self._refresh_runtime_projection()

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            raise RuntimeError("MOEA/D.update requires population state created by propose()")
        if self.weights is None or self.neighbors is None or self.ideal is None:
            raise RuntimeError("MOEA/D.update requires decomposition state created by propose()")

        cand_X = np.asarray(candidates, dtype=float)
        cand_F = np.asarray(objectives, dtype=float)
        cand_V = np.asarray(violations, dtype=float).reshape(-1)
        candidate_tokens = self.candidate_tokens_for(control, candidates)
        if cand_X.ndim == 1:
            cand_X = cand_X.reshape(1, -1)
        if cand_F.ndim == 1:
            cand_F = cand_F.reshape(-1, 1)
        candidate_count = int(cand_X.shape[0])
        if cand_F.shape[0] != candidate_count or cand_V.shape[0] != candidate_count:
            raise ValueError("MOEA/D candidate, objective, and violation counts must match")
        if len(self._pending_indices) != candidate_count:
            raise ValueError("MOEA/D feedback must align with pending subproblem indices")
        if len(self._pending_modes) != candidate_count:
            raise ValueError("MOEA/D feedback must align with pending neighbor modes")

        # update ideal point with feasible solutions only (common MOEA/D practice)
        self._update_ideal(cand_F, cand_V)

        # replace in neighborhoods
        for k, i in enumerate(self._pending_indices):
            yx = cand_X[k]
            yf = cand_F[k]
            yv = float(cand_V[k])

            # choose update set
            mode = str(self._pending_modes[k])
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
                    tokens = list(self._population_candidate_tokens)
                    if len(tokens) != int(self.pop_X.shape[0]):
                        tokens = [None] * int(self.pop_X.shape[0])
                    tokens[int(j)] = candidate_tokens[k]
                    self._population_candidate_tokens = tuple(tokens)
                    replaced += 1

        self._refresh_runtime_projection()
        self._sync_population_snapshot(control)

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._last_context_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {str(k): source for k in self._last_context_projection.keys()}

    # ------------------------------------------------------------------
    # Checkpoint / state recovery (L2 contract)
    # ------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        """Return serialisable scalar adapter state (scalar fields + ideal point).

        For the full population array use ``get_population_snapshot()`` in addition.
        Combined, these two calls fulfil the L2 checkpoint contract.
        """
        return {
            "_m": int(self._m),
            "_n": int(self._n),
            "ideal": None if self.ideal is None else self.ideal.tolist(),
            "weights": None if self.weights is None else self.weights.tolist(),
            "neighbors": None if self.neighbors is None else self.neighbors.tolist(),
            "candidate_tokens": list(self._population_candidate_tokens),
            "pending_indices": list(self._pending_indices),
            "pending_modes": list(self._pending_modes),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        """Restore scalar adapter state from a checkpoint.

        The solution arrays (pop_X/F/V) must be restored separately via
        ``set_population_snapshot()`` to keep array ownership consistent.
        """
        if not state:
            return
        self._m = int(state.get("_m") or self._m)
        self._n = int(state.get("_n") or self._n)
        ideal = state.get("ideal")
        self.ideal = None if ideal is None else np.asarray(ideal, dtype=float)
        weights = state.get("weights")
        self.weights = None if weights is None else np.asarray(weights, dtype=float)
        neighbors = state.get("neighbors")
        self.neighbors = None if neighbors is None else np.asarray(neighbors, dtype=int)
        self._population_candidate_tokens = tuple(state.get("candidate_tokens", ()) or ())
        self._pending_indices = [
            int(index) for index in tuple(state.get("pending_indices", ()) or ())
        ]
        self._pending_modes = [
            str(mode) for mode in tuple(state.get("pending_modes", ()) or ())
        ]
        if len(self._pending_indices) != len(self._pending_modes):
            raise ValueError("MOEA/D checkpoint proposal bookkeeping is misaligned")
        rng_state = state.get("rng_state")
        if isinstance(rng_state, Mapping):
            self._rng.bit_generator.state = copy.deepcopy(dict(rng_state))

    def snapshot_step_state(self) -> Mapping[str, Any]:
        return {
            "schema": "nsgablack.moead_step_transaction/v1",
            "adapter_state": super().snapshot_step_state(),
            "population": None if self.pop_X is None else np.array(self.pop_X, copy=True),
            "objectives": None if self.pop_F is None else np.array(self.pop_F, copy=True),
            "violations": None if self.pop_V is None else np.array(self.pop_V, copy=True),
            "runtime_projection": copy.deepcopy(self._last_context_projection),
        }

    def restore_step_state(self, state: Mapping[str, Any]) -> None:
        if str(state.get("schema", "")) != "nsgablack.moead_step_transaction/v1":
            raise ValueError("unsupported MOEADAdapter step transaction schema")
        adapter_state = state.get("adapter_state")
        if not isinstance(adapter_state, Mapping):
            raise TypeError("MOEADAdapter transaction state is invalid")
        self.set_state(dict(adapter_state))
        population = state.get("population")
        objectives = state.get("objectives")
        violations = state.get("violations")
        if population is None or objectives is None or violations is None:
            if not (population is None and objectives is None and violations is None):
                raise ValueError("MOEA/D transaction population is incomplete")
            self.pop_X = None
            self.pop_F = None
            self.pop_V = None
        else:
            x_arr, f_arr, v_arr = self.validate_population_snapshot(
                population,
                objectives,
                violations,
            )
            self.pop_X = x_arr
            self.pop_F = f_arr
            self.pop_V = v_arr
            if len(self._population_candidate_tokens) not in {0, int(x_arr.shape[0])}:
                raise ValueError("MOEA/D transaction tokens do not align with population")
            if not self._population_candidate_tokens:
                self._population_candidate_tokens = (None,) * int(x_arr.shape[0])
        self._last_context_projection = copy.deepcopy(
            dict(state.get("runtime_projection", {}) or {})
        )

    # ------------------------------------------------------------------
    # Public helpers for plugins
    # ------------------------------------------------------------------
    def get_population_snapshot(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            return np.zeros((0, 0)), np.zeros((0, 0)), np.zeros((0,))
        return np.asarray(self.pop_X), np.asarray(self.pop_F), np.asarray(self.pop_V)

    def get_population_candidate_tokens(self) -> tuple[str | None, ...] | None:
        if self.pop_X is None:
            return ()
        if len(self._population_candidate_tokens) != int(self.pop_X.shape[0]):
            return None
        return tuple(self._population_candidate_tokens)

    def set_population_candidate_tokens(
        self,
        candidate_tokens: Sequence[str | None],
    ) -> bool:
        tokens = tuple(candidate_tokens)
        expected = 0 if self.pop_X is None else int(self.pop_X.shape[0])
        if len(tokens) != expected:
            raise ValueError("MOEA/D population tokens must align with population rows")
        self._population_candidate_tokens = tokens
        return True

    def set_population_snapshot(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> bool:
        """Write back population snapshot from plugins (context-first path).

        When the adapter has not yet been initialised via ``setup()`` (i.e.
        ``_n == 0`` and ``_m == 0``), the incoming arrays are accepted as the
        bootstrap state and the dimension metadata is inferred from them.
        """
        try:
            x_arr, f_arr, v_arr = self.validate_population_snapshot(population, objectives, violations)
        except Exception:
            return False

        n = int(x_arr.shape[0]) if x_arr.ndim >= 2 else 0
        m = int(f_arr.shape[1]) if f_arr.ndim >= 2 else 0

        # If adapter is already initialised, enforce strict shape agreement.
        if self._n > 0 and n not in (0, self._n):
            return False
        if f_arr.shape[0] != n or v_arr.shape[0] != n:
            return False
        if self._m > 0 and n > 0 and m != int(self._m):
            return False

        preserve_tokens = (
            self.pop_X is not None
            and np.asarray(self.pop_X).shape == x_arr.shape
            and np.array_equal(self.pop_X, x_arr, equal_nan=True)
            and len(self._population_candidate_tokens) == int(x_arr.shape[0])
        )
        self.pop_X = x_arr
        self.pop_F = f_arr
        self.pop_V = v_arr
        if not preserve_tokens:
            self._population_candidate_tokens = (None,) * int(x_arr.shape[0])

        # Bootstrap dimension metadata from incoming data when uninitialised.
        if self._m == 0 and m > 0:
            self._m = m
        if self._n == 0 and n > 0:
            self._n = n

        if n > 0:
            self._recompute_ideal()
        self._refresh_runtime_projection()
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _warn_if_no_archive_plugin(self, control: Any) -> None:
        if self._warned_archive:
            return
        pm = getattr(control, "plugin_manager", None)
        if pm is None or getattr(pm, "list_plugins", None) is None:
            return
        plugins = pm.list_plugins(enabled_only=False)
        names = [getattr(p, "name", "") for p in plugins]
        if not any("archive" in str(n).lower() for n in names):
            warnings.warn(
                "MOEADAdapter did not detect an archive plugin. "
                "MOEA/D internally keeps decomposition subproblem solutions; "
                "attach ParetoArchivePlugin if explicit Pareto-front output is needed.",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_archive = True

    def _refresh_runtime_projection(self) -> None:
        projection = dict(self._last_context_projection)
        if self._pending_indices and self.weights is not None:
            batch_indices = np.asarray(self._pending_indices, dtype=int)
            projection[KEY_MOEAD_SUBPROBLEM] = batch_indices
            projection[KEY_MOEAD_WEIGHT] = np.asarray(self.weights[batch_indices], dtype=float)
            projection[KEY_MOEAD_NEIGHBOR_MODE] = list(self._pending_modes)
        self._last_context_projection = projection

    def _sync_population_snapshot(self, control: Any) -> None:
        writer = getattr(control, "write_population_snapshot", None)
        if not callable(writer):
            return
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            return
        try:
            writer(self.pop_X, self.pop_F, self.pop_V)
        except Exception:
            return

    def _recompute_ideal(self) -> None:
        if self.pop_F is None or self.pop_F.size == 0:
            self.ideal = None
            return
        if self.pop_V is None or self.pop_V.size == 0:
            self.ideal = np.min(np.asarray(self.pop_F, dtype=float), axis=0)
            return
        feasible = np.asarray(self.pop_V, dtype=float).reshape(-1) <= 0.0
        if np.any(feasible):
            self.ideal = np.min(np.asarray(self.pop_F, dtype=float)[feasible], axis=0)
        else:
            self.ideal = np.min(np.asarray(self.pop_F, dtype=float), axis=0)

    def _variation(self, control: Any, idx: int, ctx: Dict[str, Any]) -> np.ndarray:
        if self.pop_X is None or self.neighbors is None:
            return np.asarray(control.init_candidate(ctx))

        mode = str(ctx.get(KEY_MOEAD_NEIGHBOR_MODE, "neighborhood"))
        if mode == "global":
            pool = np.arange(self._n, dtype=int)
        else:
            pool = np.asarray(self.neighbors[idx], dtype=int)

        if str(self.cfg.variation).lower().strip() == "de":
            return self._de_variation(idx, pool)

        # pipeline variation fallback: mutate the current solution
        base = np.asarray(self.pop_X[idx])
        return np.asarray(control.mutate_candidate(base, ctx))

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
        return self._g(y_f, w) < self._g(x_f, w)

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
