"""
Variable Neighborhood Search (VNS) as an AlgorithmAdapter.

This adapter keeps the framework's philosophy:
- Strategy logic in adapter (propose/update)
- Operators (mutation/repair) in RepresentationPipeline where possible
"""

from __future__ import annotations
from blackbase.representation import representation_capabilities

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from ..algorithm_adapter import AlgorithmAdapter
from ...units import UnitBinding, UnitBuildRequest, CANDIDATE_SCHEMA
from ...units import StructureBuildRequest
from ...representation.structure_builders import NeighborhoodUnitBuilder
from ...units.contracts import candidate_array
from ...representation.unit_builders import CandidateUnitBuilder
import warnings

from nsgablack.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K
from blackbase.types import UnknownState
from blackbase.contracts import BatchDisposition


@dataclass
class VNSConfig:
    # number of candidates proposed per step
    batch_size: int = 32

    # neighborhood index range: k in [0, k_max]
    k_max: int = 5

    # sigma schedule: sigma = base_sigma * (scale ** k)
    base_sigma: float = 0.2
    scale: float = 1.6
    max_sigma: float = 10.0

    # accept if strictly better (with constraint penalty)
    accept_tolerance: float = 0.0

    # restart if no improvement after k_max neighborhoods
    restart_on_stagnation: bool = True

    # objective aggregation for multi-objective fallback scoring
    objective_aggregation: str = "sum"  # "sum" or "first"


