from __future__ import annotations

import numpy as np
import pytest

from blackbase.types import CandidateBatch, UnknownState
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver


class _TwoDimensionalProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="candidate_population_semantics",
            dimension=2,
            bounds={"x0": (-1.0, 1.0), "x1": (-1.0, 1.0)},
            objectives=("score",),
        )

    def evaluate(self, x):
        return float(np.sum(np.asarray(x, dtype=float) ** 2))


def _source(solver: ComposableSolver):
    states = (
        UnknownState([0.0, 0.0], metadata={"architecture": "a"}),
        UnknownState([0.0, 0.0], metadata={"architecture": "b"}),
    )
    provenance = solver.prepare_candidate_provenance(states)
    batch = CandidateBatch.from_candidates(
        states,
        candidate_tokens=tuple(item.candidate_token for item in provenance),
    )
    _rows, semantic_provenance = solver.bind_candidate_batch(
        batch,
        provenance,
        activate=False,
    )
    return batch, tuple(semantic_provenance)


def test_candidate_population_selection_follows_tokens_not_equal_numeric_rows() -> None:
    solver = ComposableSolver(problem=_TwoDimensionalProblem())
    solver.prepare_fresh_run()
    source_batch, provenance = _source(solver)

    committed = solver.commit_candidate_population(
        source_batch.numeric_matrix[[1, 0]],
        (
            source_batch.candidate_tokens[1],
            source_batch.candidate_tokens[0],
        ),
        sources=((source_batch, provenance),),
    )

    assert committed.semantic_states[0].metadata["architecture"] == "b"
    assert committed.semantic_states[1].metadata["architecture"] == "a"
    assert committed.candidate_tokens == (
        provenance[1].candidate_token,
        provenance[0].candidate_token,
    )


def test_semantic_population_rejects_selection_without_lineage_tokens() -> None:
    solver = ComposableSolver(problem=_TwoDimensionalProblem())
    solver.prepare_fresh_run()
    source_batch, provenance = _source(solver)

    with pytest.raises(ValueError, match="must preserve candidate tokens"):
        solver.commit_candidate_population(
            source_batch.numeric_matrix,
            None,
            sources=((source_batch, provenance),),
        )


def test_candidate_population_checkpoint_roundtrip_preserves_semantic_identity() -> None:
    source = ComposableSolver(problem=_TwoDimensionalProblem())
    source.prepare_fresh_run()
    source_batch, provenance = _source(source)
    committed = source.commit_candidate_population(
        source_batch.numeric_matrix,
        source_batch.candidate_tokens,
        sources=((source_batch, provenance),),
    )
    payload = source.export_candidate_population_checkpoint_state()

    restored = ComposableSolver(problem=_TwoDimensionalProblem())
    restored.population = np.array(committed.numeric_matrix, copy=True)
    restored.restore_candidate_population_checkpoint_state(payload)

    restored_batch = restored.get_candidate_population_batch()
    assert restored_batch is not None
    assert restored_batch.candidate_tokens == committed.candidate_tokens
    assert [
        item.metadata["architecture"] for item in restored_batch.semantic_states
    ] == ["a", "b"]


def test_numeric_population_writer_invalidates_mismatched_semantic_population() -> None:
    solver = ComposableSolver(problem=_TwoDimensionalProblem())
    solver.prepare_fresh_run()
    source_batch, provenance = _source(solver)
    solver.commit_candidate_population(
        source_batch.numeric_matrix,
        source_batch.candidate_tokens,
        sources=((source_batch, provenance),),
    )

    assert solver.write_population_snapshot(
        np.asarray([[0.5, 0.5]], dtype=float),
        np.asarray([[0.5]], dtype=float),
        np.asarray([0.0], dtype=float),
    )

    assert solver.get_candidate_population_batch() is None
    assert solver.get_candidate_population_provenance() == ()


def test_mutate_creates_child_token_and_repair_preserves_it() -> None:
    class _SemanticPipeline:
        mutator = object()

        def mutate(self, candidate, context):
            del context
            state = candidate if isinstance(candidate, UnknownState) else UnknownState(candidate)
            return UnknownState(
                state.as_array() + 1.0,
                metadata={**dict(state.metadata), "mutated": True},
            )

        def repair(self, candidate, context):
            del context
            state = candidate if isinstance(candidate, UnknownState) else UnknownState(candidate)
            return UnknownState(
                np.clip(state.as_array(), -1.0, 1.0),
                metadata={**dict(state.metadata), "repaired": True},
            )

    solver = ComposableSolver(
        problem=_TwoDimensionalProblem(),
        representation_pipeline=_SemanticPipeline(),
    )
    solver.prepare_fresh_run()
    original = UnknownState([0.5, 0.5], metadata={"architecture": "a"})

    mutated = solver.mutate_candidate(original)
    mutated_provenance = solver.candidate_provenance_for(mutated)
    original_provenance = solver.candidate_provenance_for(original)
    assert isinstance(mutated, UnknownState)
    assert mutated_provenance is not None
    assert original_provenance is not None
    assert mutated_provenance.candidate_token != original_provenance.candidate_token
    assert mutated_provenance.parent_token == original_provenance.candidate_token
    assert mutated_provenance.transform_stage == "mutate"

    repaired = solver.repair_candidate(mutated)
    repaired_provenance = solver.candidate_provenance_for(repaired)
    assert isinstance(repaired, UnknownState)
    assert repaired.metadata["mutated"] is True
    assert repaired.metadata["repaired"] is True
    assert repaired_provenance is not None
    assert repaired_provenance.candidate_token == mutated_provenance.candidate_token
    assert repaired_provenance.parent_token == original_provenance.candidate_token
    assert repaired_provenance.transform_stage == "repair"


def test_unknown_state_repair_creates_lineage_without_registered_input() -> None:
    class _RepairOnlyPipeline:
        def repair(self, candidate, context):
            del candidate, context
            return UnknownState([0.0, 0.0], metadata={"repaired": "semantic"})

    solver = ComposableSolver(
        problem=_TwoDimensionalProblem(),
        representation_pipeline=_RepairOnlyPipeline(),
    )
    solver.prepare_fresh_run()
    repaired = solver.repair_candidate(np.asarray([2.0, 2.0]))
    provenance = solver.candidate_provenance_for(repaired)

    assert isinstance(repaired, UnknownState)
    assert provenance is not None
    assert provenance.transform_stage == "repair"
    assert repaired.metadata["repaired"] == "semantic"
