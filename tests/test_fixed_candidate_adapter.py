from __future__ import annotations

import numpy as np
import pytest

from nsgablack.adapters import FixedCandidateAdapter


class _Control:
    def __init__(self) -> None:
        self.calls = 0

    def init_candidate(self, context):
        self.calls += 1
        assert context["run"] == "fixed"
        return np.asarray([1.0, 2.0])


def test_fixed_candidate_adapter_proposes_one_representation_candidate() -> None:
    control = _Control()
    adapter = FixedCandidateAdapter()

    candidates = adapter.propose(control, {"run": "fixed"})

    assert control.calls == 1
    assert len(candidates) == 1
    np.testing.assert_array_equal(candidates[0], np.asarray([1.0, 2.0]))


def test_fixed_candidate_adapter_accepts_exactly_one_feedback_row() -> None:
    adapter = FixedCandidateAdapter()
    candidate = np.asarray([1.0])

    adapter.update(None, [candidate], ([[0.25]], [[0.0]]), {})

    with pytest.raises(ValueError, match="exactly one candidate"):
        adapter.update(None, [candidate, candidate], ([[0.25], [0.5]], [[0.0], [0.0]]), {})

    with pytest.raises(ValueError, match="exactly one feedback row"):
        adapter.update(None, [candidate], ([], []), {})
