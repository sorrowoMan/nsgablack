"""Synchronous single-objective BO over formal, full evaluation evidence."""
from copy import deepcopy
from dataclasses import dataclass
import numpy as np
from blackbase.types import UnknownState

from ..unit_backed import UnitBackedAdapter
from ...core.evaluation_feedback import OptimizationFeedbackBatch
from ...core.state.solution_pool import SolutionRef
from ...representation.bayesian_builder import BayesianUnitBuilder
from ...units.contracts import candidate_array
from .components import FixedRBFPosterior, LowerConfidenceBound, GridAcquisitionOptimizer
from .evidence import collect_evidence, unpack_evidence, require_unintercepted_problem


@dataclass(frozen=True)
class BayesianOptimizationConfig:
    initial_points: tuple = ((0.0,), (1.0,))

    def __post_init__(self):
        points = np.asarray(self.initial_points, dtype=float)
        if points.ndim != 2 or not len(points) or not np.isfinite(points).all():
            raise ValueError("BO initial_points must be a finite nonempty matrix")
        object.__setattr__(self, "initial_points", tuple(tuple(row) for row in points.tolist()))


class BayesianOptimizationAdapter(UnitBackedAdapter):
    """Model-based proposals; candidate membership never defines training truth.

    Initial points are an explicit algorithm initializer. Subsequent numerical
    proposals are ordinary candidates and pass the shared Problem pipeline.
    Exact GP caches are derived; only verified dataset values are authoritative.
    """
    unit_builder_type = BayesianUnitBuilder
    unit_schema = BayesianUnitBuilder.unit_type.schema
    state_recovery_level = "L1"
    state_recovery_notes = "Portable verified observations, fixed GP interpretation, exact member refs."
    accepts_proposal_replacement = True
    context_requires = context_provides = context_mutates = context_cache = ()
    context_notes = "Consumes verified Evaluation Events and Adapter-owned Unit data; no shared context keys."

    def __init__(self, config=None, *, model=None, acquisition=None, optimizer=None,
                 unit_binding=None, name="bayesian_optimization", priority=0):
        super().__init__(name, priority, unit_binding=unit_binding)
        self.config = config or BayesianOptimizationConfig()
        self.model = model or FixedRBFPosterior()
        self.acquisition = acquisition or LowerConfidenceBound()
        self.optimizer = optimizer or GridAcquisitionOptimizer()
        for component in (self.model, self.acquisition, self.optimizer):
            if not callable(getattr(component, "describe", None)):
                raise TypeError("BO components must declare a stable describe() interpretation")
        if not callable(getattr(self.model, "spawn", None)):
            raise TypeError("BO model must provide spawn() for a fresh transactional numerical cache")
        if getattr(self.model, "component_state_mode", None) != "rebuild":
            raise TypeError("BO model must explicitly declare rebuild state semantics")
        for component in (self.acquisition, self.optimizer):
            if getattr(component, "component_state_mode", None) != "stateless":
                raise TypeError("BO acquisition/optimizer must explicitly declare stateless semantics; stateful components are unsupported")
        self._control = None
        self._pending_evidence = []
        self.model = self.model.spawn()
        self._owner_path = None

    def interpretation(self):
        return {"schema": "nsgablack.synchronous_bo/v1", "model": self.model.describe(),
                "acquisition": self.acquisition.describe(), "optimizer": self.optimizer.describe(),
                "initial_points": [list(row) for row in self.config.initial_points],
                "observation_policy": "direct_problem_raw/v1"}

    def setup(self, control):
        super().setup(control)
        if int(control.num_objectives) != 1 or len(self.config.initial_points[0]) != int(control.dimension):
            raise ValueError("BO initialization requires one objective and aligned points")
        if any(str(direction).lower() in {"max", "maximize", "maximise"}
               for direction in (getattr(control.problem, "objectives", None) or ())):
            raise ValueError("synchronous BO currently supports minimization only")
        self._control = control
        from ..subpools import adapter_path
        self._owner_path = adapter_path(control.adapter, self)
        self._pending_evidence = []
        self.model = self.model.spawn()

    def _model_from_rows(self, rows):
        # Model is a component cache. Failed fit must not advance dataset/cursor.
        model = self.model.spawn()
        if model is self.model or model.describe() != self.model.describe():
            raise ValueError("BO model spawn must return a fresh cache with the same interpretation")
        if rows:
            model.fit([row["x"] for row in rows], [row["y"] for row in rows])
        return model

    def synchronize_observations(self, control):
        unit = self.ensure_unit()
        if unit.owner_path and tuple(unit.owner_path) != tuple(self._owner_path):
            raise ValueError("BO Unit owner path differs from the current Adapter instance")
        unit.owner_path = tuple(self._owner_path)
        evidence = deepcopy(unit.evidence)
        known_events = {(value["run_id"], value["event_id"]) for value in evidence}
        incoming = [*self._pending_evidence, *collect_evidence(control, unit.owner_path, known_events)]
        for value in incoming:
            key = (value["run_id"], value["event_id"])
            if key not in known_events:
                unpack_evidence(value, unit.owner_path)
                evidence.append(deepcopy(value))
                known_events.add(key)
        rows = [row for value in evidence for row in unpack_evidence(value, unit.owner_path)]
        if rows != unit.observations:
            model = self._model_from_rows(rows)
            unit.evidence, unit.observations = evidence, rows
            unit.model_revision += 1
            self.model = model
        self._pending_evidence = []
        return tuple(deepcopy(unit.observations))

    def initial_candidates(self, control, context):
        del control, context
        unit = self.ensure_unit()
        observed_seeds = {row["seed_index"] for row in unit.observations if row["seed_index"] is not None}
        return tuple(UnknownState(np.asarray(point, dtype=float),
            {"bo_owner": list(unit.owner_path), "bo_seed_index": i})
            for i, point in enumerate(self.config.initial_points) if i not in observed_seeds)

    def select_acquisition(self, control, context):
        del control, context
        unit = self.ensure_unit()
        points, report = self.optimizer.minimize(self.model, self.acquisition)
        points = np.asarray(points, dtype=float)
        if points.ndim != 2 or not len(points) or not np.isfinite(points).all():
            raise ValueError("BO acquisition optimizer must return finite candidate rows")
        unit.last_acquisition = deepcopy(report)
        return tuple(UnknownState(row.copy(), {"bo_owner": list(unit.owner_path)}) for row in points)

    def propose(self, control, context):
        require_unintercepted_problem(control)
        self.get_solution_pool_roots()
        self.synchronize_observations(control)
        seeds = self.initial_candidates(control, context)
        return seeds if seeds else self.select_acquisition(control, context)

    def on_proposal_repair(self, control, repair, context):
        del control, context
        # These fields bind the original algorithm owner and initial seed slot,
        # not domain content. Numerical/domain repairs are allowed, but losing
        # this binding would silently drop observations or repeat initialization.
        absent = object()
        for before, after in zip(repair.before.semantic_states, repair.after.semantic_states, strict=True):
            for key in ("bo_owner", "bo_seed_index"):
                if before.metadata.get(key, absent) != after.metadata.get(key, absent):
                    raise ValueError(f"BO repair must preserve reserved algorithm metadata: {key}")

    def update(self, control, candidates, feedback, context):
        del context
        unit = self.ensure_unit()
        feedback = OptimizationFeedbackBatch.coerce(feedback)
        if feedback.candidate_count != len(candidates):
            raise ValueError("BO update candidates/feedback must align")
        refs = [SolutionRef.from_dict(item.info["accepted_solution_ref"]) for item in feedback.items]
        unit.accepted_refs = [ref.as_dict() for ref in refs]
        unit.accepted_values = [candidate_array(candidate).tolist() for candidate in candidates]
        # The full Event is already durable here, including rows excluded by
        # admission. Re-sync before the next proposal also learns failed steps.
        self.synchronize_observations(control)

    def get_current_candidates(self):
        return () if self.algorithm_unit is None else tuple(np.asarray(row) for row in self.algorithm_unit.accepted_values)

    def get_solution_pool_roots(self, control=None):
        if self.algorithm_unit is None:
            return ()
        unit = self.algorithm_unit
        refs = tuple(SolutionRef.from_dict(ref) for ref in unit.accepted_refs)
        control = control or self._control
        if refs and control is not None:
            batch = control.solution_pool.read(refs, allow_pending=True)
            if not np.array_equal(batch.numeric_matrix, np.asarray(unit.accepted_values)):
                raise ValueError("BO accepted members disagree with exact Pool versions")
        return refs

    def _get_algorithm_state(self):
        pending = deepcopy(self._pending_evidence)
        if self._control is not None and self._owner_path is not None:
            evidence = [] if self.algorithm_unit is None else self.algorithm_unit.evidence
            known = {(value["run_id"], value["event_id"]) for value in [*evidence, *pending]}
            pending.extend(collect_evidence(self._control, self._owner_path, known))
        return {"interpretation": self.interpretation(), "pending_dataset_evidence": pending,
                "owner_path": self._owner_path}

    def _set_algorithm_state(self, state):
        if state.get("interpretation", self.interpretation()) != self.interpretation():
            raise ValueError("BO checkpoint model/acquisition/optimizer interpretation differs")
        path = state.get("owner_path")
        if path is not None:
            path = tuple(path)
            if self._owner_path is not None and self._owner_path != path:
                raise ValueError("BO checkpoint Adapter owner path differs")
            self._owner_path = path
        pending = deepcopy(state.get("pending_dataset_evidence", []))
        for value in pending:
            unpack_evidence(value, self._owner_path or ())
        self._pending_evidence = pending
        if self.algorithm_unit is None:
            self.model = self.model.spawn()

    def _after_unit_restore(self):
        unit = self.algorithm_unit
        if tuple(unit.owner_path) != tuple(self._owner_path or ()):
            raise ValueError("BO restored Unit owner path differs")
        expected = [row for value in unit.evidence for row in unpack_evidence(value, unit.owner_path)]
        if expected != unit.observations:
            raise ValueError("BO dataset differs from its portable verified evidence")
        self.model = self._model_from_rows(expected)
