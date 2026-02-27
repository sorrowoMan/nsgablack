from __future__ import annotations

from pathlib import Path

from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin, Plugin


class _ExplodingPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Fault-injection plugin for regression testing.",)

    def __init__(self) -> None:
        super().__init__(name="exploding_plugin")
        self.calls = 0

    def on_generation_end(self, generation: int):
        self.calls += 1
        raise RuntimeError("injected generation_end failure")


def _make_solver(sample_problem):
    solver = BlackBoxSolverNSGAII(sample_problem)
    solver.pop_size = 12
    solver.max_generations = 4
    solver.enable_progress_log = False
    return solver


def test_plugin_failure_does_not_abort_solver(sample_problem):
    solver = _make_solver(sample_problem)
    plugin = _ExplodingPlugin()
    solver.add_plugin(plugin)

    result = solver.run(return_dict=True)

    assert int(result["generation"]) == solver.max_generations
    assert plugin.calls >= 1


def test_checkpoint_auto_resume_missing_file_is_tolerated_when_not_strict(sample_problem, tmp_path: Path):
    solver = _make_solver(sample_problem)
    plugin = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(tmp_path / "missing_ckpt"),
            auto_resume=True,
            resume_from="does_not_exist.pkl",
            strict=False,
        )
    )
    solver.add_plugin(plugin)

    result = solver.run(return_dict=True)
    assert int(result["generation"]) == solver.max_generations


def test_checkpoint_auto_resume_missing_file_fails_fast_when_strict(
    sample_problem, tmp_path: Path, monkeypatch
):
    # strict checkpoint mode now requires an explicit HMAC key.
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "test-key")
    solver = _make_solver(sample_problem)
    plugin = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(tmp_path / "missing_ckpt"),
            auto_resume=True,
            resume_from="does_not_exist.pkl",
            strict=True,
        )
    )

    try:
        solver.add_plugin(plugin)
    except FileNotFoundError:
        return
    raise AssertionError("strict auto-resume should raise FileNotFoundError on missing checkpoint")
