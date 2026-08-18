from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest


def _build_composable_solver(sample_problem):
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-10.0, high=10.0),
        mutator=ContextGaussianMutation(base_sigma=0.3, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-10.0, high=10.0),
    )
    solver = ComposableSolver(
        problem=sample_problem,
        adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=6)),
        representation_pipeline=pipeline,
    )
    return solver


def test_checkpoint_resume_composable_solver(sample_problem, tmp_path: Path):
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "ckpt"
    solver_a = _build_composable_solver(sample_problem)
    solver_a.max_steps = 5
    plugin_a = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_every=1,
            save_on_finish=True,
            keep_last=8,
            auto_resume=False,
        )
    )
    solver_a.add_plugin(plugin_a)
    result_a = solver_a.run()

    assert result_a["steps"] == 5
    assert plugin_a.latest_checkpoint_path is not None
    assert Path(plugin_a.latest_checkpoint_path).exists()

    solver_b = _build_composable_solver(sample_problem)
    solver_b.max_steps = 7
    plugin_b = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_every=1,
            save_on_finish=False,
            keep_last=8,
            auto_resume=True,
            resume_from="latest",
        )
    )
    solver_b.add_plugin(plugin_b)

    result_b = solver_b.run()
    assert plugin_b.last_loaded_path is not None
    assert result_b["steps"] == 7
    assert result_b["resume_from"] >= 1
    assert result_b["steps_executed"] >= 1


def test_checkpoint_roundtrip_preserves_complete_incumbent(
    sample_problem,
    tmp_path: Path,
) -> None:
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "incumbent_ckpt"
    solver_a = _build_composable_solver(sample_problem)
    incumbent_x = np.arange(int(solver_a.dimension), dtype=float)
    solver_a._update_best(
        incumbent_x.reshape(1, -1),
        np.asarray([[1.5, 0.5]]),
        np.asarray([0.0]),
    )
    plugin_a = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    solver_a.add_plugin(plugin_a)
    path = plugin_a.save_checkpoint(reason="incumbent_roundtrip")
    assert path is not None

    solver_b = _build_composable_solver(sample_problem)
    plugin_b = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    solver_b.add_plugin(plugin_b)
    restored_incumbents = []
    original_set_incumbent = solver_b.set_incumbent

    def _record_atomic_restore(incumbent):
        restored_incumbents.append(incumbent)
        return original_set_incumbent(incumbent)

    solver_b.set_incumbent = _record_atomic_restore
    assert plugin_b.resume(str(path)) is True

    assert len(restored_incumbents) == 1
    assert solver_b.get_incumbent() is not None
    assert np.allclose(solver_b.best_x, incumbent_x)
    assert np.allclose(solver_b.best_objectives, [1.5, 0.5])
    assert solver_b.best_constraint_violation == 0.0
    assert solver_b.best_score == 2.0


def test_checkpoint_without_incumbent_clears_target_incumbent(
    sample_problem,
    tmp_path: Path,
) -> None:
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "empty_incumbent_ckpt"
    solver_a = _build_composable_solver(sample_problem)
    plugin_a = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    solver_a.add_plugin(plugin_a)
    path = plugin_a.save_checkpoint(reason="empty_incumbent")
    assert path is not None

    solver_b = _build_composable_solver(sample_problem)
    solver_b._update_best(
        np.zeros((1, int(solver_b.dimension)), dtype=float),
        np.asarray([[1.0, 1.0]]),
        np.asarray([0.0]),
    )
    assert solver_b.get_incumbent() is not None
    plugin_b = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    solver_b.add_plugin(plugin_b)

    assert plugin_b.resume(str(path)) is True
    assert solver_b.get_incumbent() is None
    assert solver_b.best_x is None
    assert solver_b.best_objectives is None


def test_checkpoint_retention_keeps_last_n(sample_problem, tmp_path: Path):
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "retain"
    solver = _build_composable_solver(sample_problem)
    solver.max_steps = 8
    plugin = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_every=1,
            save_on_finish=True,
            keep_last=2,
            auto_resume=False,
        )
    )
    solver.add_plugin(plugin)
    solver.run()

    files = sorted(checkpoint_dir.glob("checkpoint_g*.pkl"))
    assert 1 <= len(files) <= 2


