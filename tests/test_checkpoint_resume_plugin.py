from __future__ import annotations

import os
from pathlib import Path

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

    # Loaded state should already place solver at saved generation.
    assert solver_b.generation >= 4
    before_eval = int(getattr(solver_b, "evaluation_count", 0))
    result_b = solver_b.run(return_dict=True)
    assert int(result_b["generation"]) == 6
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
