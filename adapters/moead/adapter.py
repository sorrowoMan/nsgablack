"""
MOEA/D as an AlgorithmAdapter (decomposition-based multi-objective optimization).

Design goals (framework-aligned):
- Strategy + state live in the adapter (weights / neighborhood / ideal point / replacement).
- Search operations may be directly assembled; the legacy Pipeline mutation path remains supported.
- Plugins provide engineering capabilities (archive/logging/parallel evaluation) without polluting bases.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import warnings

import numpy as np

from blackbase.contracts import BatchDisposition

from ..unit_backed import UnitBackedAdapter, UnitField
from ...representation.structure_builders import DecompositionUnitBuilder
from ...representation.structure_builders import simplex_points
from ..algorithm_adapter import AlgorithmAdapter
from ..selection import SelectionRequest
from ..change import ChangeRequest
from ..population_pool_refs import (feedback_pool_bindings, align_pool_bindings, validate_pool_bindings,
                                   install_population_state, validate_numeric_population_replacement)
from ..subpools import adapter_path
from ...core.state.pool_views import ObjectiveProjection
from nsgablack.context_keys import (
    KEY_MOEAD_NEIGHBOR_MODE,
    KEY_MOEAD_SUBPROBLEM,
    KEY_MOEAD_WEIGHT,
    KEY_SOLUTION_INPUT_REF,
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

    # Positive per-objective comparison scales. Raw feedback and ideal points
    # retain their Problem units; direction views publish the same w / scale.
    objective_scales: Optional[tuple[float, ...]] = None

    # weight generation
    weight_generation: str = "simplex_lattice"  # "simplex_lattice" | "random_dirichlet"
    lattice_h: Optional[int] = None  # if None, chosen automatically
    random_seed: Optional[int] = 0

    # variation
    variation: str = "pipeline"  # "pipeline" | "de"
    de_F: float = 0.5
    de_CR: float = 0.9


class MOEADAdapter(UnitBackedAdapter):
    """MOEA/D adapter for ComposableSolver."""
    pool_input_modes = ("initialize", "compete")
    publishes_projection_subpools = True
    operation_methods = {"initializer": "initialize", "mutator": "mutate", "change": "change",
                         "selector": "select", "repair": "repair", "pool_maintenance": "maintain"}
    unit_build_operations = ("initialize", "decomposition")
    # Repaired trial values keep their subproblem and neighborhood identities;
    # update consumes fresh feedback, with no trial-derived path cost to retain.
    accepts_proposal_replacement = True
    unit_builder_type = DecompositionUnitBuilder
    unit_schema = DecompositionUnitBuilder.unit_type.schema
    pop_X = UnitField("population")
    pop_F = UnitField("objectives")
    pop_V = UnitField("violations")
    _population_candidate_tokens = UnitField("candidate_tokens")
    weights = UnitField("weights")
    neighbors = UnitField("neighbors")
    ideal = UnitField("ideal")
    _pending_indices = UnitField("pending_indices")
    _pending_modes = UnitField("pending_modes")
    admission_unit_fields = ("pending_indices", "pending_modes")

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
        *,
        initializer=None,
        mutator=None,
        change=None,
        pool_maintenance=None,
        selector=None,
        repair=None,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
        self.config = self.resolve_config(
            config=config,
            config_cls=MOEADConfig,
            config_kwargs=config_kwargs,
            adapter_name="MOEADAdapter",
        )
        self.cfg = self.config
        self.cfg.objective_scales = self._validated_objective_scales()
        self.set_pool_maintenance(pool_maintenance)
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
        self._population_pool_bindings = ()
        self._initialization_target = None
        self._initialization_proposed_count = None

        self._pending_indices: List[int] = []
        self._pending_modes: List[str] = []
        self._warned_archive = False
        self._last_context_projection: Dict[str, Any] = {}
        self.set_initializer(initializer)
        self.set_mutator(mutator)
        self.set_change(change)
        self.set_selector(selector)
        self.set_repair(repair)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def setup(self, control: Any) -> None:
        self.reset_unit()
        self._population_pool_bindings = ()
        self._initialization_target = None
        self._initialization_proposed_count = None
        missing = [
            name
            for name in ("init_population",)
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
        self._comparison_weights(np.ones(self._m))

        # Candidate intake belongs to the first dispatched task. Setup cannot
        # know its pool selection, repair context, budget or admission policy.
        self._n = max(2, int(self.cfg.population_size))
        self._pending_indices = []
        self._pending_modes = []
        self._last_context_projection = {}
        self.seed_operator_bindings(self._rng)
        self._refresh_runtime_projection()

        # Optional: warn if user did not attach any archive/recording plugin.
        self._warn_if_no_archive_plugin(control)

    def teardown(self, control: Any) -> None:
        return None

    def default_pool_input_count(self):
        return max(2, int(self.cfg.population_size))

    @property
    def pool_views_ready(self):
        """Whether this owner has completed its accepted bootstrap population."""
        return (self.weights is not None and self.pop_X is not None and len(self.pop_X) == self._n
                and len(self._population_pool_bindings) == self._n
                and bool(self._population_pool_bindings) and all(self._population_pool_bindings))

    # ------------------------------------------------------------------
    # Adapter API
    # ------------------------------------------------------------------
    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self._m == 0:
            self.setup(control)

        input_ref = context.get(KEY_SOLUTION_INPUT_REF)
        if self.weights is None:
            return self.initiate(control, context)

        assert self.pop_X is not None
        assert self.weights is not None
        assert self.neighbors is not None
        self.ensure_unit().require_current_feedback()

        if input_ref is not None and control.solution_pool.input_remaining(input_ref):
            candidates = self.init_population(control, control.solution_pool.input_remaining(input_ref), context)
            # External refinements compete against the current decomposition,
            # using each destination's own weight and the ordinary nr limit.
            self._pending_indices = [0] * len(candidates)
            self._pending_modes = ["global"] * len(candidates)
            return (tuple(self.semantic_proposal(control, candidate) for candidate in candidates)
                    if self._operator_bindings() else candidates)

        self._pending_indices = list(self.chose(context))
        self._pending_modes = []
        out: List[np.ndarray] = []
        for idx in self._pending_indices:
            ctx = dict(context)
            mode = "neighborhood" if (self._rng.random() < float(self.cfg.delta)) else "global"
            self._pending_modes.append(str(mode))
            ctx[KEY_MOEAD_SUBPROBLEM] = int(idx)
            ctx[KEY_MOEAD_WEIGHT] = np.asarray(self.weights[idx], dtype=float)
            ctx[KEY_MOEAD_NEIGHBOR_MODE] = mode
            cand = self.change(control, idx, ctx)
            out.append(self.semantic_proposal(control, cand)
                       if self.get_bound_mutator() is not None or self.get_bound_change() is not None
                       else np.asarray(cand))
        self._refresh_runtime_projection()
        return out

    def initiate(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        """Request only the missing bootstrap rows; ordinary admission owns feedback."""
        input_ref = context.get(KEY_SOLUTION_INPUT_REF)
        remaining = None if input_ref is None else control.solution_pool.input_remaining(input_ref)
        if self._initialization_target is None:
            self._initialization_target = self._n if remaining is None else min(self._n, remaining)
            if self._initialization_target < 2:
                raise ValueError("MOEA/D initialization requires at least two selected pool candidates")
        have = 0 if self.pop_X is None else len(self.pop_X)
        needed = self._initialization_target - have
        if remaining is not None and remaining < needed:
            raise ValueError("MOEA/D initialization input ended before its declared intake completed")
        candidates = self.init_population(control, needed, context)
        self._initialization_proposed_count = len(candidates)
        self._pending_indices, self._pending_modes = [], []
        return (tuple(self.semantic_proposal(control, candidate) for candidate in candidates)
                if self._operator_bindings() else candidates)

    def chose(self, context: Dict[str, Any]) -> Tuple[int, ...]:
        """Choose directions for this attempt, without changing their slot identities."""
        del context
        batch = max(1, min(int(self.cfg.batch_size), self._n))
        indices = self._rng.choice(self._n, size=batch, replace=False) if batch < self._n else np.arange(self._n)
        return tuple(int(index) for index in indices)

    def _proposal_contexts(self, proposed_count, context):
        if self._initialization_proposed_count is not None:
            return [dict(context) for _ in range(proposed_count)]
        out = []
        for index, mode in zip(self._pending_indices, self._pending_modes):
            ctx = dict(context)
            ctx[KEY_MOEAD_SUBPROBLEM] = index
            ctx[KEY_MOEAD_WEIGHT] = np.array(self.weights[index], copy=True)
            ctx[KEY_MOEAD_NEIGHBOR_MODE] = mode
            out.append(ctx)
        return out

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        del control, context
        if self._initialization_proposed_count is not None:
            if disposition.proposed_count != self._initialization_proposed_count:
                raise ValueError("MOEA/D initialization disposition does not align with proposals")
            self._initialization_proposed_count = len(disposition.accepted_indices)
            return
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
        self.return_feedback(control, candidates, feedback, context)
        from ..pool_maintenance import run_pool_maintenance
        run_pool_maintenance(self, control, candidates, feedback, context, rng=self._rng)

    def return_feedback(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        """Consume admitted feedback using the current ideal, directions and nr limit."""
        objectives, violations = feedback
        if self._initialization_proposed_count is not None:
            self._update_initialization(control, candidates, feedback, context)
            return
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            raise RuntimeError("MOEA/D.update requires population state created by propose()")
        if self.weights is None or self.neighbors is None or self.ideal is None:
            raise RuntimeError("MOEA/D.update requires decomposition state created by propose()")

        cand_X = np.asarray(candidates, dtype=float)
        cand_F = np.asarray(objectives, dtype=float)
        cand_V = np.asarray(violations, dtype=float).reshape(-1)
        candidate_tokens = self.candidate_tokens_for(control, candidates)
        member_inputs = self.member_inputs_for(control, candidates)
        incoming_bindings = feedback_pool_bindings(control, candidates, feedback, candidate_tokens,
            candidate_metadata=member_inputs["candidate_metadata"])
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
        self.ensure_unit().require_current_feedback()

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
            P = np.array(P, dtype=int, copy=True)
            self._rng.shuffle(P)
            replacements = []
            for j in P:
                if len(replacements) >= int(self.cfg.nr):
                    break
                if int(j) not in replacements and self._is_better_for_subproblem(
                        yf, yv, int(j), trial_candidate=yx, context=context):
                    replacements.append(int(j))
            if replacements:
                count = len(replacements)
                change = self.ensure_unit().replace_evaluated_rows(
                    replacements, np.repeat(yx[None, :], count, axis=0),
                    np.repeat(yf[None, :], count, axis=0), np.full(count, yv),
                    candidate_tokens=(candidate_tokens[k],) * count,
                    **{name: (rows[k],) * count for name, rows in member_inputs.items()},
                )
                self._population_pool_bindings = align_pool_bindings(
                    self._population_pool_bindings, (incoming_bindings[k],) * count, change)

        self._refresh_runtime_projection()
        self._sync_population_snapshot(control)

    def _update_initialization(self, control, candidates, feedback, context):
        if len(candidates) != self._initialization_proposed_count:
            raise ValueError("MOEA/D initialization feedback does not align with admitted candidates")
        if not len(candidates):
            return
        objectives, violations = feedback
        x, f, v = np.asarray(candidates, dtype=float), np.asarray(objectives, dtype=float), np.asarray(violations, dtype=float)
        if f.ndim == 1:
            f = f.reshape(-1, 1)
        tokens = self.candidate_tokens_for(control, candidates)
        member_inputs = self.member_inputs_for(control, candidates)
        incoming = feedback_pool_bindings(control, candidates, feedback, tokens,
            candidate_metadata=member_inputs["candidate_metadata"])
        if self.pop_X is None or len(self.pop_X) == 0:
            change = self.ensure_unit().initialize_population(x, f, v, candidate_tokens=tokens, **member_inputs)
        else:
            change = self.ensure_unit().apply_selection(np.arange(len(self.pop_X) + len(x)),
                x, f, v, candidate_tokens=tokens, **member_inputs)
        self._population_pool_bindings = align_pool_bindings(self._population_pool_bindings, incoming, change)
        self._initialization_proposed_count = None
        if len(self.pop_X) == self._initialization_target:
            self._n = len(self.pop_X)
            weights = self._generate_weights(self._n, self._m)
            self.rebuild_unit("decomposition", weights=weights,
                              neighbors=max(1, min(int(self.cfg.neighborhood_size), self._n)))
            self._recompute_ideal()
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
    def _get_algorithm_state(self) -> Dict[str, Any]:
        """Return serialisable scalar adapter state (scalar fields + ideal point).

        For the full population array use ``get_population_snapshot()`` in addition.
        Combined, these two calls fulfil the L2 checkpoint contract.
        """
        return {
            **self._get_algorithm_local_state(),
            "ideal": None if self.ideal is None else self.ideal.tolist(),
            "weights": None if self.weights is None else self.weights.tolist(),
            "neighbors": None if self.neighbors is None else self.neighbors.tolist(),
            "candidate_tokens": list(self._population_candidate_tokens),
            "pending_indices": list(self._pending_indices),
            "pending_modes": list(self._pending_modes),
        }

    def _get_algorithm_local_state(self):
        # Unit-owned matrices, direction state and pending coordinates travel
        # once through the Unit codec in a step snapshot.
        return {
            "objective_scales": self._validated_objective_scales(),
            "_m": int(self._m),
            "_n": int(self._n),
            "population_pool_bindings": copy.deepcopy(list(self._population_pool_bindings)),
            "initialization_target": self._initialization_target,
            "initialization_proposed_count": self._initialization_proposed_count,
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        """Restore scalar adapter state from a checkpoint.

        The solution arrays (pop_X/F/V) must be restored separately via
        ``set_population_snapshot()`` to keep array ownership consistent.
        """
        if not state:
            return
        self._set_algorithm_local_state(state)
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

    def _set_algorithm_local_state(self, state):
        saved_scales = state.get("objective_scales")
        if saved_scales is not None:
            saved_scales = tuple(saved_scales)
        if saved_scales != self._validated_objective_scales():
            raise ValueError("MOEA/D checkpoint objective scales differ from the configured comparison frame")
        self._population_pool_bindings = tuple(copy.deepcopy(state.get("population_pool_bindings", ())))
        self._initialization_target = state.get("initialization_target")
        self._initialization_proposed_count = state.get("initialization_proposed_count")
        if (self._initialization_target is not None
                and (type(self._initialization_target) is not int or self._initialization_target < 2)):
            raise ValueError("MOEA/D checkpoint initialization target must be at least two")
        if (self._initialization_proposed_count is not None
                and (type(self._initialization_proposed_count) is not int or self._initialization_proposed_count < 0)):
            raise ValueError("MOEA/D checkpoint initialization proposal count must be nonnegative")
        self._m = int(state.get("_m") or self._m)
        self._n = int(state.get("_n") or self._n)
        rng_state = state.get("rng_state")
        if isinstance(rng_state, Mapping):
            self._rng.bit_generator.state = copy.deepcopy(dict(rng_state))

    def _snapshot_algorithm_step_state(self) -> Mapping[str, Any]:
        if (type(self)._get_algorithm_state is not MOEADAdapter._get_algorithm_state
                or type(self)._set_algorithm_state is not MOEADAdapter._set_algorithm_state):
            return {
                "schema": "nsgablack.moead_step_transaction/v1",
                "adapter_state": copy.deepcopy(self._get_algorithm_state()),
                "population": None if self.pop_X is None else np.array(self.pop_X, copy=True),
                "objectives": None if self.pop_F is None else np.array(self.pop_F, copy=True),
                "violations": None if self.pop_V is None else np.array(self.pop_V, copy=True),
                "runtime_projection": copy.deepcopy(self._last_context_projection),
            }
        return {
            "schema": "nsgablack.moead_step_transaction/v2",
            "adapter_state": self._get_algorithm_local_state(),
            "runtime_projection": copy.deepcopy(self._last_context_projection),
        }

    def _restore_algorithm_step_state(self, state: Mapping[str, Any]) -> None:
        schema = str(state.get("schema", ""))
        if schema not in {"nsgablack.moead_step_transaction/v1", "nsgablack.moead_step_transaction/v2"}:
            raise ValueError("unsupported MOEADAdapter step transaction schema")
        adapter_state = state.get("adapter_state")
        if not isinstance(adapter_state, Mapping):
            raise TypeError("MOEADAdapter transaction state is invalid")
        if schema == "nsgablack.moead_step_transaction/v2":
            self._set_algorithm_local_state(adapter_state)
            self._last_context_projection = copy.deepcopy(dict(state.get("runtime_projection", {}) or {}))
            return
        self._set_algorithm_state(dict(adapter_state))
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
    def _after_unit_restore(self):
        validate_pool_bindings(self._population_pool_bindings, self.pop_X, self._population_candidate_tokens)
        if (self._initialization_target is not None and self.pop_X is not None
                and len(self.pop_X) > self._initialization_target):
            raise ValueError("MOEA/D checkpoint population exceeds its initialization target")
        self._refresh_runtime_projection()

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
        except (TypeError, ValueError, KeyError):
            return False

        n = int(x_arr.shape[0]) if x_arr.ndim >= 2 else 0
        m = int(f_arr.shape[1]) if f_arr.ndim >= 2 else 0

        # If adapter is already initialised, enforce strict shape agreement.
        if self.weights is not None and self._n > 0 and n not in (0, self._n):
            return False
        if self.weights is None and self._initialization_target is not None and n > self._initialization_target:
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
        same_feedback = (np.array_equal(self.pop_F, f_arr, equal_nan=True)
                         and np.array_equal(self.pop_V, v_arr, equal_nan=True))
        validate_numeric_population_replacement(self._population_pool_bindings, preserve_tokens=preserve_tokens)
        # PopulationPartition intentionally exposes immutable arrays.  MOEA/D
        # owns a mutable runtime population, so accepting a Snapshot must cross
        # that ownership boundary with defensive copies.
        if preserve_tokens:
            self.ensure_unit().attach_feedback(f_arr, v_arr)
        else:
            self.ensure_unit().initialize_population(x_arr, f_arr, v_arr)
            self._population_pool_bindings = (None,) * len(x_arr)

        # Bootstrap dimension metadata from incoming data when uninitialised.
        if self._m == 0 and m > 0:
            self._m = m
        if self._n == 0 and n > 0:
            self._n = n

        if n > 0 and not (preserve_tokens and same_feedback):
            self._recompute_ideal()
        self._refresh_runtime_projection()
        return True

    def set_population_state(self, control, batch, feedback, *, solution_refs, provenance):
        solution_refs = tuple(solution_refs)
        count, objectives = batch.numeric_matrix.shape[0], feedback.objectives.shape[1]
        if count < 2 or objectives < 2:
            raise ValueError("MOEA/D population delivery requires at least two members and objectives")
        if self.weights is not None and (count != self._n or objectives != self._m):
            raise ValueError("MOEA/D population delivery cannot change an active decomposition shape")
        if self._m and objectives != self._m:
            raise ValueError("MOEA/D population feedback does not match its objective dimension")
        same_population = (self.weights is not None
            and tuple(binding["ref"] for binding in self._population_pool_bindings if binding is not None)
                == tuple(ref.as_dict() for ref in solution_refs)
            and np.array_equal(self.pop_F, feedback.objectives, equal_nan=True)
            and np.array_equal(self.pop_V, feedback.violations, equal_nan=True))
        install_population_state(self, control, batch, feedback, solution_refs=solution_refs, provenance=provenance)
        if not same_population:
            self._n, self._m = count, objectives
            self._initialization_target = count
            self._initialization_proposed_count = None
            self._pending_indices, self._pending_modes = [], []
        if self.weights is None:
            self.rebuild_unit("decomposition", weights=self._generate_weights(count, objectives),
                              neighbors=max(1, min(int(self.cfg.neighborhood_size), count)))
        if not same_population:
            self._recompute_ideal()
        self._refresh_runtime_projection()
        self._publish_direction_views(control)
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
        # Numeric/manual updates may lack version receipts. They remain usable
        # locally, but cannot publish a pool task by guessing a token's version.
        if any(self._population_pool_bindings):
            self._publish_direction_views(control)
        writer = getattr(control, "write_population_snapshot", None)
        if not callable(writer):
            return
        if self.pop_X is None or self.pop_F is None or self.pop_V is None:
            return
        try:
            writer(self.pop_X, self.pop_F, self.pop_V)
        except Exception:
            raise

    def _publish_direction_views(self, control):
        pool = getattr(control, "solution_pool", None)
        if pool is None or self.weights is None or self.pop_X is None or not len(self.pop_X):
            return
        self.ensure_unit().require_current_feedback()
        creator = adapter_path(control.adapter, self)
        refs = self.get_solution_pool_roots(control)
        method = str(self.cfg.decomposition).lower().strip()
        publications = []
        for i, (weight, ref) in enumerate(zip(self.weights, refs, strict=True)):
            projection = ObjectiveProjection(method, tuple(self._comparison_weights(weight)),
                tuple(self.ideal) if method == "tchebycheff" else ())
            publications.append(dict(name="/".join((*creator, f"direction:{i}")),
                refs=(ref,), created_by=creator, slot=i, projection=projection))
        pool._publish_projection_subpools(publications)

    def get_solution_pool_roots(self, control):
        return validate_pool_bindings(self._population_pool_bindings, self.pop_X,
            self._population_candidate_tokens, control=control, require=True)

    def get_population_solution_refs(self, control):
        return validate_pool_bindings(self._population_pool_bindings, self.pop_X,
            self._population_candidate_tokens, control=control, require=True)

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

    @property
    def uses_pipeline_mutation(self):
        return self.get_bound_change() is None and str(self.cfg.variation).lower().strip() != "de"

    def change(self, control: Any, idx: int, context: Dict[str, Any]) -> np.ndarray:
        """Generate one direction's proposal through the assembled or native rule.

        A custom function receives the target at row zero followed by the other
        eligible parents. All rows and direction parameters are detached data;
        the callback never receives the Solver or live Unit.
        """
        if self.get_bound_change() is None:
            return self._variation(control, idx, context)
        if self.pop_X is None or self.neighbors is None:
            raise RuntimeError("MOEA/D change requires an evaluated decomposition population")
        mode = str(context.get(KEY_MOEAD_NEIGHBOR_MODE, "neighborhood"))
        eligible = np.arange(self._n, dtype=int) if mode == "global" else np.asarray(self.neighbors[idx], dtype=int)
        # Equal values and repeated tokens may occupy distinct slots. Deduplicate
        # the offered slot indices only, keeping the current target first.
        parent_indices = tuple(dict.fromkeys((int(idx), *(int(index) for index in eligible))))
        refs = self.get_population_solution_refs(control)
        request = ChangeRequest(
            self.pop_X[list(parent_indices)],
            source_refs=tuple(refs[index] for index in parent_indices),
            parameters={
                "algorithm": "moead", "subproblem_index": int(idx),
                "mode": mode, "neighbor_mode": mode,
                "weight": self.weights[idx], "ideal": self.ideal,
                "neighbor_indices": self.neighbors[idx], "parent_indices": parent_indices,
                "decomposition": str(self.cfg.decomposition),
                "de_F": float(self.cfg.de_F), "de_CR": float(self.cfg.de_CR),
            },
            context=context,
            unit_id=self.get_unit_id(),
        )
        base = np.array(self.pop_X[idx], copy=True)
        self._bind_variation_parent(control, idx, base)
        return self.apply_change(control, base, request, context, rng=self._rng)

    def _variation(self, control: Any, idx: int, ctx: Dict[str, Any]) -> np.ndarray:
        if self.pop_X is None or self.neighbors is None:
            return self.init_candidate(control, ctx)

        mode = str(ctx.get(KEY_MOEAD_NEIGHBOR_MODE, "neighborhood"))
        if mode == "global":
            pool = np.arange(self._n, dtype=int)
        else:
            pool = np.asarray(self.neighbors[idx], dtype=int)

        if str(self.cfg.variation).lower().strip() == "de":
            trial = self._de_variation(idx, pool)
            if self.get_bound_mutator() is None:
                return trial
            # Direct mutation is an explicitly additional operator after the
            # structured DE trial, not a replacement for differential donors.
            self._bind_variation_parent(control, idx, trial)
            return self.mutate_candidate(control, trial, ctx)

        # pipeline variation fallback: mutate the current solution
        base = np.array(self.pop_X[idx], copy=True)
        if self.get_bound_mutator() is not None:
            self._bind_variation_parent(control, idx, base)
            return self.mutate_candidate(control, base, ctx)
        return np.asarray(self.mutate_candidate(control, base, ctx))

    def _bind_variation_parent(self, control, index, candidate):
        ref = self.get_population_solution_refs(control)[index]
        parent = control.propose_solutions((ref,)).semantic_states[0]
        record = control.candidate_provenance_for(parent)
        control.bind_candidate_provenance((candidate,), (record,), activate=False)

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

    def _is_better_for_subproblem(self, y_f: np.ndarray, y_v: float, j: int,
                                  *, trial_candidate=None, context=None) -> bool:
        assert self.pop_F is not None and self.pop_V is not None and self.weights is not None and self.ideal is not None

        x_f = np.asarray(self.pop_F[j], dtype=float)
        x_v = float(self.pop_V[j])
        if self.get_bound_selector() is not None:
            if trial_candidate is None:
                raise ValueError("MOEA/D replacement selection requires the evaluated trial candidate")
            weight = np.asarray(self.weights[j], dtype=float)
            request = SelectionRequest("replacement", np.vstack([self.pop_X[j], trial_candidate]),
                np.vstack([x_f, y_f]), [x_v, y_v], 1,
                scores=[self._g(x_f, weight), self._g(y_f, weight)],
                parameters={"algorithm": "moead", "slot": int(j),
                            "comparison": "decomposition_feasibility_first",
                            "decomposition": str(self.cfg.decomposition),
                            "objective_scales": self._validated_objective_scales(),
                            "weight": tuple(float(value) for value in weight),
                            "ideal": tuple(float(value) for value in self.ideal),
                            "strict_improvement": True}, context=context)
            return int(self.select_indices(request, rng=self._rng)[0]) == 1

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
        w = self._comparison_weights(w)
        if f.shape != w.shape:
            raise ValueError("MOEA/D objective values and direction weights must align")
        if str(self.cfg.decomposition).lower().strip() == "weighted_sum":
            return float(np.sum(w * f))
        # tchebycheff (default)
        assert self.ideal is not None
        return float(np.max(w * np.abs(f - self.ideal)))

    def _validated_objective_scales(self):
        value = self.cfg.objective_scales
        if value is None:
            return None
        try:
            scales = np.asarray(value, dtype=float)
        except (TypeError, ValueError):
            raise ValueError("MOEA/D objective scales must be a finite positive vector") from None
        if (scales.ndim != 1 or not len(scales) or not np.all(np.isfinite(scales))
                or np.any(scales <= 0)):
            raise ValueError("MOEA/D objective scales must be a finite positive vector")
        return tuple(float(item) for item in scales)

    def _comparison_weights(self, weight):
        weight = np.asarray(weight, dtype=float).reshape(-1)
        scales = self._validated_objective_scales()
        if scales is None:
            return weight
        if len(scales) != len(weight):
            raise ValueError("MOEA/D objective scales must align with the Problem objectives")
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            effective = weight / np.asarray(scales)
        if not np.all(np.isfinite(effective)):
            raise ValueError("MOEA/D objective scales produce non-finite comparison weights")
        return effective

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
        return simplex_points(m, H, positive=True)

    @staticmethod
    def _compute_neighbors(W: np.ndarray, T: int) -> np.ndarray:
        W = np.asarray(W, dtype=float)
        # pairwise distances in weight space
        # (N,N) but N is usually moderate; keep simple to avoid extra deps
        diff = W[:, None, :] - W[None, :, :]
        dist = np.sqrt(np.sum(diff * diff, axis=2))
        idx = np.argsort(dist, axis=1)[:, :T]
        return np.asarray(idx, dtype=int)