def test_checkpoint_resume_nsga2_solver(sample_problem, tmp_path: Path):
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "nsga_ckpt"

    solver_a = EvolutionSolver(sample_problem)
    solver_a.pop_size = 12
    solver_a.max_generations = 4
    solver_a.enable_progress_log = False
    plugin_a = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_every=1,
            save_on_finish=True,
            keep_last=5,
            auto_resume=False,
        )
    )
    solver_a.add_plugin(plugin_a)
    result_a = solver_a.run(return_dict=True)
    assert int(result_a["generation"]) == 4

    solver_b = EvolutionSolver(sample_problem)
    solver_b.pop_size = 12
    solver_b.max_generations = 6
    solver_b.enable_progress_log = False
    plugin_b = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_every=1,
            save_on_finish=False,
            keep_last=5,
            auto_resume=True,
            resume_from="latest",
        )
    )
    solver_b.add_plugin(plugin_b)

    # Registration only attaches the plugin; resume is a run lifecycle action.
    assert solver_b.generation == 0
    before_eval = int(getattr(solver_b, "evaluation_count", 0))
    result_b = solver_b.run(return_dict=True)
    assert int(result_b["generation"]) == 6
    assert int(result_b["resume_from"]) >= 4
    assert int(getattr(solver_b, "evaluation_count", 0)) >= before_eval


def test_checkpoint_resume_hmac_roundtrip(sample_problem, tmp_path: Path):
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "hmac_ckpt"
    os.environ["NSGABLACK_CHECKPOINT_HMAC_KEY"] = "unit-test-hmac-key"
    try:
        solver_a = EvolutionSolver(sample_problem)
        solver_a.pop_size = 8
        solver_a.max_generations = 2
        solver_a.enable_progress_log = False
        plugin_a = CheckpointResumePlugin(
            config=CheckpointResumeConfig(
                checkpoint_dir=str(checkpoint_dir),
                save_every=1,
                save_on_finish=True,
                keep_last=3,
                auto_resume=False,
            )
        )
        solver_a.add_plugin(plugin_a)
        solver_a.run()
        assert plugin_a.latest_checkpoint_path is not None

        solver_b = EvolutionSolver(sample_problem)
        solver_b.pop_size = 8
        solver_b.max_generations = 3
        solver_b.enable_progress_log = False
        plugin_b = CheckpointResumePlugin(
            config=CheckpointResumeConfig(
                checkpoint_dir=str(checkpoint_dir),
                auto_resume=False,
            )
        )
        solver_b.add_plugin(plugin_b)
        assert plugin_b.resume("latest") is True
    finally:
        os.environ.pop("NSGABLACK_CHECKPOINT_HMAC_KEY", None)


def test_checkpoint_resume_blocks_unsigned_when_hmac_key_present(sample_problem, tmp_path: Path):
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "unsigned_ckpt"
    os.environ.pop("NSGABLACK_CHECKPOINT_HMAC_KEY", None)

    solver_a = EvolutionSolver(sample_problem)
    solver_a.pop_size = 8
    solver_a.max_generations = 2
    solver_a.enable_progress_log = False
    plugin_a = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_every=1,
            save_on_finish=True,
        )
    )
    solver_a.add_plugin(plugin_a)
    solver_a.run()

    os.environ["NSGABLACK_CHECKPOINT_HMAC_KEY"] = "unit-test-hmac-key"
    try:
        solver_b = EvolutionSolver(sample_problem)
        solver_b.pop_size = 8
        solver_b.max_generations = 3
        solver_b.enable_progress_log = False
        plugin_b = CheckpointResumePlugin(
            config=CheckpointResumeConfig(
                checkpoint_dir=str(checkpoint_dir),
                auto_resume=False,
                unsafe_allow_unsigned=False,
            )
        )
        solver_b.add_plugin(plugin_b)
        try:
            plugin_b.resume("latest")
        except ValueError as exc:
            assert "unsigned checkpoint is blocked" in str(exc)
        else:
            raise AssertionError("unsigned checkpoint should be blocked when HMAC key is configured")
    finally:
        os.environ.pop("NSGABLACK_CHECKPOINT_HMAC_KEY", None)


