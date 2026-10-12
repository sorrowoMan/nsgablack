"""Adapter-owned compound Units. Builders create them; decisions drive operations.

These are mutable algorithm structures, not a second Solver population or a
bag of runtime services. Numeric fields alias the Adapter compatibility API.
Provider sessions, RNGs and execution resources must never be stored here.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field, fields
from inspect import signature
from typing import Any, ClassVar, Mapping
import numpy as np
from .contracts import UnitSchema
from .features import FeatureUnit, FeatureContractError, _signature
from .population_operations import PopulationChange


def structure_schema(name: str, *fields: str, version: int = 1) -> UnitSchema:
    return UnitSchema(f"nsgablack.{name}", version=version, required_fields=fields, candidate_projection=False)


def _validate_candidate_feedback(unit):
    if not isinstance(unit.candidate_feedback, dict):
        raise ValueError("Candidate feedback must be explicit value/revision records")
    for name, record in unit.candidate_feedback.items():
        if (not isinstance(name, str) or not isinstance(record, dict)
                or set(record) != {"value", "dependencies", "revision"}
                or not isinstance(record["dependencies"], tuple) or not record["dependencies"]
                or any(not isinstance(field, str) or not hasattr(unit, field) for field in record["dependencies"])
                or not isinstance(record["revision"], str)
                or not isinstance(record["value"], (int, float))):
            raise ValueError("Invalid candidate feedback record")


def _validate_candidate_feedback_feature(unit, spec):
    if "candidate_feedback" in spec.depends_on:
        for record in unit.candidate_feedback.values():
            if record["revision"] != _signature({name: getattr(unit, name) for name in record["dependencies"]}):
                raise FeatureContractError("Candidate changed since trajectory feedback was attached")


def _validate_indices(values, upper_bound, label):
    indices = np.asarray(values)
    if indices.ndim != 1 or (indices.size and indices.dtype.kind not in "iu"):
        raise ValueError(f"{label} must be integer indices")
    if indices.size and (upper_bound is None or indices.min() < 0 or indices.max() >= upper_bound):
        raise ValueError(f"{label} are outside the associated structure")


@dataclass
class TrajectoryUnit(FeatureUnit):
    unit_id: str
    current: Any = None
    best: Any = None
    candidate_kind: str = "array"
    candidate_metadata: dict = field(default_factory=dict)
    candidate_feedback: dict = field(default_factory=dict, kw_only=True)
    schema: ClassVar = structure_schema("trajectory", "current", "best", "candidate_feedback", version=2)
    feature_feedback_fields: ClassVar = {"candidate_feedback": "selection"}

    def validate(self) -> None:
        _validate_candidate_feedback(self)
        for value in (self.current, self.best):
            if value is not None and np.asarray(value).ndim != 1:
                raise ValueError("Trajectory states must be vectors")

    def validate_feature_inputs(self, spec):
        _validate_candidate_feedback_feature(self, spec)


@dataclass
class PollUnit(TrajectoryUnit):
    directions: Any = None
    probes: list = field(default_factory=list)
    displacements: Any = None
    schema: ClassVar = structure_schema("poll", "current", "directions", "probes", "displacements", "candidate_feedback", version=2)

    def validate(self):
        super().validate()
        for value in (self.directions, self.displacements):
            if value is not None and (np.asarray(value).ndim != 2 or len(value) != len(self.probes)
                    or (self.current is not None and np.shape(value)[1] != len(self.current))):
                raise ValueError("Poll directions/displacements must align with probe identities")


@dataclass
class ParameterUnit(TrajectoryUnit):
    first_moment: Any = None
    second_moment: Any = None
    schema: ClassVar = structure_schema("parameters", "current", "first_moment", "second_moment", "candidate_feedback", version=2)

    def validate(self) -> None:
        super().validate()
        if (self.first_moment is None) != (self.second_moment is None):
            raise ValueError("Optimizer moments must occur as a pair")
        if self.first_moment is not None:
            if np.shape(self.first_moment) != np.shape(self.second_moment):
                raise ValueError("Optimizer moment shapes differ")
            if self.current is not None and np.shape(self.current) != np.shape(self.first_moment):
                raise ValueError("Optimizer moments must align with parameters")


@dataclass
class PopulationUnit(FeatureUnit):
    unit_id: str
    population: Any = None
    objectives: Any = None
    violations: Any = None
    candidate_tokens: tuple = ()
    feedback_population_revision: str | None = field(default=None, kw_only=True, repr=False)
    feedback_field_revisions: dict | None = field(default=None, kw_only=True, repr=False)
    schema: ClassVar = structure_schema("population", "population", "objectives", "violations", "candidate_tokens")
    feature_feedback_fields: ClassVar = {"objectives": "selection", "violations": "selection"}
    # Extra row-aligned fields opt into one maintenance hook. Scalar/geometry
    # fields are not automatically interpreted as population member data.
    member_fields: ClassVar[tuple[str, ...]] = ()

    def validate_member_contract(self):
        names = self.member_fields
        extra = {f.name for f in fields(self)} - {f.name for f in fields(PopulationUnit)}
        if (not isinstance(names, tuple) or any(not isinstance(n, str) or n not in extra for n in names)
                or len(set(names)) != len(names)):
            raise ValueError("member_fields must name unique extra Unit data fields")
        if not callable(self.on_members_changed):
            raise TypeError("Population Unit requires on_members_changed(change)")
        signature(self.on_members_changed).bind(None)
        if names and type(self).on_members_changed is PopulationUnit.on_members_changed:
            raise TypeError("Declared member_fields require on_members_changed(change) maintenance")

    def on_members_changed(self, change: PopulationChange) -> Mapping[str, Any]:
        """Read old fields and return detached-ready extra data updates.

        Do not mutate this Unit, evaluate, or choose members here. Every declared
        member field must be returned. The operation validates a draft containing
        both base and extra fields before publishing any of them.
        """
        return {}

    @staticmethod
    def _population_input(population, objectives, violations, candidate_tokens, *, missing_tokens=True):
        x = np.array(population, dtype=float, copy=True)
        if x.ndim != 2 or (objectives is None) != (violations is None):
            raise ValueError("Population input requires a matrix and paired feedback")
        f = None if objectives is None else np.array(objectives, dtype=float, copy=True)
        v = None if violations is None else np.array(violations, dtype=float, copy=True)
        tokens = tuple(candidate_tokens)
        if not tokens and missing_tokens:
            tokens = (None,) * len(x)
        if (len(tokens) != len(x) or any(t is not None and not isinstance(t, str) for t in tokens)
                or (f is not None and (f.ndim != 2 or len(f) != len(x) or v.shape != (len(x),)))):
            raise ValueError("Population candidates, feedback and tokens must align")
        return x, f, v, tokens

    def _publish_members(self, x, f, v, tokens, change):
        from ..representation.structure_builders import encode_unit_value, decode_unit_value
        self.validate_member_contract()
        updates = self.on_members_changed(change)
        allowed = {item.name for item in fields(self)} - {item.name for item in fields(PopulationUnit)}
        if (not isinstance(updates, Mapping) or not set(updates) <= allowed
                or not set(self.member_fields) <= set(updates)):
            raise ValueError("Member hook must return declared extra fields, including all member_fields")
        updates = decode_unit_value(encode_unit_value(dict(updates)))
        revision = None if x is None else _signature(x)
        base = dict(population=x, objectives=f, violations=v, candidate_tokens=tokens,
                    feedback_field_revisions={"objectives": revision if f is not None else None,
                                              "violations": revision if v is not None else None},
                    feedback_population_revision=revision if f is not None else None)
        draft = copy(self)
        for name, value in {**base, **updates}.items():
            object.__setattr__(draft, name, value)
        # Base alignment cannot be bypassed by a custom validator. Extra
        # validators may express dependencies beyond row count.
        PopulationUnit.validate(draft)
        if type(draft).validate is not PopulationUnit.validate:
            draft.validate()
        for name, value in {**base, **updates}.items():
            object.__setattr__(self, name, value)
        self.clear_features()
        return change

    def initialize_population(self, population, objectives=None, violations=None, *, candidate_tokens=()):
        """Install a new population; every row is explicitly a new member."""
        x, f, v, tokens = self._population_input(population, objectives, violations, candidate_tokens)
        old_count = 0 if self.population is None else len(self.population)
        change = PopulationChange("initialize", old_count, len(x), (None,) * len(x), tuple(range(len(x))))
        return self._publish_members(x, f, v, tokens, change)

    def clear_population(self):
        old_count = 0 if self.population is None else len(self.population)
        return self._publish_members(None, None, None, (), PopulationChange("clear", old_count, 0, (), ()))

    def apply_selection(self, indices, population, objectives, violations, *, candidate_tokens):
        """Apply Adapter-selected indices over [previous population, incoming].

        No ranking or survival policy lives here. Feedback and tokens follow
        exactly the same indices, including numerically identical proposals.
        """
        self.require_current_feedback()
        x, f, v, tokens = self._population_input(population, objectives, violations, candidate_tokens,
                                               missing_tokens=False)
        if f is None or x.shape[1:] != np.shape(self.population)[1:] or f.shape[1:] != np.shape(self.objectives)[1:]:
            raise ValueError("Selection incoming rows must match population dimensions and feedback")
        old_count = len(self.population)
        indices = np.asarray(indices)
        _validate_indices(indices, old_count + len(x), "Population selection indices")
        keep = indices.astype(int)
        old = tuple(int(i) if i < old_count else None for i in keep)
        new = tuple(int(i - old_count) if i >= old_count else None for i in keep)
        change = PopulationChange("selection", old_count, len(x), old, new)
        all_tokens = tuple(self.candidate_tokens or (None,) * old_count) + tokens
        return self._publish_members(np.concatenate((self.population, x))[keep],
            np.concatenate((self.objectives, f))[keep], np.concatenate((self.violations, v))[keep],
            tuple(all_tokens[i] for i in keep), change)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        revisions = getattr(self, "feedback_field_revisions", None)
        if name in {"objectives", "violations"} and revisions is not None:
            population = getattr(self, "population", None)
            revision = None if population is None or value is None else _signature(population)
            object.__setattr__(self, "feedback_field_revisions", {**revisions, name: revision})
            self._sync_feedback_revision()

    def __post_init__(self):
        # Old payloads carry one shared stamp (or none). Preserve it; new
        # payloads also distinguish a partially reattached feedback pair.
        revisions = self.feedback_field_revisions
        if revisions is None:
            revision = self.feedback_population_revision
            if revision is None and self.population is not None:
                revision = _signature(self.population)
            revisions = {name: revision if getattr(self, name) is not None else None
                         for name in ("objectives", "violations")}
        if (not isinstance(revisions, dict) or set(revisions) != {"objectives", "violations"}
                or any(value is not None and not isinstance(value, str) for value in revisions.values())):
            raise ValueError("Population feedback revisions must describe objectives and violations")
        self.feedback_field_revisions = dict(revisions)
        self._sync_feedback_revision()

    def _sync_feedback_revision(self):
        revisions = self.feedback_field_revisions
        self.feedback_population_revision = (revisions["objectives"]
            if revisions["objectives"] == revisions["violations"] else None)

    def require_current_feedback(self):
        """Reject a changed candidate matrix paired with older feedback."""
        PopulationUnit.validate(self)
        if self.population is None or self.objectives is None or self.violations is None:
            raise FeatureContractError("Population requires evaluated feedback")
        revision = _signature(self.population)
        if any(self.feedback_field_revisions[name] != revision for name in ("objectives", "violations")):
            raise FeatureContractError("Population changed since feedback was attached; reevaluate before reading selection features")

    def validate_feature_inputs(self, spec):
        if spec.feedback_view == "selection" and self.objectives is not None and self.violations is not None:
            self.require_current_feedback()

    def attach_feedback(self, objectives, violations):
        """Attach an aligned evaluated pair to the current candidate matrix.

        This records the owner's assertion of alignment, not proof of evaluation.
        Validate and detach both arrays before changing either current field.
        """
        if self.population is None:
            raise ValueError("Population feedback requires population rows")
        objectives, violations = np.array(objectives, copy=True), np.array(violations, copy=True)
        count = len(self.population)
        if objectives.ndim != 2 or len(objectives) != count or violations.shape != (count,):
            raise ValueError("Population feedback must align with rows")
        revision = _signature(self.population)
        object.__setattr__(self, "objectives", objectives)
        object.__setattr__(self, "violations", violations)
        self.feedback_field_revisions = dict(objectives=revision, violations=revision)
        self._sync_feedback_revision()

    def replace_evaluated_rows(self, indices, population, objectives, violations, *, candidate_tokens):
        """Replace candidate/feedback/identity together after Adapter selection.

        All validation and array writes use drafts before publishing fields.
        Repeated indices apply in input order. No acceptance or search decision
        is made here; the enclosing step transaction still owns rollback.
        """
        self.require_current_feedback()
        indices = np.asarray(indices)
        _validate_indices(indices, len(self.population), "Population replacement indices")
        count = len(indices)
        x, f, v = np.asarray(population), np.asarray(objectives), np.asarray(violations)
        tokens = tuple(candidate_tokens)
        if (x.shape != (count, np.shape(self.population)[1])
                or f.shape != (count, np.shape(self.objectives)[1]) or v.shape != (count,)
                or len(tokens) != count or any(t is not None and not isinstance(t, str) for t in tokens)):
            raise ValueError("Population replacement candidates, feedback and tokens must align")
        if not count:
            return
        new_x, new_f, new_v = (np.array(value, copy=True) for value in
                               (self.population, self.objectives, self.violations))
        new_tokens = list(self.candidate_tokens or (None,) * len(new_x))
        for row, index in enumerate(indices):
            new_x[index], new_f[index], new_v[index] = x[row], f[row], v[row]
            new_tokens[index] = tokens[row]
        old = list(range(len(new_x)))
        incoming = [None] * len(new_x)
        for row, index in enumerate(indices):
            old[index], incoming[index] = None, row
        change = PopulationChange("replacement", len(new_x), count, tuple(old), tuple(incoming))
        return self._publish_members(new_x, new_f, new_v, tuple(new_tokens), change)

    def pairwise_distances(self, *, cache=True):
        """Lazily maintain numeric geometry; tokens still define membership identity."""
        from .population_features import POPULATION_DISTANCES
        return self.feature(POPULATION_DISTANCES, cache=cache)

    def validate(self) -> None:
        self.validate_member_contract()
        count = 0 if self.population is None else len(self.population)
        for name in self.member_fields:
            value = getattr(self, name)
            if np.ndim(value) == 0 or len(value) != count:
                raise ValueError(f"Population member field {name} must align with rows")
        if self.population is None:
            if self.objectives is not None or self.violations is not None or self.candidate_tokens:
                raise ValueError("Population Unit feedback/tokens require population rows")
            return
        x = np.asarray(self.population)
        if x.ndim != 2:
            raise ValueError("Population Unit requires a matrix")
        n = len(x)
        if self.candidate_tokens and len(self.candidate_tokens) != n:
            raise ValueError("Population Unit candidate tokens must align with rows")
        if (self.objectives is None) != (self.violations is None):
            raise ValueError("Population Unit objectives and violations must occur as a pair")
        for value, ndim in ((self.objectives, 2), (self.violations, 1)):
            if value is not None and (np.asarray(value).ndim != ndim or len(value) != n):
                raise ValueError("Population Unit feedback must align with rows")


@dataclass
class ReferencePopulationUnit(PopulationUnit):
    reference_points: Any = field(default_factory=lambda: np.zeros((0, 0)))
    schema: ClassVar = structure_schema("reference_population", *PopulationUnit.schema.required_fields, "reference_points")

    def validate(self):
        super().validate()
        refs = np.asarray(self.reference_points)
        if refs.ndim != 2 or (refs.size and self.objectives is not None and refs.shape[1] != np.shape(self.objectives)[1]):
            raise ValueError("Reference directions must match objective geometry")


@dataclass
class DifferentialPopulationUnit(PopulationUnit):
    target_indices: list = field(default_factory=list)
    target_scores: Any = field(default_factory=lambda: np.zeros(0))
    schema: ClassVar = structure_schema("differential_population", *PopulationUnit.schema.required_fields, "target_indices", "target_scores")

    def validate(self) -> None:
        super().validate()
        if np.asarray(self.target_scores).ndim != 1 or len(self.target_indices) != len(self.target_scores):
            raise ValueError("DE targets and baseline scores must align")
        _validate_indices(self.target_indices,
            None if self.population is None else len(self.population), "DE targets")


@dataclass
class DecompositionUnit(PopulationUnit):
    weights: Any = None
    neighbors: Any = None
    ideal: Any = None
    pending_indices: list = field(default_factory=list)
    pending_modes: list = field(default_factory=list)
    schema: ClassVar = structure_schema("decomposition", *PopulationUnit.schema.required_fields, "weights", "neighbors", "ideal", "pending_indices", "pending_modes")

    def validate(self) -> None:
        super().validate()
        if self.weights is not None and np.asarray(self.weights).ndim != 2:
            raise ValueError("Decomposition weights must be a matrix")
        if self.weights is not None and self.neighbors is not None:
            w, b = np.asarray(self.weights), np.asarray(self.neighbors)
            if b.ndim != 2 or b.dtype.kind not in "iu" or len(b) != len(w) or (b.size and (b.min() < 0 or b.max() >= len(w))):
                raise ValueError("Decomposition neighbors do not address weights")
        if self.weights is not None:
            w = np.asarray(self.weights)
            if self.population is not None and len(w) != len(self.population):
                raise ValueError("Decomposition weights must align with population rows")
            if self.objectives is not None and w.shape[1] != np.shape(self.objectives)[1]:
                raise ValueError("Decomposition weights must match objective dimensions")
            if self.ideal is not None and np.shape(self.ideal) != (w.shape[1],):
                raise ValueError("Decomposition ideal must match objective dimensions")
        elif self.neighbors is not None:
            raise ValueError("Decomposition neighbors require weights")
        elif self.ideal is not None:
            # Public population bootstrap can compute an ideal before setup
            # materializes weights and neighborhoods.
            if np.asarray(self.ideal).ndim != 1 or (self.objectives is not None
                    and len(self.ideal) != np.shape(self.objectives)[1]):
                raise ValueError("Decomposition ideal must match objective dimensions")
        if len(self.pending_indices) != len(self.pending_modes):
            raise ValueError("Subproblem proposal records must align")
        _validate_indices(self.pending_indices,
            len(self.weights) if self.weights is not None else
            (None if self.population is None else len(self.population)), "Subproblem targets")


@dataclass
class RegionUnit(FeatureUnit):
    unit_id: str
    center: Any = None
    basis: Any = None
    weights: Any = None
    basis_method: str = "none"
    candidate_feedback: dict = field(default_factory=dict, kw_only=True)
    schema: ClassVar = structure_schema("local_region", "center", "basis", "weights", "basis_method", "candidate_feedback", version=2)
    feature_feedback_fields: ClassVar = {"candidate_feedback": "selection"}

    def validate(self) -> None:
        _validate_candidate_feedback(self)
        if self.center is not None and np.asarray(self.center).ndim != 1:
            raise ValueError("Region center must be a vector")
        if self.basis is not None:
            b = np.asarray(self.basis)
            if b.ndim != 2 or (self.center is not None and len(b) != len(self.center)):
                raise ValueError("Region basis does not match its center")

    def validate_feature_inputs(self, spec):
        _validate_candidate_feedback_feature(self, spec)


@dataclass
class ModelSearchUnit(FeatureUnit):
    unit_id: str
    center: Any = None
    history_x: list = field(default_factory=list)
    history_y: list = field(default_factory=list)
    schema: ClassVar = structure_schema("model_search", "center", "history_x", "history_y")

    def validate(self) -> None:
        if len(self.history_x) != len(self.history_y):
            raise ValueError("Surrogate input and target history must align")


@dataclass
class ArchiveUnit(FeatureUnit):
    unit_id: str
    entries: list = field(default_factory=list)
    schema: ClassVar = structure_schema("elite_archive", "entries")


@dataclass
class NeighborhoodUnit(FeatureUnit):
    unit_id: str
    scales: tuple = ()
    schema: ClassVar = structure_schema("neighborhoods", "scales")

    def validate(self):
        if not self.scales or any(not np.isfinite(s) or s < 0 for s in self.scales):
            raise ValueError("Neighborhood scales must be nonempty, finite and nonnegative")