class VNSAdapter(AlgorithmAdapter):
    """VNS adapter for ComposableSolver."""
    pool_input_modes = ("initialize",)
    supports_pool_restart = True
    uses_pipeline_mutation = True
    context_requires = ("generation",)
    context_provides = (KEY_VNS_K, KEY_MUTATION_SIGMA)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "VNS writes neighborhood index/sigma into per-step context for mutator consumption.",
        "Use context-aware mutator to make neighborhood switching effective.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores neighborhood structure, incumbent/pending Units and identity counter."
    unit_schema = CANDIDATE_SCHEMA
    unit_build_operations = ("fresh", "spawn", "refresh")
    unit_contract_mode = "owned"
    additional_unit_schemas = {"neighborhood": NeighborhoodUnitBuilder.unit_type.schema}
    additional_unit_build_operations = {"neighborhood": ("initialize",)}

    # Soft partner contracts (informational; no hard dependency).
    #
    # VNS itself is representation-agnostic. It communicates neighborhood changes
    # via `context` and expects the representation pipeline's mutator (or a wrapper)
    # to consume these keys.
    recommended_mutators = ["ContextGaussianMutation", "ContextSelectMutator"]

    def __init__(
        self,
        config: Optional[VNSConfig] = None,
        name: str = "vns",
        priority: int = 0,
        unit_binding: Optional[UnitBinding] = None,
        neighborhood_binding: Optional[UnitBinding] = None,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=VNSConfig,
            config_kwargs=config_kwargs,
            adapter_name="VNSAdapter",
        )
        self.cfg = self.config
        self.set_unit_binding(unit_binding or UnitBinding(CandidateUnitBuilder()))
        self.neighborhood_binding = neighborhood_binding or UnitBinding(NeighborhoodUnitBuilder())
        self._require_unit_binding(self.neighborhood_binding, slot="neighborhood")
        self.neighborhood_unit = self.neighborhood_binding.build(StructureBuildRequest(
            f"{name}:neighborhoods", parameters={"k_max": self.cfg.k_max,
                "base_sigma": self.cfg.base_sigma, "scale": self.cfg.scale, "max_sigma": self.cfg.max_sigma}))
        if len(self.neighborhood_unit.scales) != int(self.cfg.k_max) + 1:
            raise ValueError("VNS neighborhood Unit must expose k_max + 1 neighborhoods")
        self._unit_counter = 0
        self._current_unit = None
        self._current_pool_token = None
        self._pending_units = []
        self.k = 0
        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self._warned_missing_operator = False
        self._last_context_projection: Dict[str, Any] = {}

    @property
    def current_unit(self):
        return self._current_unit

    @property
    def current_x(self):
        return None if self._current_unit is None else candidate_array(self._current_unit.to_candidate()).copy()

    @current_x.setter
    def current_x(self, candidate):
        if candidate is None:
            self._current_unit = None
            return
        self._current_unit = self._build_candidate_unit(candidate, {})

    def _build_candidate_unit(self, candidate, context):
        next_id = self._unit_counter + 1
        build_context = dict(context)
        build_context.setdefault(KEY_VNS_K, int(self.k))
        build_context.setdefault(KEY_MUTATION_SIGMA, float(self._current_sigma()))
        unit = self.unit_binding.build(UnitBuildRequest(
            f"{self.name}:candidate:{next_id}", candidate,
            purpose="fresh" if self._current_unit is None else "spawn",
        ), build_context)
        self._unit_counter = next_id
        return unit

    def setup(self, control: Any) -> None:
        self.validate_unit_bindings()
        self._unit_counter = 0
        self._pending_units = []
        self.k = 0
        self.current_x = None
        self.current_score = None
        self._current_pool_token = None
        self._warn_if_pipeline_does_not_consume_context(control)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(self._current_sigma()),
        }

    def _warn_if_pipeline_does_not_consume_context(self, control: Any) -> None:
        """Emit diagnostics without depending on the host source-code code page."""
        if self._warned_missing_operator:
            return
        pipeline = getattr(control, "representation_pipeline", None)
        if not representation_capabilities(pipeline).supports("mutate"):
            warnings.warn(
                "VNSAdapter pipeline has no declared mutate capability; VNS can only "
                "produce a fixed candidate or fail. Configure a context-aware "
                "ContextGaussianMutation or ContextSelectMutator.",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True
            return
        # Capability is declared by the pipeline; context consumption uses the
        # existing component contract, never a guess from parameter names.
        mutator = getattr(pipeline, "mutator", pipeline)
        consumes = bool(getattr(mutator, "context_requires", ()))
        if not consumes:
            warnings.warn(
                "VNSAdapter found a mutator without declared context_requires. "
                "Neighborhood changes may degrade "
                "to fixed perturbations. Use ContextGaussianMutation, "
                "ContextSelectMutator, or another context-aware mutator.",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            self._current_unit = self._build_candidate_unit(control.init_candidate(context), context)

        # Evaluate the seed itself before comparing neighbors. A pool restart
        # cannot silently assign the first neighbor's score to the input seed.
        if self.current_score is None:
            self._pending_units = [self._current_unit]
            return [self._current_unit.to_candidate()]

        sigma = float(self._current_sigma())
        ctx = dict(context)
        ctx[KEY_VNS_K] = int(self.k)
        ctx[KEY_MUTATION_SIGMA] = float(sigma)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(sigma),
        }

        out = []
        self._pending_units = []
        for _ in range(int(self.cfg.batch_size)):
            # Existing numeric mutators consume arrays. Preserve the semantic
            # envelope after numeric mutation. The control plane repairs later.
            template = self._current_unit.to_candidate()
            cand = self.mutate_candidate(control, self.current_x, ctx)
            if isinstance(template, UnknownState) and not isinstance(cand, UnknownState):
                cand = template.with_values(cand)
            unit = self._build_candidate_unit(cand, ctx)
            self._pending_units.append(unit)
            out.append(unit.to_candidate())
        return out

    def get_operator_unit(self):
        return self._current_unit

    def _proposal_contexts(self, proposed_count, context):
        return tuple({**context, KEY_VNS_K: int(self.k), KEY_MUTATION_SIGMA: float(self._current_sigma())}
                     for _ in range(proposed_count))

    def on_proposal_repair(self, control, repair, context):
        if repair.proposed_count != len(self._pending_units):
            raise ValueError("VNS repair must align with pending Units")
        for row in repair.changed_rows:
            index = repair.proposal_indices[row]
            old = self._pending_units[index]
            self._pending_units[index] = self.unit_binding.build(UnitBuildRequest(
                old.unit_id, repair.after.semantic_states[row], purpose="refresh"), context)

    def on_proposal_disposition(self, control, disposition: BatchDisposition, context) -> None:
        if disposition.proposed_count != len(self._pending_units):
            raise ValueError("VNS proposal disposition does not match pending Units")
        self._pending_units = [self._pending_units[index] for index in disposition.accepted_indices]

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if candidates is None or len(candidates) == 0:
            return
        if self._pending_units and len(candidates) != len(self._pending_units):
            raise ValueError("VNS feedback does not match pending Units")

        scores = self._scores(objectives, violations)
        best_idx = int(np.argmin(scores))
        best_score = float(scores[best_idx])

        if self.current_score is None:
            self.current_score = best_score
            self._accept_candidate(control, candidates, best_idx, context)
            self._pending_units = []
            self.k = 0
            return

        improved = (best_score + float(self.cfg.accept_tolerance)) < float(self.current_score)
        if improved:
            self.current_score = best_score
            self._accept_candidate(control, candidates, best_idx, context)
            self._pending_units = []
            self.k = 0
            self._last_context_projection = {
                KEY_VNS_K: int(self.k),
                KEY_MUTATION_SIGMA: float(self._current_sigma()),
            }
            return

        # no improvement: move to next neighborhood
        self._pending_units = []
        self.k += 1
        if self.k > int(self.cfg.k_max):
            if bool(self.cfg.restart_on_stagnation):
                self.k = 0
                self._current_unit = self._build_candidate_unit(control.init_candidate(context), context)
                self.current_score = None
                self._current_pool_token = None
            else:
                self.k = int(self.cfg.k_max)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(self._current_sigma()),
        }

    def _current_sigma(self) -> float:
        return float(self.neighborhood_unit.scales[int(self.k)])

    def _accept_candidate(self, control, candidates, index, context):
        self._current_pool_token = self.candidate_tokens_for(control, candidates)[index]
        resolver = getattr(control, "semantic_candidate_state", None)
        candidate = candidates[index]
        if callable(resolver) and not isinstance(candidate, UnknownState):
            candidate = resolver(candidate, candidate_index=index)
        previous = self._pending_units[index] if index < len(self._pending_units) else None
        if previous is not None:
            projected = previous.to_candidate()
            same_values = np.array_equal(candidate_array(projected), candidate_array(candidate), equal_nan=True)
            old_meta = projected.as_dict()["metadata"] if isinstance(projected, UnknownState) else {}
            new_meta = candidate.as_dict()["metadata"] if isinstance(candidate, UnknownState) else {}
            if same_values and old_meta == new_meta:
                self._current_unit = previous
                return
        # The mapped candidate was repaired or supplied directly: construct its
        # new structure instead of guessing an old identity from other rows.
        self._current_unit = self._build_candidate_unit(candidate, context)

    def get_current_candidates(self):
        return None if self._current_unit is None else (self._current_unit.to_candidate(),)

    def restart_search(self, control, context):
        """Start a new local task without replaying setup or resetting IDs."""
        self._current_unit = None
        self._current_pool_token = None
        self._pending_units = []
        self.current_score = None
        self.k = 0
        self._last_context_projection = {KEY_VNS_K: 0, KEY_MUTATION_SIGMA: float(self._current_sigma())}

    def get_solution_pool_roots(self, control):
        if self.current_score is None:
            return ()
        return control.solution_pool.refs_for_tokens((self._current_pool_token,))

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._last_context_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {str(k): source for k in self._last_context_projection.keys()}

    def _scores(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        mode = str(self.cfg.objective_aggregation).lower().strip()
        if mode == "first":
            agg = obj[:, 0]
        else:
            agg = np.sum(obj, axis=1)
        return agg + (1e6 * vio)

    def get_state(self) -> Dict[str, Any]:
        return {
            "unit_contract": self.get_unit_contract(),
            "neighborhood_unit": self.neighborhood_binding.dump(self.neighborhood_unit),
            "current_unit": None if self._current_unit is None else self.unit_binding.dump(self._current_unit),
            "unit_counter": self._unit_counter,
            "pending_units": [self.unit_binding.dump(unit) for unit in self._pending_units],
            "k": int(self.k),
            "current_x": None if self.current_x is None else candidate_array(self.current_x).tolist(),
            "current_score": None if self.current_score is None else float(self.current_score),
            "current_pool_token": self._current_pool_token,
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "unit_contract" in state and state["unit_contract"] != self.get_unit_contract():
            raise ValueError("VNS checkpoint Unit binding mismatch")
        current = self._current_unit
        counter = self._unit_counter
        k = int(state.get("k", self.k))
        neighborhood = (self.neighborhood_binding.restore(state["neighborhood_unit"])
                        if "neighborhood_unit" in state else self.neighborhood_unit)
        if len(neighborhood.scales) != int(self.cfg.k_max) + 1 or not 0 <= k < len(neighborhood.scales):
            raise ValueError("VNS checkpoint neighborhood structure does not match configuration")
        score = state.get("current_score", self.current_score)
        pending = [self.unit_binding.restore(unit) for unit in state.get("pending_units", ())]
        if "current_unit" in state:
            current = (None if state["current_unit"] is None
                       else self.unit_binding.restore(state["current_unit"]))
            counter = int(state["unit_counter"])
            if counter < 0:
                raise ValueError("VNS Unit counter must be nonnegative")
        elif "current_x" in state:
            current = None
            if state["current_x"] is not None:
                counter += 1
                current = self.unit_binding.build(UnitBuildRequest(
                    f"{self.name}:candidate:{counter}", state["current_x"],
                ), {KEY_VNS_K: k})
        self._current_unit = current
        self.neighborhood_unit = neighborhood
        self._unit_counter = counter
        self._pending_units = pending
        self.k = k
        self.current_score = score
        self._current_pool_token = state.get("current_pool_token")
        self._last_context_projection = {
            KEY_VNS_K: int(self.k), KEY_MUTATION_SIGMA: float(self._current_sigma()),
        }