def test_checkpoint_resume_allows_unsigned_when_explicitly_unsafe(sample_problem, tmp_path: Path):
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "unsafe_unsigned_ckpt"
    os.environ.pop("NSGABLACK_CHECKPOINT_HMAC_KEY", None)

    solver_a = EvolutionSolver(sample_problem)
    solver_a.pop_size = 8
    solver_a.max_generations = 2
    solver_a.enable_progress_log = False
    plugin_a = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_every=1,
            save_on_finish=True,
        )
    )
    solver_a.add_plugin(plugin_a)
    solver_a.run()

    os.environ["NSGABLACK_CHECKPOINT_HMAC_KEY"] = "unit-test-hmac-key"
    try:
        solver_b = EvolutionSolver(sample_problem)
        solver_b.pop_size = 8
        solver_b.max_generations = 3
        solver_b.enable_progress_log = False
        plugin_b = CheckpointResumePlugin(
            config=CheckpointResumeConfig(
                checkpoint_dir=str(checkpoint_dir),
                auto_resume=False,
                unsafe_allow_unsigned=True,
            )
        )
        solver_b.add_plugin(plugin_b)
        assert plugin_b.resume("latest") is True
    finally:
        os.environ.pop("NSGABLACK_CHECKPOINT_HMAC_KEY", None)


def test_checkpoint_strict_requires_hmac_and_forbids_unsafe(sample_problem, tmp_path: Path):
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    checkpoint_dir = tmp_path / "strict_ckpt"
    os.environ.pop("NSGABLACK_CHECKPOINT_HMAC_KEY", None)

    solver = EvolutionSolver(sample_problem)
    solver.pop_size = 8
    solver.max_generations = 1
    solver.enable_progress_log = False
    plugin = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            strict=True,
            unsafe_allow_unsigned=False,
        )
    )
    solver.add_plugin(plugin)
    try:
        plugin.save_checkpoint(reason="manual")
    except ValueError as exc:
        assert "strict checkpoint mode requires HMAC key" in str(exc)
    else:
        raise AssertionError("strict checkpoint save must require HMAC key")

    os.environ["NSGABLACK_CHECKPOINT_HMAC_KEY"] = "unit-test-hmac-key"
    try:
        plugin_unsafe = CheckpointResumePlugin(
            config=CheckpointResumeConfig(
                checkpoint_dir=str(checkpoint_dir),
                strict=True,
                unsafe_allow_unsigned=True,
            )
        )
        plugin_unsafe.attach(solver)
        try:
            plugin_unsafe.save_checkpoint(reason="manual")
        except ValueError as exc:
            assert "forbids unsafe_allow_unsigned=True" in str(exc)
        else:
            raise AssertionError("strict checkpoint must forbid unsafe_allow_unsigned=True")
    finally:
        os.environ.pop("NSGABLACK_CHECKPOINT_HMAC_KEY", None)


def test_attach_checkpoint_resume_trust_checkpoint_maps_to_unsafe(sample_problem, tmp_path: Path):
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.utils.wiring import attach_checkpoint_resume

    solver = EvolutionSolver(sample_problem)
    plugin = attach_checkpoint_resume(
        solver,
        checkpoint_dir=str(tmp_path / "suite_ckpt"),
        strict=False,
        trust_checkpoint=True,
    )
    assert bool(plugin.cfg.unsafe_allow_unsigned) is True


def test_attach_checkpoint_resume_strict_conflicts_with_trust_checkpoint(sample_problem, tmp_path: Path):
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.utils.wiring import attach_checkpoint_resume

    solver = EvolutionSolver(sample_problem)
    with pytest.raises(ValueError):
        attach_checkpoint_resume(
            solver,
            checkpoint_dir=str(tmp_path / "suite_ckpt_conflict"),
            strict=True,
            trust_checkpoint=True,
        )


def test_checkpoint_writer_uses_v2_and_carries_incumbent_selection_audit(
    sample_problem,
) -> None:
    from nsgablack.plugins import CheckpointResumePlugin

    solver = _build_composable_solver(sample_problem)
    solver.prepare_fresh_run()
    solver.scalarizer_fallback_count = 3
    solver.result_quality_degraded = True
    plugin = CheckpointResumePlugin()
    plugin.attach(solver)

    payload = plugin._build_payload(solver=solver, reason="schema-test")
    state = payload["solver_state"]

    assert payload["schema"] == "nsgablack.checkpoint.v2"
    assert state["run_sequence"] == 1
    assert state["incumbent_selection"] == {
        "policy_id": "objective_sum/v1",
        "policy_context": {},
        "failure_policy": "raise",
        "fallback_count": 3,
        "result_quality_degraded": True,
        "audit_complete": True,
    }
    assert state["incumbent_projection"] == {
        "incumbent_revision": solver._incumbent_commit.revision,
        "incumbent_context_projection_revision": solver._incumbent_commit.revision,
        "incumbent_context_projection_current": True,
        "incumbent_context_projection_error": None,
    }


