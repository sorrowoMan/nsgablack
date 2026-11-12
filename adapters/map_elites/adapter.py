"""MAP-Elites with one archive owner and transactional exact Pool result views."""
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
import numpy as np

from ..unit_backed import UnitBackedAdapter
from ..operator_binding import OperatorBinding
from ..operations import OperatorBindingRestoreError
from ..subpools import adapter_path
from ...representation.map_elites_builder import MapElitesUnitBuilder
from ...core.evaluation_feedback import OptimizationFeedbackBatch
from ...core.state.solution_pool import SolutionRef
from ...core.state.step_outcome import StepOutcome
from ...units.features import _readonly
from ...units.contracts import candidate_array
from .components import IdentityDescriptor, GridCells, MinimizeObjective, GaussianArchiveEmitter


@dataclass(frozen=True)
class MapElitesConfig:
    batch_size: int = 5
    random_seed: int = 31

    def __post_init__(self):
        if type(self.batch_size) is not int or self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if type(self.random_seed) is not int or self.random_seed < 0:
            raise ValueError("random_seed must be a nonnegative integer")


class MapElitesAdapter(UnitBackedAdapter):
    unit_builder_type = MapElitesUnitBuilder
    unit_schema = MapElitesUnitBuilder.unit_type.schema
    population_state_mode = "single"
    state_recovery_level = "L2"
    state_recovery_notes = "Restores exact archive versions, grid/descriptor identities, emitter and RNG."
    accepts_proposal_replacement = True
    operation_methods = {}
    context_notes = "Archive decisions use actual evaluated candidates and raw feedback; no shared context writes."

    def __init__(self, config=None, *, descriptor=None, cells=None, competition=None,
                 emitter=None, unit_binding=None, name="map_elites", priority=0):
        super().__init__(name=name, priority=priority, unit_binding=unit_binding)
        self.config = MapElitesConfig() if config is None else config
        self.descriptor = IdentityDescriptor() if descriptor is None else descriptor
        self.cells = GridCells() if cells is None else cells
        self.competition = MinimizeObjective() if competition is None else competition
        self.emitter = GaussianArchiveEmitter() if emitter is None else emitter
        parts = (("descriptor", self.descriptor, "describe"), ("cells", self.cells, "locate"),
                 ("competition", self.competition, "prefer"), ("emitter", self.emitter, "emit"))
        if len({id(part) for _, part, _ in parts if not getattr(part, "stateless", False)}) != sum(
                not getattr(part, "stateless", False) for _, part, _ in parts):
            raise ValueError("stateful archive components require distinct ownership")
        self._parts = {key: OperatorBinding(part, method=method) for key, part, method in parts}
        self._initial_parts = {key: part.get_state() for key, part in self._parts.items()}
        self._rng = np.random.default_rng(self.config.random_seed)
        self._pending = 0

    def setup(self, control):
        pending, seen, owners = [getattr(control, "adapter", self)], set(), {}
        while pending:
            owner = pending.pop()
            if id(owner) in seen:
                continue
            seen.add(id(owner))
            pending.extend(owner.step_transaction_children())
            for name, binding in getattr(owner, "_parts", {}).items():
                if not isinstance(binding, OperatorBinding):
                    continue
                if binding.stateless:
                    continue
                identity = id(binding.component)
                if identity in owners:
                    raise ValueError("stateful algorithm component has multiple Adapter owners")
                owners[identity] = (owner, name)
        self.reset_unit()
        self._rng = np.random.default_rng(self.config.random_seed)
        self._pending = 0
        for name, binding in self._parts.items():
            binding.set_state(self._initial_parts[name])

    def propose(self, control, context):
        self._validate_pool(control)
        unit = self.ensure_unit()
        rows = tuple(self.emitter.emit(_readonly(unit.entries), self.config.batch_size,
            rng=self._rng, control=control, context=MappingProxyType(dict(context))))
        if len(rows) > self.config.batch_size:
            raise ValueError("emitter exceeded the declared batch size")
        self._pending = len(rows)
        return rows

    def get_empty_proposal_outcome(self, control, context):
        if getattr(self.emitter, "exhausted", False) is True:
            return StepOutcome(status="terminal", reason="map_elites_emitter_exhausted")
        return None

    def on_proposal_disposition(self, control, disposition, context):
        if disposition.proposed_count != self._pending:
            raise ValueError("archive disposition does not align with original proposals")
        self._pending = disposition.accepted_count

    def update(self, control, candidates, feedback, context):
        feedback = OptimizationFeedbackBatch.coerce(feedback)
        if len(candidates) != feedback.candidate_count or self._pending != len(candidates):
            raise ValueError("archive update candidates, receipts and disposition must align")
        unit = self.ensure_unit()
        entries = {tuple(item["cell"]): item for item in unit.entries}
        replacements = 0
        for index, candidate in enumerate(candidates):
            value = feedback.items[index].info.get("accepted_solution_ref")
            if value is None:
                raise ValueError("archive updates require exact accepted solution receipts")
            ref = SolutionRef.from_dict(dict(value))
            actual = control.solution_pool.read((ref,), allow_pending=True)
            x = candidate_array(candidate)
            if not np.array_equal(actual.numeric_matrix[0], x):
                raise ValueError("archive receipt candidate differs from evaluated point")
            raw_f, raw_v = control.solution_pool.read_raw_feedback((ref,), allow_pending=True)
            if not np.array_equal(raw_f[0], feedback.raw_objectives[index]) or raw_v[0] != feedback.raw_violations[index]:
                raise ValueError("archive raw feedback differs from its precise Pool version")
            descriptor = np.asarray(self.descriptor.describe(actual.semantic_states[0], feedback.items[index]), dtype=float)
            cell = tuple(self.cells.locate(descriptor))
            challenger = {"cell": cell, "descriptor": descriptor.tolist(), "candidate": x.copy(),
                "objectives": feedback.raw_objectives[index].copy(), "violation": float(feedback.raw_violations[index]),
                "quality": self.competition.quality(feedback.raw_objectives[index]), "solution_ref": ref.as_dict()}
            if self.competition.prefer(_readonly(challenger), _readonly(entries.get(cell))):
                entries[cell] = challenger
                replacements += 1
        unit.entries = [entries[key] for key in sorted(entries)]
        unit.evaluations += len(candidates)
        unit.replacements += replacements
        unit.validate()
        self._pending = 0
        creator = adapter_path(control.adapter, self)
        control.solution_pool.publish_subpool_view("/".join((*creator, "archive")),
            self.get_solution_pool_roots(control), created_by=creator)

    def _validate_pool(self, control):
        if self.algorithm_unit is None:
            return
        self._validate_archive_interpretation()
        refs = self.get_solution_pool_roots(control)
        if refs:
            batch = control.solution_pool.read(refs, allow_pending=True)
            expected = np.asarray([entry["candidate"] for entry in self.algorithm_unit.entries])
            if not np.array_equal(batch.numeric_matrix, expected):
                raise ValueError("archive members differ from their exact Pool references")
            raw_f, raw_v = control.solution_pool.read_raw_feedback(refs, allow_pending=True)
            expected_f = np.asarray([entry["objectives"] for entry in self.algorithm_unit.entries])
            expected_v = np.asarray([entry["violation"] for entry in self.algorithm_unit.entries])
            if not np.array_equal(raw_f, expected_f) or not np.array_equal(raw_v, expected_v):
                raise ValueError("archive cached raw feedback differs from its exact Pool references")

    def _validate_archive_interpretation(self):
        """Check built-in pure interpretations; never re-run a custom descriptor to observe state."""
        if self.algorithm_unit is None:
            return
        self.algorithm_unit.validate()
        for entry in self.algorithm_unit.entries:
            if type(self.cells) is GridCells and self.cells.locate(entry["descriptor"]) != tuple(entry["cell"]):
                raise ValueError("archive cell differs from the saved descriptor")
            if type(self.competition) is MinimizeObjective and self.competition.quality(entry["objectives"]) != entry["quality"]:
                raise ValueError("archive quality differs from cached raw objectives")
            if type(self.descriptor) is IdentityDescriptor:
                expected = np.asarray(entry["candidate"])
                if self.descriptor.indices is not None:
                    expected = expected[list(self.descriptor.indices)]
                if not np.array_equal(expected, entry["descriptor"]):
                    raise ValueError("archive identity descriptor differs from its candidate")

    def get_solution_pool_roots(self, control):
        return (() if self.algorithm_unit is None else tuple(
            SolutionRef.from_dict(item["solution_ref"]) for item in self.algorithm_unit.entries))

    def get_population_solution_refs(self, control):
        self._validate_pool(control)
        return self.get_solution_pool_roots(control)

    def get_population_snapshot(self):
        self._validate_archive_interpretation()
        if self.algorithm_unit is None or not self.algorithm_unit.entries:
            return None
        entries = self.algorithm_unit.entries
        return (np.asarray([x["candidate"] for x in entries]), np.asarray([x["objectives"] for x in entries]),
                np.asarray([x["violation"] for x in entries]))

    def get_population_candidate_tokens(self):
        return tuple(ref.candidate_token for ref in self.get_solution_pool_roots(None))

    def get_runtime_context_projection(self, control=None):
        unit = self.algorithm_unit
        return {"archive_size": 0 if unit is None else len(unit.entries),
                "accepted_observations": 0 if unit is None else unit.evaluations,
                "archive_replacements": 0 if unit is None else unit.replacements}

    def set_population_snapshot(self, population, objectives, violations):
        saved = self.get_population_snapshot()
        if saved is None:
            return False
        if not all(np.array_equal(a, b) for a, b in zip(saved, (population, objectives, violations))):
            raise ValueError("archive numerical setters cannot replace identified champions")
        return True

    def set_population_candidate_tokens(self, tokens):
        if tuple(tokens) != self.get_population_candidate_tokens():
            raise ValueError("archive numerical setters cannot replace champion identities")
        return True

    def _get_algorithm_state(self):
        return {"schema": "nsgablack.map_elites/v1", "config": {"batch_size": self.config.batch_size,
            "random_seed": self.config.random_seed}, "rng": deepcopy(self._rng.bit_generator.state),
            "pending": self._pending, "components": {name: binding.get_state() for name, binding in self._parts.items()}}

    def _set_algorithm_state(self, state):
        if state.get("schema") != "nsgablack.map_elites/v1" or state.get("config") != {
                "batch_size": self.config.batch_size, "random_seed": self.config.random_seed}:
            raise ValueError("MAP-Elites checkpoint configuration differs")
        if set(state["components"]) != set(self._parts):
            raise ValueError("MAP-Elites checkpoint components differ")
        pending = state["pending"]
        if type(pending) is not int or not 0 <= pending <= self.config.batch_size:
            raise ValueError("invalid archive pending count")
        rng = np.random.default_rng()
        rng.bit_generator.state = deepcopy(state["rng"])
        for name, part in self._parts.items():
            part.validate_state(state["components"][name])
        self._validate_archive_interpretation()
        previous = {name: part.get_state() for name, part in self._parts.items()}
        attempted = []
        try:
            for name, part in self._parts.items():
                attempted.append(name)
                part.set_state(state["components"][name])
        except BaseException as original:
            failures = []
            for name in reversed(attempted):
                try:
                    self._parts[name].set_state(previous[name])
                except BaseException as failure:
                    failures.append(failure)
            if failures:
                raise OperatorBindingRestoreError(original, failures) from original
            raise
        self._rng, self._pending = rng, pending
