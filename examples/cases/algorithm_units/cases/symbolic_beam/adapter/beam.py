"""Beam 扩展、去重和选择；结构由算法管线构建。"""
from __future__ import annotations
from typing import Any, Dict, Iterable, Sequence
import numpy as np
from nsgablack.adapters.unit_backed import UnitBackedAdapter, UnitField
from ..pipeline.beam_units import BeamUnitBuilder

class JointBeamAdapter(UnitBackedAdapter):
    """Joint bundle expansion and beam selection."""

    unit_builder_type = BeamUnitBuilder
    unit_build_operations = ("initialize", "layout")
    unit_schema = BeamUnitBuilder.unit_type.schema
    _beam_masks = UnitField("masks")
    state_recovery_level = "L1"
    state_recovery_notes = "Restores beam masks and feature layout via the Unit codec."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Beam state stays in the Unit; domain residual and ranking operations come from Problem."

    def __init__(
        self,
        *,
        beam_width: int = 16,
        shortlist_size: int = 64,
        expansions_per_state: int = 6,
        bundle_size: int = 3,
        max_candidates: int = 320,
        objective1_weight: float = 0.02,
        violation_weight: float = 1e6,
        unit_binding=None,
    ) -> None:
        super().__init__(name="joint_beam_demo", unit_binding=unit_binding)
        self.beam_width = max(1, int(beam_width))
        self.shortlist_size = max(4, int(shortlist_size))
        self.expansions_per_state = max(1, int(expansions_per_state))
        self.bundle_size = max(1, int(bundle_size))
        self.max_candidates = max(self.beam_width, int(max_candidates))
        self.objective1_weight = float(objective1_weight)
        self.violation_weight = float(violation_weight)
        self._beam_masks: list[np.ndarray] = []

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        problem = getattr(control, "problem", None)
        if problem is None:
            return []
        if not self._beam_masks:
            self._beam_masks = self._bootstrap(problem)
        out: list[np.ndarray] = []
        seen: set[bytes] = set()
        for parent in self._beam_masks[: self.beam_width]:
            residual = np.asarray(problem.residual_from_mask(parent), dtype=float).reshape(-1)
            shortlist = np.asarray(
                problem.rank_candidates_by_residual(
                    residual,
                    exclude_mask=parent,
                    top_n=self.shortlist_size,
                ),
                dtype=int,
            )
            produced = 0
            for anchor in shortlist:
                if produced >= self.expansions_per_state:
                    break
                child = np.asarray(parent, dtype=bool).copy()
                child[int(anchor)] = True
                if self.bundle_size > 1:
                    follow = [int(v) for v in shortlist if int(v) != int(anchor)]
                    bundle = problem.omp_bundle_from_shortlist(
                        child,
                        follow,
                        bundle_size=self.bundle_size - 1,
                    )
                    for idx in bundle:
                        child[int(idx)] = True
                safe = np.asarray(problem.decode_mask(problem.encode_mask(child)), dtype=bool)
                key = self._mask_key(safe)
                if key in seen:
                    continue
                seen.add(key)
                out.append(np.asarray(problem.encode_mask(safe), dtype=float))
                produced += 1
                if len(out) >= self.max_candidates:
                    break
            if len(out) >= self.max_candidates:
                break
        if not out:
            out = [np.asarray(problem.encode_mask(mask), dtype=float) for mask in self._beam_masks[: self.beam_width]]
        return out

    def update(self, control: Any, candidates: Sequence[np.ndarray], feedback, context: Dict[str, Any]) -> None:
        objectives, violations = feedback
        _ = control
        _ = context
        if candidates is None or len(candidates) == 0:
            return
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if vio.shape[0] != obj.shape[0]:
            vio = np.zeros((obj.shape[0],), dtype=float)
        score = obj[:, 0].copy()
        if obj.shape[1] > 1:
            score += self.objective1_weight * obj[:, 1]
        score += self.violation_weight * np.maximum(vio, 0.0)
        order = np.argsort(score)
        problem = getattr(control, "problem", None)
        if problem is None:
            return
        beam: list[np.ndarray] = []
        seen: set[bytes] = set()
        for i in order:
            safe = np.asarray(problem.decode_mask(candidates[int(i)]), dtype=bool)
            key = self._mask_key(safe)
            if key in seen:
                continue
            seen.add(key)
            beam.append(safe)
            if len(beam) >= self.beam_width:
                break
        if beam:
            self._beam_masks = beam

    def _bootstrap(self, problem: SymbolicPoolProblem) -> list[np.ndarray]:
        self.rebuild_unit("layout", dimension=int(problem.dimension))
        base = self.algorithm_unit.empty_mask.copy()
        residual = np.asarray(problem.residual_from_mask(base), dtype=float).reshape(-1)
        shortlist = np.asarray(
            problem.rank_candidates_by_residual(
                residual,
                exclude_mask=base,
                top_n=max(self.shortlist_size, self.beam_width),
            ),
            dtype=int,
        )
        beam: list[np.ndarray] = []
        seen: set[bytes] = set()
        for anchor in shortlist:
            child = base.copy()
            child[int(anchor)] = True
            if self.bundle_size > 1:
                follow = [int(v) for v in shortlist if int(v) != int(anchor)]
                bundle = problem.omp_bundle_from_shortlist(
                    child,
                    follow,
                    bundle_size=self.bundle_size - 1,
                )
                for idx in bundle:
                    child[int(idx)] = True
            safe = np.asarray(problem.decode_mask(problem.encode_mask(child)), dtype=bool)
            key = self._mask_key(safe)
            if key in seen:
                continue
            seen.add(key)
            beam.append(safe)
            if len(beam) >= self.beam_width:
                break
        return beam or [base]

    @staticmethod
    def _mask_key(mask: np.ndarray) -> bytes:
        packed = np.packbits(np.asarray(mask, dtype=np.uint8), bitorder="little")
        return bytes(packed.tolist())



def build_adapter(args, *, unit_binding=None):
    adapter = JointBeamAdapter(
        unit_binding=unit_binding,
        beam_width=int(args.beam_width),
        shortlist_size=int(args.shortlist_size),
        expansions_per_state=int(args.expansions_per_state),
        bundle_size=int(args.bundle_size),
        max_candidates=int(args.max_candidates),
        objective1_weight=float(args.objective1_weight),
    )
    return adapter