def test_checkpoint_roundtrip_restores_scalarizer_audit_and_validates_policy(
    sample_problem,
    tmp_path: Path,
) -> None:
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin

    def failing_scalarizer(objective_row, violation, context):
        del objective_row, violation, context
        raise RuntimeError("expected scalarizer failure")

    checkpoint_dir = tmp_path / "scalarizer_audit"
    solver_a = _build_composable_solver(sample_problem)
    solver_a.set_incumbent_scalarizer(
        failing_scalarizer,
        policy_id="test/failing-scalarizer/v1",
        context={"weights": [0.75, 0.25]},
        failure_policy="fallback_sum",
    )
    solver_a.prepare_fresh_run()
    solver_a._update_best(
        np.zeros((1, int(solver_a.dimension))),
        np.asarray([[2.0, 3.0]]),
        np.asarray([0.0]),
    )
    assert solver_a.scalarizer_fallback_count == 1
    plugin_a = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    plugin_a.attach(solver_a)
    path = plugin_a.save_checkpoint(reason="scalarizer-audit")
    assert path is not None

    solver_b = _build_composable_solver(sample_problem)
    solver_b.set_incumbent_scalarizer(
        failing_scalarizer,
        policy_id="test/failing-scalarizer/v1",
        context={"weights": [0.75, 0.25]},
        failure_policy="fallback_sum",
    )
    plugin_b = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    plugin_b.attach(solver_b)
    assert plugin_b.resume(str(path)) is True
    assert solver_b.scalarizer_fallback_count == 1
    assert solver_b.result_quality_degraded is True
    assert solver_b.scalarizer_audit_complete is True

    mismatched = _build_composable_solver(sample_problem)
    mismatch_plugin = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(checkpoint_dir),
            save_on_finish=False,
        )
    )
    mismatch_plugin.attach(mismatched)
    with pytest.raises(ValueError, match="scalarizer policy mismatch"):
        mismatch_plugin.resume(str(path))
    assert mismatched.get_incumbent() is None


def test_v1_checkpoint_migrates_explicitly_and_marks_scalarizer_audit_unknown(
    sample_problem,
) -> None:
    from nsgablack.plugins import CheckpointResumePlugin

    solver = _build_composable_solver(sample_problem)
    plugin = CheckpointResumePlugin()
    plugin.attach(solver)
    payload_v1 = {
        "schema": "nsgablack.checkpoint.v1",
        "solver_state": {
            "generation": 2,
            "evaluation_count": 5,
            "best_x": np.zeros((int(solver.dimension),), dtype=float),
            "best_objectives": np.asarray([1.0, 2.0]),
            "best_constraint_violation": 0.0,
            "best_score": 3.0,
            "active_run_id": "case-a:solver-run:4:oldnonce",
        },
        "resume_cursor": 2,
        "adapter_state": None,
        "plugin_states": {},
        "rng_state": {},
    }

    plugin._restore_payload(solver=solver, payload=payload_v1)

    assert solver.get_incumbent() is not None
    assert solver._run_sequence == 4
    assert solver.scalarizer_audit_complete is False
    assert solver.result_quality_degraded is None
    restored_run_id = solver._active_run_id
    solver.prepare_fresh_run()
    assert solver._run_sequence == 5
    assert solver._active_run_id != restored_run_id
    assert ":solver-run:5:" in solver._active_run_id


def test_unknown_checkpoint_schema_is_rejected_before_solver_mutation(
    sample_problem,
) -> None:
    from nsgablack.plugins import CheckpointResumePlugin

    solver = _build_composable_solver(sample_problem)
    plugin = CheckpointResumePlugin()
    plugin.attach(solver)
    payload = {
        "schema": "nsgablack.checkpoint.v999",
        "solver_state": {"generation": 99},
    }

    with pytest.raises(ValueError, match="unsupported checkpoint schema"):
        plugin._restore_payload(solver=solver, payload=payload)
    assert solver.generation == 0


def test_checkpoint_writer_rejects_incumbent_selection_split_brain(
    sample_problem,
) -> None:
    from nsgablack.plugins import CheckpointResumePlugin

    solver = _build_composable_solver(sample_problem)
    solver._update_best(
        np.zeros((1, int(solver.dimension))),
        np.asarray([[1.0, 2.0]]),
        np.asarray([0.0]),
    )
    solver.incumbent_scalarizer_id = "changed-after-incumbent/v1"
    plugin = CheckpointResumePlugin()
    plugin.attach(solver)

    with pytest.raises(ValueError, match="incumbent/selection policy mismatch"):
        plugin._build_payload(solver=solver, reason="inconsistent")


