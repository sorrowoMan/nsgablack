from __future__ import annotations

import numpy as np

from blackbase.contracts import BatchDisposition
from nsgablack.adapters import (
    AStarAdapter,
    DifferentialEvolutionAdapter,
    GradientDescentAdapter,
    MOAStarAdapter,
    MOEADAdapter,
)


def _non_prefix_disposition(proposed_count: int) -> BatchDisposition:
    return BatchDisposition(
        proposed_count=proposed_count,
        accepted_indices=(0, 2),
        reason="test_filter",
    )


def test_de_disposition_keeps_target_state_aligned() -> None:
    adapter = DifferentialEvolutionAdapter()
    adapter._last_target_indices = [10, 11, 12]
    adapter._last_target_scores = np.asarray([1.0, 2.0, 3.0])

    adapter.on_proposal_disposition(None, _non_prefix_disposition(3), {})

    assert adapter._last_target_indices == [10, 12]
    np.testing.assert_array_equal(adapter._last_target_scores, [1.0, 3.0])


def test_moead_disposition_keeps_subproblem_modes_aligned() -> None:
    adapter = MOEADAdapter()
    adapter._pending_indices = [4, 7, 9]
    adapter._pending_modes = ["global", "neighborhood", "global"]

    adapter.on_proposal_disposition(None, _non_prefix_disposition(3), {})

    assert adapter._pending_indices == [4, 9]
    assert adapter._pending_modes == ["global", "global"]


def test_gradient_disposition_preserves_probe_identity() -> None:
    adapter = GradientDescentAdapter()
    adapter._pending_probes = [(2, 1), (2, -1), (5, 1)]

    adapter.on_proposal_disposition(None, _non_prefix_disposition(3), {})

    assert adapter._pending_probes == [(2, 1), (5, 1)]


def test_astar_disposition_keeps_path_metadata_aligned() -> None:
    adapter = AStarAdapter(neighbors=lambda _state, _context: ())
    adapter._pending = [
        {"parent_key": "a", "base_g": 1.0},
        {"parent_key": "b", "base_g": 2.0},
        {"parent_key": "c", "base_g": 3.0},
    ]

    adapter.on_proposal_disposition(None, _non_prefix_disposition(3), {})

    assert [item["parent_key"] for item in adapter._pending] == ["a", "c"]


def test_moa_star_disposition_keeps_path_metadata_aligned() -> None:
    adapter = MOAStarAdapter(neighbors=lambda _state, _context: ())
    adapter._pending = [
        {"parent_key": "a", "base_g": np.asarray([1.0, 2.0])},
        {"parent_key": "b", "base_g": np.asarray([2.0, 3.0])},
        {"parent_key": "c", "base_g": np.asarray([3.0, 4.0])},
    ]

    adapter.on_proposal_disposition(None, _non_prefix_disposition(3), {})

    assert [item["parent_key"] for item in adapter._pending] == ["a", "c"]
