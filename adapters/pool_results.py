"""Shared delivery evidence for single-trajectory pool refiners.

Units still own algorithm working values. This module records which evaluated
pool version was selected, freezes the comparison frame, and preserves source
identity when the working value is projected back into a proposal.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from blackbase.types import UnknownState

from ..core.state.incumbent import CandidateProvenance
from ..core.state.pool_views import ObjectiveProjection
from ..core.state.solution_pool import SolutionRef
from ..units.contracts import candidate_array


@dataclass(frozen=True)
class PoolSelection:
    score: float
    violation: float
    ref: SolutionRef | None
    provenance: CandidateProvenance | None
    metadata: dict
    semantic: bool = False

    def as_dict(self):
        return dict(score=self.score, violation=self.violation,
                    ref=None if self.ref is None else self.ref.as_dict(),
                    provenance=None if self.provenance is None else self.provenance.as_dict(),
                    metadata=copy.deepcopy(self.metadata), semantic=self.semantic)

    @classmethod
    def from_dict(cls, value):
        score, violation = float(value["score"]), float(value["violation"])
        if not np.isfinite(score) or not np.isfinite(violation):
            raise ValueError("pool refinement selection requires finite feedback")
        ref = None if value["ref"] is None else SolutionRef.from_dict(dict(value["ref"]))
        provenance = (None if value["provenance"] is None
                      else CandidateProvenance.from_dict(dict(value["provenance"])))
        if ref is not None and (provenance is None or provenance.candidate_token != ref.candidate_token):
            raise ValueError("pool refinement reference differs from its candidate provenance")
        semantic = value.get("semantic", bool(value["metadata"]))
        if type(semantic) is not bool:
            raise ValueError("pool selection semantic kind must be boolean")
        return cls(score, violation, ref, provenance, copy.deepcopy(dict(value["metadata"])), semantic)


class PoolRefinementState:
    """A task's current selection and best evaluated result, with exact refs."""

    def __init__(self):
        self.projection = None
        self.frame_bound = False
        self.current: PoolSelection | None = None
        self.best: PoolSelection | None = None
        self.seed_provenance = None
        self.seed_metadata = {}
        self.seed_semantic = False

    @staticmethod
    def _candidate_details(control, candidate, index=None):
        lookup = getattr(control, "candidate_provenance_for", None)
        provenance = lookup(candidate) if callable(lookup) else None
        indexed = provenance is None and index is not None
        if indexed and callable(lookup):
            provenance = lookup(candidate, candidate_index=index)
        semantic = candidate
        resolver = getattr(control, "semantic_candidate_state", None)
        if callable(resolver) and not isinstance(candidate, UnknownState) and provenance is not None:
            semantic = resolver(candidate, **({"candidate_index": index} if indexed else {}))
        metadata = semantic.as_dict()["metadata"] if isinstance(semantic, UnknownState) else {}
        return provenance, metadata, semantic

    def remember_seed(self, control, candidate):
        provenance, metadata, semantic = self._candidate_details(control, candidate)
        self.seed_provenance = provenance
        self.seed_metadata = copy.deepcopy(metadata)
        self.seed_semantic = isinstance(semantic, UnknownState)

    def project_current(self, control, candidate, *, semantic=False):
        selected = self.current
        provenance = self.seed_provenance if selected is None else selected.provenance
        metadata = self.seed_metadata if selected is None else selected.metadata
        projected = np.array(candidate, copy=True)
        if semantic and (self.seed_semantic if selected is None else selected.semantic):
            projected = UnknownState(projected, copy.deepcopy(metadata))
        binder = getattr(control, "bind_candidate_provenance", None)
        if provenance is not None and callable(binder):
            binder([projected], [provenance], activate=False)
        return projected

    def derive_candidate(self, control, values, *, stage, metadata=None):
        """Bind an algorithm-generated neighbor without reusing its parent's token."""
        selected = self.current
        metadata = (self.seed_metadata if selected is None else selected.metadata) if metadata is None else metadata
        parent = self.seed_provenance if selected is None else selected.provenance
        candidate = np.array(values, copy=True)
        if metadata or (self.seed_semantic if selected is None else selected.semantic):
            candidate = UnknownState(candidate, copy.deepcopy(metadata))
        prepare = getattr(control, "prepare_candidate_provenance", None)
        binder = getattr(control, "bind_candidate_provenance", None)
        if callable(prepare) and callable(binder):
            record, = prepare((candidate,))
            if parent is not None:
                record = replace(record, parent_token=parent.candidate_token,
                                 source_kind="mutation", transform_stage=stage,
                                 metadata={**dict(parent.metadata), **dict(record.metadata)})
            binder((candidate,), (record,), activate=False)
        return candidate

    def scores(self, feedback, ordinary_scores):
        projection = getattr(feedback, "metadata", {}).get("subpool_projection")
        if projection is not None:
            projection = ObjectiveProjection.from_dict(dict(projection)).as_dict()
        if self.frame_bound and projection != self.projection:
            raise ValueError("objective projection changed without restarting its refinement task")
        self.projection, self.frame_bound = projection, True
        objectives, violations = feedback
        violations = np.asarray(violations, dtype=float).reshape(-1)
        # Selection violations intentionally match MOEA/D's comparison view.
        # The separate hard admission policy continues to consume raw evidence.
        values = (np.asarray(objectives, dtype=float)[:, 0] if projection is not None
                  else np.asarray(ordinary_scores(objectives, violations), dtype=float).reshape(-1))
        if len(values) != len(violations) or not np.all(np.isfinite(values)) or not np.all(np.isfinite(violations)):
            raise ValueError("pool refinement requires aligned finite selection feedback")
        return values, violations

    def key(self, score, violation):
        if self.projection is None:
            return (float(score),)
        return (float(violation) > 0, float(violation) if violation > 0 else float(score))

    def improves_current(self, score, violation, fallback_score=None):
        if self.current is None:
            return fallback_score is None or float(score) < float(fallback_score)
        return self.key(score, violation) < self.key(self.current.score, self.current.violation)

    def permits_exploration(self, violation):
        # A projected task never trades worsening feasibility for objective gain.
        return (self.projection is None or self.current is None
                or (violation <= 0 and self.current.violation <= 0)
                or (violation > 0 and violation == self.current.violation))

    def capture(self, control, candidates, feedback, index, score, violation):
        provenance, metadata, semantic = self._candidate_details(control, candidates[index], index)
        items = getattr(feedback, "items", ())
        value = items[index].info.get("accepted_solution_ref") if items else None
        ref = None if value is None else SolutionRef.from_dict(dict(value))
        selected = PoolSelection(float(score), float(violation), ref, provenance, copy.deepcopy(metadata),
                                 isinstance(semantic, UnknownState))
        if ref is not None:
            self.validate(control, selected, candidate=semantic)
        return selected

    def observe_best(self, control, candidates, feedback, index, score, violation):
        if self.best is None or self.key(score, violation) < self.key(self.best.score, self.best.violation):
            self.best = self.capture(control, candidates, feedback, index, score, violation)
            return True
        return False

    @staticmethod
    def validate(control, selected, *, candidate=None):
        if selected.ref is None:
            raise ValueError("refinement result requires an exact accepted solution reference")
        if selected.provenance is None or selected.ref.candidate_token != selected.provenance.candidate_token:
            raise ValueError("selected solution reference does not match its candidate token")
        stored = control.solution_pool.read((selected.ref,), allow_pending=True).semantic_states[0]
        metadata = stored.as_dict()["metadata"] if isinstance(stored, UnknownState) else {}
        if metadata != selected.metadata:
            raise ValueError("selected solution reference differs from its semantic metadata")
        if candidate is not None and not np.array_equal(candidate_array(stored), candidate_array(candidate), equal_nan=True):
            raise ValueError("selected solution reference differs from its candidate values")

    def roots(self, control):
        refs = []
        for selected in (self.current, self.best):
            if selected is None:
                continue
            if selected.ref is not None:
                self.validate(control, selected)
                refs.append(selected.ref)
            elif selected.provenance is not None:
                raise ValueError("selected pool candidate requires its exact accepted solution reference")
        return tuple(dict.fromkeys(refs))

    def results(self, control):
        if self.best is None:
            return ()
        self.validate(control, self.best)
        return (self.best.ref,)

    def as_dict(self):
        return dict(schema="nsgablack.pool_refinement_result/v1", projection=copy.deepcopy(self.projection),
                    frame_bound=self.frame_bound,
                    current=None if self.current is None else self.current.as_dict(),
                    best=None if self.best is None else self.best.as_dict(),
                    seed_provenance=None if self.seed_provenance is None else self.seed_provenance.as_dict(),
                    seed_metadata=copy.deepcopy(self.seed_metadata), seed_semantic=self.seed_semantic)

    @classmethod
    def from_dict(cls, value):
        result = cls()
        if value is None:
            return result
        if value.get("schema") != "nsgablack.pool_refinement_result/v1":
            raise ValueError("unsupported pool refinement result state")
        projection = value.get("projection")
        result.projection = None if projection is None else ObjectiveProjection.from_dict(dict(projection)).as_dict()
        result.frame_bound = value["frame_bound"]
        if type(result.frame_bound) is not bool:
            raise ValueError("pool refinement frame_bound must be boolean")
        result.current = None if value["current"] is None else PoolSelection.from_dict(value["current"])
        result.best = None if value["best"] is None else PoolSelection.from_dict(value["best"])
        if not result.frame_bound and (result.projection is not None or result.current is not None or result.best is not None):
            raise ValueError("pool refinement selections require a frozen comparison frame")
        if result.current is not None and result.best is None:
            raise ValueError("pool refinement current selection requires a best result")
        if result.current is not None and result.key(result.current.score, result.current.violation) < result.key(result.best.score, result.best.violation):
            raise ValueError("pool refinement best result is worse than its current selection")
        if result.projection is not None and any(v is not None and v.ref is None for v in (result.current, result.best)):
            raise ValueError("projected refinement restore requires exact accepted references")
        provenance = value.get("seed_provenance")
        result.seed_provenance = None if provenance is None else CandidateProvenance.from_dict(dict(provenance))
        result.seed_metadata = copy.deepcopy(dict(value.get("seed_metadata", {})))
        result.seed_semantic = value.get("seed_semantic", bool(result.seed_metadata))
        if type(result.seed_semantic) is not bool:
            raise ValueError("pool seed semantic kind must be boolean")
        return result
