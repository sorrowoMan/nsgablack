from __future__ import annotations

import numpy as np
import pytest

from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import AlgorithmAdapter, PopulationPartition
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.solver_helpers import validate_population_snapshot_v2
from nsgablack.plugins.system.checkpoint_resume import (
    CheckpointResumeConfig,
    CheckpointResumePlugin,
)


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


class _PartitionAliasAdapter(AlgorithmAdapter):
    population_state_mode = "partitioned"
    state_recovery_level = "L2"

    def __init__(self, *, accept_writeback: bool = True) -> None:
        super().__init__(name="partition_alias")
        self.accept_writeback = bool(accept_writeback)
        self.partitions: tuple[PopulationPartition, ...] = ()
        self.writeback_count = 0

    def propose(self, control, context):
        del control, context
        return (UnknownState([0.0, 0.0], metadata={"architecture": "shared"}),)

    def update(self, control, candidates, feedback, context):
        del context
        if self.partitions:
            return
        token = self.candidate_tokens_for(control, candidates)[0]
        objectives, violations = feedback
        population = np.asarray(candidates, dtype=float)
        self.partitions = (
            PopulationPartition(
                partition_id="explorer/population",
                population=population,
                objectives=objectives,
                violations=violations,
                candidate_tokens=(token,),
                owner=self.name,
            ),
            PopulationPartition(
                partition_id="exploiter/population",
                population=population,
                objectives=objectives,
                violations=violations,
                candidate_tokens=(token,),
                owner=self.name,
            ),
        )

    def get_population_partitions(self):
        return self.partitions

    def set_population_partitions(self, partitions):
        if not self.accept_writeback:
            return False
        self.partitions = tuple(partitions)
        self.writeback_count += 1
        return True

    def get_state(self):
        return {
            "accept_writeback": self.accept_writeback,
            "partitions": [partition.as_dict() for partition in self.partitions],
            "writeback_count": self.writeback_count,
        }

    def set_state(self, state):
        self.accept_writeback = bool(state.get("accept_writeback", True))
        self.partitions = tuple(
            PopulationPartition.from_dict(item)
            for item in tuple(state.get("partitions", ()) or ())
        )
        self.writeback_count = int(state.get("writeback_count", 0))


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


def test_candidate_population_derives_slot_alias_for_reused_source_token() -> None:
    solver = ComposableSolver(problem=_TwoDimensionalProblem())
    solver.prepare_fresh_run()
    source_batch, provenance = _source(solver)
    source_token = provenance[0].candidate_token

    committed = solver.commit_candidate_population(
        source_batch.numeric_matrix[[0, 0]],
        (source_token, source_token),
        sources=((source_batch, provenance),),
    )
    committed_provenance = solver.get_candidate_population_provenance()

    assert committed.candidate_tokens[0] == source_token
    assert committed.candidate_tokens[1] != source_token
    assert len(set(committed.candidate_tokens)) == 2
    assert committed_provenance[1].parent_token == source_token
    assert committed_provenance[1].transform_stage == "population_slot_alias"
    assert committed_provenance[1].metadata == provenance[0].metadata
    assert committed.semantic_states[1].metadata == {"architecture": "a"}


def test_partitioned_population_derives_global_slot_alias_for_shared_token() -> None:
    solver = ComposableSolver(
        problem=_TwoDimensionalProblem(),
        adapter=_PartitionAliasAdapter(),
    )
    solver.prepare_fresh_run()
    source_batch, provenance = _source(solver)
    source_token = provenance[0].candidate_token
    population = source_batch.numeric_matrix[[0]]
    objectives = np.asarray([[0.0]], dtype=float)
    violations = np.asarray([0.0], dtype=float)

    solver._commit_candidate_population_partitions(
        (
            PopulationPartition(
                partition_id="explorer/population",
                population=population,
                objectives=objectives,
                violations=violations,
                candidate_tokens=(source_token,),
            ),
            PopulationPartition(
                partition_id="exploiter/population",
                population=population,
                objectives=objectives,
                violations=violations,
                candidate_tokens=(source_token,),
            ),
        ),
        evaluated_batch=source_batch,
        evaluated_provenance=provenance,
        previous_population_batch=None,
        previous_population_provenance=(),
    )
    checkpoint = solver.export_candidate_population_partitions_checkpoint_state()
    assert checkpoint is not None
    first, second = checkpoint["partitions"]
    first_token = first["batch"]["candidate_tokens"][0]
    second_token = second["batch"]["candidate_tokens"][0]

    assert first_token == source_token
    assert second_token != source_token
    assert second["provenance"][0]["parent_token"] == source_token
    assert second["provenance"][0]["transform_stage"] == "population_slot_alias"
    assert second["provenance"][0]["metadata"] == provenance[0].as_dict()["metadata"]
    assert second["batch"]["semantic_states"][0]["metadata"] == {
        "architecture": "a"
    }

    restored = ComposableSolver(problem=_TwoDimensionalProblem())
    restored.restore_candidate_population_partitions_checkpoint_state(checkpoint)
    restored_checkpoint = (
        restored.export_candidate_population_partitions_checkpoint_state()
    )
    assert restored_checkpoint == checkpoint

    solver.population_authority_mode = "partitioned"
    authority_payload = solver._prepare_snapshot_payload(None, None, None)
    assert (
        validate_population_snapshot_v2(
            authority_payload,
            snapshot_schema=solver.snapshot_schema,
            expected_authority_mode="partitioned",
        )
        == "partitioned"
    )


