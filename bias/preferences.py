"""Explicit comparison subjects. Adapters, not preferences, make decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Callable

import numpy as np
from blackbase.types import UnknownState

from nsgablack.units.views import UnitView, PopulationView
from .core.base import AlgorithmicBias


class PreferenceContractError(ValueError):
    """A declared preference cannot run; never silently disable the preference."""


class PreferenceScope(str, Enum):
    CANDIDATE = "candidate"
    CANDIDATE_IN_UNIT = "candidate_in_unit"
    UNIT = "unit"
    UNIT_TRANSITION = "unit_transition"


@dataclass(frozen=True)
class PreferenceQuery:
    scope: PreferenceScope
    candidate: object = None
    candidate_token: str | None = None
    unit: UnitView | None = None
    proposed_unit: UnitView | None = None
    numeric_candidate: object = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        scope = PreferenceScope(self.scope)
        object.__setattr__(self, "scope", scope)
        has_candidate = scope in (PreferenceScope.CANDIDATE, PreferenceScope.CANDIDATE_IN_UNIT)
        if has_candidate != (self.candidate is not None):
            raise PreferenceContractError("Preference scope and candidate disagree")
        if (scope != PreferenceScope.CANDIDATE) != (self.unit is not None):
            raise PreferenceContractError("Preference scope and Unit dependency disagree")
        if self.unit is not None and not isinstance(self.unit, UnitView):
            raise PreferenceContractError("Preferences require a detached UnitView")
        if (scope == PreferenceScope.UNIT_TRANSITION) != (self.proposed_unit is not None):
            raise PreferenceContractError("Only a Unit transition has a proposed Unit")
        if self.proposed_unit is not None:
            if not isinstance(self.proposed_unit, UnitView) or self.unit.identity != self.proposed_unit.identity:
                raise PreferenceContractError("A transition must preserve the Unit owner, ID and schema")
        if self.candidate_token is not None and (not has_candidate or not isinstance(self.candidate_token, str) or not self.candidate_token):
            raise PreferenceContractError("A candidate token requires a candidate subject")
        if has_candidate:
            semantic = self.candidate if isinstance(self.candidate, UnknownState) else None
            values = np.asarray(semantic.as_array() if semantic is not None else self.candidate, dtype=float)
            if values.ndim != 1 or not np.all(np.isfinite(values)):
                raise PreferenceContractError("Candidate preference requires a finite numeric projection")
            numeric = np.frombuffer(values.tobytes(), dtype=float)
            object.__setattr__(self, "numeric_candidate", numeric)
            object.__setattr__(self, "candidate", semantic if semantic is not None else numeric)


@dataclass(frozen=True)
class PreferenceScore:
    """A comparable score with explicit direction, separate from raw objectives."""

    value: float
    direction: str
    reason: str

    def __post_init__(self):
        if (not math.isfinite(float(self.value)) or self.direction not in {"minimize", "maximize"}
                or not isinstance(self.reason, str) or not self.reason.strip()):
            raise PreferenceContractError("Preference score needs a finite value, direction and reason")

    def minimization_delta(self) -> float:
        return float(self.value) if self.direction == "minimize" else -float(self.value)


class PopulationDiversityPreference:
    """Nearest-member novelty, population mean novelty, or its transition gain."""

    supported_scopes = (PreferenceScope.CANDIDATE_IN_UNIT, PreferenceScope.UNIT,
                        PreferenceScope.UNIT_TRANSITION)

    @staticmethod
    def _population(view):
        if not isinstance(view, PopulationView):
            raise PreferenceContractError("Diversity requires an explicitly bound PopulationView")
        return view.population

    def _diversity(self, view):
        population = self._population(view)
        if len(population) < 2:
            return 0.0
        distances = np.array(view.pairwise_distances(), copy=True)
        np.fill_diagonal(distances, np.inf)
        return float(np.mean(np.min(distances, axis=1)))

    def evaluate(self, query: PreferenceQuery) -> PreferenceScore:
        if query.scope not in self.supported_scopes:
            raise PreferenceContractError("Diversity needs a Unit dependency")
        population = self._population(query.unit)
        if query.scope == PreferenceScope.CANDIDATE_IN_UNIT:
            if len(population) and population.shape[1] != len(query.numeric_candidate):
                raise PreferenceContractError("Candidate and PopulationView dimensions differ")
            indices = [i for i, token in enumerate(query.unit.candidate_tokens)
                       if query.candidate_token is None or token != query.candidate_token]
            value = (float(np.min(np.linalg.norm(population[indices] - query.numeric_candidate, axis=1)))
                     if indices else 0.0)
            reason = "nearest_other_member_distance"
        elif query.scope == PreferenceScope.UNIT:
            value, reason = self._diversity(query.unit), "mean_nearest_member_distance"
        else:
            value = self._diversity(query.proposed_unit) - self._diversity(query.unit)
            reason = "population_diversity_gain"
        return PreferenceScore(value, "maximize", reason)


class UnitPreferenceBias(AlgorithmicBias):
    """Explicit candidate-in-Unit bridge into the existing selection projection.

    The view provider is a local read dependency, not a context/store key or a
    checkpoint object graph. Its Unit is checkpointed by the owning Adapter.
    Unit/transition scores are consumed explicitly by Adapter policies instead.
    """

    cacheable = False
    uses_candidate_semantics = True
    objective_independent = True
    state_recovery_level = "L0"
    state_recovery_notes = "Validates preference assembly identity; Unit state is restored by its Adapter."
    context_notes = "Reads an explicitly bound detached Unit view; emits selection guidance."

    def __init__(self, preference, view_provider: Callable, *, name="unit_preference", weight=0.1,
                 apply_to_paths=()):
        super().__init__(name, weight, adaptive=False)
        if PreferenceScope.CANDIDATE_IN_UNIT not in preference.supported_scopes or not callable(view_provider):
            raise PreferenceContractError("UnitPreferenceBias requires a candidate-in-Unit policy and view provider")
        self.preference = preference
        self.view_provider = view_provider
        self._binding_identity = None
        self.apply_to_paths = self._validate_paths(apply_to_paths)

    @staticmethod
    def _validate_paths(paths):
        from ..adapters.strategy_task import _path
        if isinstance(paths, (str, bytes)):
            raise PreferenceContractError("apply_to_paths requires a sequence of instance paths")
        try:
            values = tuple(_path(path) for path in paths)
        except (TypeError, ValueError) as exc:
            raise PreferenceContractError("Invalid Unit preference candidate scope") from exc
        if len(set(values)) != len(values):
            raise PreferenceContractError("Unit preference candidate scopes must be unique")
        return values

    @classmethod
    def from_adapter(cls, preference, adapter, *, owner_path, **kwargs):
        if isinstance(owner_path, str):
            raise PreferenceContractError("owner_path must contain instance segments, not a flat string")
        path = tuple(owner_path)
        # Validate assembly before the first evaluation.
        view = adapter.preference_view(owner_path=path)
        bias = cls(preference, lambda context: adapter.preference_view(owner_path=path), **kwargs)
        bias._binding_identity = {"owner_path": list(path), "unit_id": view.unit_id, "schema": view.schema.as_dict()}
        return bias

    def validate_contract(self):
        if not callable(self.view_provider) or PreferenceScope.CANDIDATE_IN_UNIT not in self.preference.supported_scopes:
            raise PreferenceContractError("Invalid candidate-in-Unit preference binding")
        self._validate_paths(self.apply_to_paths)

    def get_state(self):
        return {"binding": self._binding_identity,
                "policy_type": f"{type(self.preference).__module__}.{type(self.preference).__qualname__}",
                "apply_to_paths": [list(path) for path in self.apply_to_paths]}

    def set_state(self, state):
        if state != self.get_state():
            raise PreferenceContractError("Unit preference checkpoint binding/policy differs from assembly")

    def compute(self, x, context):
        try:
            state = getattr(context, "candidate_state", None)
            candidate = state if isinstance(state, UnknownState) else x
            if self.apply_to_paths:
                from ..adapters.strategy_task import StrategyOrigin
                origins = StrategyOrigin.from_candidate(candidate) if isinstance(candidate, UnknownState) else ()
                if not any(origin.owner_path[:len(path)] == path
                           for origin in origins for path in self.apply_to_paths):
                    return 0.0
            view = self.view_provider(context)
            if self._binding_identity is not None:
                observed = {"owner_path": list(view.owner_path), "unit_id": view.unit_id,
                            "schema": view.schema.as_dict()}
                if observed != self._binding_identity:
                    raise PreferenceContractError("Unit preference dependency changed its bound identity")
            query = PreferenceQuery(PreferenceScope.CANDIDATE_IN_UNIT, candidate=candidate,
                                    candidate_token=getattr(context, "candidate_token", None),
                                    unit=view)
            score = self.preference.evaluate(query)
            if not isinstance(score, PreferenceScore):
                raise PreferenceContractError("Unit preference must return a PreferenceScore")
            return score.minimization_delta()
        except PreferenceContractError:
            raise
        except Exception as exc:
            raise PreferenceContractError(f"Unit preference {self.name} failed") from exc
