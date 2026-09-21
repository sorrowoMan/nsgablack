from __future__ import annotations

import numpy as np

from nsgablack.adapters import (
    AlgorithmAdapter,
    EliteRetentionAdapter,
    EliteRetentionConfig,
)
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.context_contracts import ContextContract, get_component_contract


class _Inner(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__("inner")
        self.updated = None

    def propose(self, control, context):
        del control, context
        return (np.asarray([9.0]), np.asarray([8.0]))

    def update(self, control, candidates, feedback, context):
        del control, context
        self.updated = (tuple(np.asarray(item) for item in candidates), feedback)

    def get_state(self):
        return {}

    def set_state(self, state):
        del state


class _Control:
    def fork_rng(self, name):
        del name
        return np.random.default_rng(7)

    def mutate_candidate(self, candidate, context):
        del context
        return np.asarray(candidate, dtype=float) + 0.5

    def repair_candidate(self, candidate, context):
        del context
        return np.asarray(candidate, dtype=float)


def test_elite_retention_wrapper_exposes_context_contract() -> None:
    contract = get_component_contract(EliteRetentionAdapter(_Inner()))

    assert isinstance(contract, ContextContract)


def test_elite_candidates_are_injected_before_canonical_evaluation() -> None:
    inner = _Inner()
    adapter = EliteRetentionAdapter(
        inner,
        EliteRetentionConfig(
            retention_probability=1.0,
            retention_ratio=0.5,
            history_size=2,
        ),
    )
    control = _Control()
    adapter.setup(control)
    feedback = OptimizationFeedbackBatch.from_arrays(
        np.asarray([[1.0], [2.0]]),
        np.asarray([0.0, 0.0]),
    )
    adapter.update(
        control,
        (np.asarray([1.0]), np.asarray([2.0])),
        feedback,
        {},
    )

    proposed = adapter.propose(control, {})

    assert len(proposed) == 2
    assert np.asarray(proposed[-1]).tolist() in ([1.5], [2.5])
    assert np.asarray(proposed[-1]).tolist() != [8.0]
    assert inner.updated is not None


def test_elite_archive_rolls_back_with_step_transaction() -> None:
    adapter = EliteRetentionAdapter(
        _Inner(),
        EliteRetentionConfig(history_size=2),
    )
    control = _Control()
    adapter.setup(control)
    transaction = adapter.begin_step_transaction()
    adapter._archive.append(
        {
            "candidate": np.asarray([4.0]),
            "objectives": np.asarray([4.0]),
            "violation": 0.0,
            "score": 4.0,
        }
    )

    transaction.rollback()

    assert adapter._archive == []
