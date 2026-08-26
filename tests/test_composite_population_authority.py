from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pytest

from nsgablack.adapters import (
    AlgorithmAdapter,
    CompositeAdapter,
    PopulationPartition,
)
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.evolution_solver import EvolutionSolver


class _PopulationAdapter(AlgorithmAdapter):
    state_recovery_level = "L2"
    state_recovery_notes = "Test L2 population authority."
    population_state_mode = "single"

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.population = np.empty((0, 2), dtype=float)
        self.objectives = np.empty((0, 1), dtype=float)
        self.violations = np.empty((0,), dtype=float)
        self.tokens: tuple[str | None, ...] = ()

    def setup(self, control: Any) -> None:
        del control
        self.population = np.empty((0, 2), dtype=float)
        self.objectives = np.empty((0, 1), dtype=float)
        self.violations = np.empty((0,), dtype=float)
        self.tokens = ()

    def propose(self, control, context):
        del control, context
        return ()

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context

    def get_population_snapshot(self):
        return self.population, self.objectives, self.violations

    def set_population_snapshot(self, population, objectives, violations):
        self.population, self.objectives, self.violations = (
            self.validate_population_snapshot(population, objectives, violations)
        )
        return True

    def get_population_candidate_tokens(self):
        return self.tokens

    def set_population_candidate_tokens(
        self,
        candidate_tokens: Sequence[str | None],
    ) -> bool:
        tokens = tuple(candidate_tokens)
        if len(tokens) != int(self.population.shape[0]):
            raise ValueError("test population token mismatch")
        self.tokens = tokens
        return True

    def get_state(self):
        # Population arrays intentionally remain outside ordinary state.
        return {"name": self.name}

    def set_state(self, state):
        if str(state.get("name", self.name)) != self.name:
            raise ValueError("test adapter identity mismatch")


class _SetupClearsStateAdapter(AlgorithmAdapter):
    state_recovery_level = "L1"
    state_recovery_notes = "Test setup/restore lifecycle ordering."

    def __init__(self) -> None:
        super().__init__(name="setup_clears_state")
        self.value = 0

    def setup(self, control):
        del control
        self.value = 0

    def propose(self, control, context):
        del control, context
        return ()

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context

    def get_state(self):
        return {"value": int(self.value)}

    def set_state(self, state):
        self.value = int(state["value"])


class _SerialSetupStateAdapter(_SetupClearsStateAdapter):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.setup_count = 0

    def setup(self, control):
        self.setup_count += 1
        super().setup(control)


def _set_population(adapter: _PopulationAdapter, offset: float) -> None:
    population = np.asarray(
        [[offset, offset + 1.0], [offset + 2.0, offset + 3.0]],
        dtype=float,
    )
    adapter.set_population_snapshot(
        population,
        np.asarray([[offset], [offset + 1.0]], dtype=float),
        np.asarray([0.0, 0.0], dtype=float),
    )
    adapter.set_population_candidate_tokens(
        (f"token:{offset}:0", f"token:{offset}:1")
    )


def test_composite_keeps_child_populations_as_stable_partitions() -> None:
    first = _PopulationAdapter("first")
    second = _PopulationAdapter("second")
    _set_population(first, 1.0)
    _set_population(second, 10.0)
    composite = CompositeAdapter((first, second))

    assert composite.get_population_snapshot() is None
    partitions = composite.get_population_partitions()
    assert [item.partition_id for item in partitions] == [
        "child:0:first/population",
        "child:1:second/population",
    ]
    assert tuple(partitions[0].candidate_tokens) == ("token:1.0:0", "token:1.0:1")
    assert tuple(partitions[1].candidate_tokens) == ("token:10.0:0", "token:10.0:1")

    restored = CompositeAdapter(
        (_PopulationAdapter("first"), _PopulationAdapter("second"))
    )
    restored.set_state(composite.get_state())
    restored_partitions = restored.get_population_partitions()
    assert [item.as_dict() for item in restored_partitions] == [
        item.as_dict() for item in partitions
    ]


def test_serial_delegate_resolves_the_last_confirmed_population_owner() -> None:
    from nsgablack.adapters.serial_strategy import SerialPhaseSpec, StrategyChainAdapter

    single = _PopulationAdapter("single")
    partitioned = CompositeAdapter(
        (_PopulationAdapter("left"), _PopulationAdapter("right"))
    )
    chain = StrategyChainAdapter(
        (
            SerialPhaseSpec("single", single, steps=1),
            SerialPhaseSpec("partitioned", partitioned, steps=-1),
        )
    )
    chain.setup(object())
    chain._population_owner_idx = 0
    chain._current_idx = 1

    assert chain.resolve_population_state_mode() == "single"
    assert chain.supported_population_state_modes() == frozenset(
        {"single", "partitioned"}
    )

    chain._population_owner_idx = 1
    assert chain.resolve_population_state_mode() == "partitioned"