def test_partition_slot_alias_is_stable_across_committed_steps() -> None:
    adapter = _PartitionAliasAdapter()
    solver = ComposableSolver(
        problem=_TwoDimensionalProblem(),
        adapter=adapter,
    )

    solver.step()
    first = solver.export_candidate_population_partitions_checkpoint_state()
    assert first is not None
    first_tokens = tuple(
        item["batch"]["candidate_tokens"][0]
        for item in first["partitions"]
    )

    solver.step()
    second = solver.export_candidate_population_partitions_checkpoint_state()
    assert second is not None
    second_tokens = tuple(
        item["batch"]["candidate_tokens"][0]
        for item in second["partitions"]
    )

    assert len(set(first_tokens)) == 2
    assert second_tokens == first_tokens
    assert tuple(
        partition.candidate_tokens[0]
        for partition in adapter.get_population_partitions()
    ) == first_tokens
    assert adapter.writeback_count == 2


def test_partition_commit_fails_when_adapter_rejects_normalized_writeback() -> None:
    adapter = _PartitionAliasAdapter(accept_writeback=False)
    solver = ComposableSolver(
        problem=_TwoDimensionalProblem(),
        adapter=adapter,
    )

    with pytest.raises(
        RuntimeError,
        match="rejected normalized population partitions",
    ):
        solver.step()

    assert adapter.get_population_partitions() == ()
    assert solver.get_candidate_population_partitions() == {}
    assert solver.get_population_authority_identity() is None


def test_partition_alias_checkpoint_keeps_solver_and_adapter_state_aligned(
    tmp_path,
) -> None:
    store_options = {
        "snapshot_store_backend": "file",
        "snapshot_store_dir": str(tmp_path / "partition-alias-state"),
        "snapshot_store_key_prefix": "partition-alias-checkpoint",
    }
    source_adapter = _PartitionAliasAdapter()
    source = ComposableSolver(
        problem=_TwoDimensionalProblem(),
        adapter=source_adapter,
        **store_options,
    )
    source._active_run_id = "partition-alias-checkpoint-run"
    source.step()
    source.step()

    writer = CheckpointResumePlugin(
        config=CheckpointResumeConfig(save_on_finish=False)
    )
    writer.attach(source)
    payload = writer._build_payload(solver=source, reason="partition-alias")
    solver_partition_state = payload["solver_state"][
        "candidate_population_partitions"
    ]
    solver_partitions = [
        item["partition"] for item in solver_partition_state["partitions"]
    ]

    assert payload["adapter_population_partitions"] == solver_partitions
    assert payload["adapter_state"]["partitions"] == solver_partitions

    target_adapter = _PartitionAliasAdapter()
    target = ComposableSolver(
        problem=_TwoDimensionalProblem(),
        adapter=target_adapter,
        **store_options,
    )
    target.set_snapshot_store(
        source.snapshot_store,
        evaluation_evidence_journal=source.evaluation_evidence_journal,
        authority_store=source.authority_store,
    )
    reader = CheckpointResumePlugin(
        config=CheckpointResumeConfig(save_on_finish=False)
    )
    reader.attach(target)
    reader._restore_payload(solver=target, payload=payload)

    restored = target.export_candidate_population_partitions_checkpoint_state()
    assert restored == solver_partition_state
    assert [
        partition.as_dict()
        for partition in target_adapter.get_population_partitions()
    ] == solver_partitions
    restored_tokens = tuple(
        item["batch"]["candidate_tokens"][0]
        for item in restored["partitions"]
    )

    target.step()
    advanced = target.export_candidate_population_partitions_checkpoint_state()
    assert advanced is not None
    assert tuple(
        item["batch"]["candidate_tokens"][0]
        for item in advanced["partitions"]
    ) == restored_tokens


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
    from blackbase.representation import RepresentationCapabilities
    class _SemanticPipeline:
        representation_capabilities = RepresentationCapabilities(frozenset({"mutate", "repair"}))

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
    from blackbase.representation import RepresentationCapabilities
    class _RepairOnlyPipeline:
        representation_capabilities = RepresentationCapabilities(frozenset({"repair"}))

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
