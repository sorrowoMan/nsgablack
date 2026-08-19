"""Evaluate one representation-owned candidate without inventing a search loop."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from blackbase.contracts import ComponentContract

from ..algorithm_adapter import AlgorithmAdapter


class FixedCandidateAdapter(AlgorithmAdapter):
    """Provider-neutral strategy for one-shot evaluation Cases.

    The Representation owns the candidate and the Problem owns its meaning.
    This Adapter merely routes that candidate through the canonical NSGABlack
    lifecycle, so diagnostic and validation Cases do not need a private
    control loop.
    """

    method_ids = ("evaluation.fixed",)
    context_requires = ()
    context_optional = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Evaluates Representation.init() exactly once per solver step.",
        "Does not mutate, fit, sample, or select a backend.",
    )
    state_recovery_level = "L0"
    state_recovery_notes = "No adapter-owned state; the Solver checkpoint is authoritative."
    contract = ComponentContract(
        name="fixed_candidate",
        supports_gradient=False,
        supports_batch=False,
        supports_resume=True,
        metadata={
            "family": "one_shot",
            "provider_neutral": True,
            "method_ids": method_ids,
        },
    )

    def __init__(self, name: str = "fixed_candidate", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)

    def propose(self, control: Any, context: Mapping[str, Any]) -> Sequence[Any]:
        return (control.init_candidate(context),)

    def update(
        self,
        control: Any,
        candidates: Sequence[Any],
        feedback: Any,
        context: Mapping[str, Any],
    ) -> None:
        del control, context
        if len(tuple(candidates)) != 1:
            raise ValueError("FixedCandidateAdapter requires exactly one candidate")
        objectives, violations = feedback
        if len(objectives) != 1 or len(violations) != 1:
            raise ValueError("FixedCandidateAdapter requires exactly one feedback row")


__all__ = ["FixedCandidateAdapter"]