def test_evolution_solver_rejects_partitioned_adapter_topology(sample_problem) -> None:
    adapter = CompositeAdapter(
        (_PopulationAdapter("left"), _PopulationAdapter("right"))
    )
    solver = EvolutionSolver(sample_problem, adapter=adapter, pop_size=2)

    with pytest.raises(TypeError, match="one authoritative population"):
        solver.setup()


def test_checkpoint_queues_restore_until_after_adapter_setup(
    sample_problem,
    tmp_path: Path,
) -> None:
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "post_setup_restore"
    source_adapter = _SetupClearsStateAdapter()
    source_adapter.value = 7
    source = ComposableSolver(sample_problem, adapter=source_adapter)
    writer = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    source.add_plugin(writer)
    path = writer.save_checkpoint(reason="post-setup-restore")
    assert path is not None

    target_adapter = _SetupClearsStateAdapter()
    target = ComposableSolver(sample_problem, adapter=target_adapter)
    reader = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    target.add_plugin(reader)

    assert reader.resume(str(path)) is True
    assert target_adapter.value == 0
    assert reader.get_report()["resume_audit"]["status"] == "queued"
    target.run(max_steps=0)

    assert target_adapter.value == 7
    audit = reader.get_report()["resume_audit"]
    assert audit["issues"] == [], audit["issues"]
    assert audit["status"] == "restored", audit


def test_population_partition_rejects_misaligned_tokens() -> None:
    try:
        PopulationPartition(
            partition_id="broken",
            population=np.zeros((2, 2)),
            objectives=np.zeros((2, 1)),
            violations=np.zeros((2,)),
            candidate_tokens=("only-one",),
        )
    except ValueError as exc:
        assert "tokens" in str(exc)
    else:  # pragma: no cover - contract guard
        raise AssertionError("misaligned partition tokens were accepted")


def test_serial_restore_sets_up_target_phase_before_applying_state() -> None:
    from nsgablack.adapters.serial_strategy import SerialPhaseSpec, StrategyChainAdapter

    source_first = _SerialSetupStateAdapter("first")
    source_second = _SerialSetupStateAdapter("second")
    source = StrategyChainAdapter(
        (
            SerialPhaseSpec("first", source_first, steps=1),
            SerialPhaseSpec("second", source_second, steps=-1),
        )
    )
    source.setup(object())
    source._current_idx = 1
    source_second.value = 17
    state = source.get_state()

    target_first = _SerialSetupStateAdapter("first")
    target_second = _SerialSetupStateAdapter("second")
    target = StrategyChainAdapter(
        (
            SerialPhaseSpec("first", target_first, steps=1),
            SerialPhaseSpec("second", target_second, steps=-1),
        )
    )
    target.setup(object())
    target.set_state(state)

    assert target_first.setup_count == 1
    assert target_second.setup_count == 1
    assert target._current_idx == 1
    assert target_second.value == 17
    target._advance_phase(object())
    assert target_second.setup_count == 1

    mismatched = dict(state)
    mismatched["phase_names"] = ["renamed", "second"]
    with pytest.raises(ValueError, match="phase identity mismatch"):
        target.set_state(mismatched)


def test_run_progress_rejects_another_logical_run(sample_problem) -> None:
    solver = ComposableSolver(sample_problem)
    solver._active_run_id = "run:current"

    with pytest.raises(ValueError, match="different logical run"):
        solver.restore_run_progress_state(
            {
                "schema": "nsgablack.run_progress/v1",
                "steps_completed": 2,
                "elapsed_seconds": 1.0,
                "deadline_remaining_seconds": None,
                "run_id": "run:other",
            }
        )


def test_candidate_partition_restore_rejects_lineage_token_mismatch(
    sample_problem,
) -> None:
    solver = ComposableSolver(sample_problem)
    payload = {
        "schema": "nsgablack.candidate_population_partitions/v1",
        "authority_mode": "partitioned",
        "partitions": [
            {
                "partition": PopulationPartition(
                    partition_id="child/population",
                    population=np.asarray([[1.0, 2.0]]),
                    objectives=np.asarray([[3.0]]),
                    violations=np.asarray([0.0]),
                    candidate_tokens=("token:batch",),
                ).as_dict(),
                "batch": {
                    "semantic_states": [
                        {"values": [1.0, 2.0], "metadata": {}}
                    ],
                    "numeric_matrix": [[1.0, 2.0]],
                    "candidate_tokens": ["token:batch"],
                },
                "provenance": [
                    {
                        "candidate_token": "token:other",
                        "source_kind": "test",
                    }
                ],
            }
        ],
    }

    with pytest.raises(ValueError, match="token disagrees with lineage"):
        solver.restore_candidate_population_partitions_checkpoint_state(payload)