def test_checkpoint_restore_rejects_internal_policy_mismatch_before_builder_check(
    sample_problem,
) -> None:
    from nsgablack.plugins import CheckpointResumePlugin

    source = _build_composable_solver(sample_problem)
    source._update_best(
        np.zeros((1, int(source.dimension))),
        np.asarray([[1.0, 2.0]]),
        np.asarray([0.0]),
    )
    source_plugin = CheckpointResumePlugin()
    source_plugin.attach(source)
    payload = source_plugin._build_payload(solver=source, reason="tamper-test")
    payload["solver_state"]["incumbent_selection"]["policy_id"] = "builder-b/v1"
    payload["solver_state"]["incumbent_selection"]["policy_context"] = {
        "weights": [0.25, 0.75]
    }

    def scalarizer(objective_row, violation, context):
        del violation
        return float(np.dot(objective_row, context["weights"]))

    target = _build_composable_solver(sample_problem)
    target.set_incumbent_scalarizer(
        scalarizer,
        policy_id="builder-b/v1",
        context={"weights": [0.25, 0.75]},
    )
    target_plugin = CheckpointResumePlugin()
    target_plugin.attach(target)

    with pytest.raises(ValueError, match="incumbent/selection policy mismatch"):
        target_plugin._restore_payload(solver=target, payload=payload)
    assert target.get_incumbent() is None
    assert target.generation == 0


def test_checkpoint_restore_rejects_internal_policy_context_mismatch(
    sample_problem,
) -> None:
    from nsgablack.plugins import CheckpointResumePlugin

    source = _build_composable_solver(sample_problem)

    def scalarizer(objective_row, violation, context):
        del violation
        return float(np.dot(objective_row, context["weights"]))

    source.set_incumbent_scalarizer(
        scalarizer,
        policy_id="weighted/v1",
        context={"weights": [0.5, 0.5]},
    )
    source._update_best(
        np.zeros((1, int(source.dimension))),
        np.asarray([[1.0, 2.0]]),
        np.asarray([0.0]),
    )
    plugin = CheckpointResumePlugin()
    plugin.attach(source)
    payload = plugin._build_payload(solver=source, reason="context-tamper")
    payload["solver_state"]["incumbent_selection"]["policy_context"] = {
        "weights": [0.9, 0.1]
    }

    with pytest.raises(ValueError, match="policy context mismatch"):
        plugin._restore_payload(solver=source, payload=payload)


def test_checkpoint_restore_recomputes_projection_health_for_live_store(
    sample_problem,
) -> None:
    from blackbase.context import InMemoryContextStore
    from nsgablack.plugins import CheckpointResumePlugin

    class FailingContextStore(InMemoryContextStore):
        def apply_patch(self, values, *, delete_keys=(), ttl_seconds=None):
            raise RuntimeError("restored ContextStore unavailable")

    source = _build_composable_solver(sample_problem)
    source._update_best(
        np.zeros((1, int(source.dimension))),
        np.asarray([[1.0, 2.0]]),
        np.asarray([0.0]),
    )
    source_plugin = CheckpointResumePlugin()
    source_plugin.attach(source)
    payload = source_plugin._build_payload(solver=source, reason="projection-audit")
    saved_audit = payload["solver_state"]["incumbent_projection"]
    assert saved_audit["incumbent_context_projection_current"] is True

    target = _build_composable_solver(sample_problem)
    target.set_context_store(FailingContextStore())
    target_plugin = CheckpointResumePlugin()
    target_plugin.attach(target)
    target_plugin._restore_payload(solver=target, payload=payload)

    live_audit = target.get_incumbent_projection_audit()
    assert target._restored_incumbent_projection_audit == saved_audit
    assert live_audit["incumbent_context_projection_current"] is False
    assert live_audit["incumbent_context_projection_error"] == {
        "revision": live_audit["incumbent_revision"],
        "error_type": "RuntimeError",
        "message": "restored ContextStore unavailable",
    }


def test_checkpoint_rejects_internally_inconsistent_projection_audit(
    sample_problem,
) -> None:
    from nsgablack.plugins import CheckpointResumePlugin

    source = _build_composable_solver(sample_problem)
    plugin = CheckpointResumePlugin()
    plugin.attach(source)
    payload = plugin._build_payload(solver=source, reason="projection-tamper")
    payload["solver_state"]["incumbent_projection"][
        "incumbent_context_projection_current"
    ] = False

    target = _build_composable_solver(sample_problem)
    with pytest.raises(ValueError, match="current flag is inconsistent"):
        plugin._restore_payload(solver=target, payload=payload)
    assert target.get_incumbent() is None
