"""User-facing checkpoint flags use the same signed runtime lifecycle."""
from pathlib import Path

import numpy as np
import pytest

from tests.test_production_project_acceptance import production, population
from tests.test_production_quality_benchmark import benchmark, flags


def test_build_check_does_not_create_a_key_or_checkpoint_directory(production):
    build, _, folder = production
    directory = folder / "check-only"
    solver = build(extra=("--checkpoint-dir", str(directory), "--check"))
    assert solver.get_plugin("checkpoint_resume").cfg.strict
    assert not directory.exists()


def test_case_flags_save_and_resume_latest_without_environment_keys(production, monkeypatch):
    build, _, folder = production
    monkeypatch.delenv("NSGABLACK_CHECKPOINT_HMAC_KEY", raising=False)
    expected = build()
    expected.run()
    x, f = population(expected).pop_X.copy(), population(expected).pop_F.copy()
    directory = folder / "checkpoints"
    prefix = build(extra=("--checkpoint-dir", str(directory), "--checkpoint-every", "2"))
    prefix.run(max_steps=3)
    assert prefix.run_progress_steps == 3
    plugin = prefix.get_plugin("checkpoint_resume")
    checkpoint = Path(plugin.latest_checkpoint_path)
    assert checkpoint.is_file()
    key = directory / "signing.checkpoint-key"
    original_key = key.read_bytes()
    assert len(original_key) >= 32
    resumed = build(extra=("--checkpoint-dir", str(directory), "--resume"))
    resumed.run()
    assert key.read_bytes() == original_key
    assert resumed.adapter.cursor.completed
    assert resumed.run_progress_steps == expected.run_progress_steps
    assert resumed.evaluation_count == expected.evaluation_count
    np.testing.assert_array_equal(population(resumed).pop_X, x)
    np.testing.assert_array_equal(population(resumed).pop_F, f)
    assert resumed.get_plugin("checkpoint_resume").get_report()["resume_audit"]["current"]


@pytest.mark.parametrize("corrupt", [False, True])
def test_resume_never_recreates_a_missing_key_or_accepts_a_wrong_key(production, corrupt):
    build, _, folder = production
    directory = folder / "checkpoints"
    source = build(extra=("--checkpoint-dir", str(directory), "--checkpoint-every", "1"))
    source.run(max_steps=2)
    checkpoint = source.get_plugin("checkpoint_resume").latest_checkpoint_path
    key = directory / "signing.checkpoint-key"
    if corrupt:
        key.write_bytes(b"wrong-signing-key" * 4)
    else:
        key.unlink()
    target = build(extra=("--resume", checkpoint))
    with pytest.raises(Exception, match="HMAC verification failed" if corrupt else "signing key file not found"):
        target.run()
    assert target.evaluation_count == target.run_progress_steps == 0
    assert key.exists() is corrupt


@pytest.mark.parametrize("extra", [("--resume",), ("--checkpoint-every", "2"),
                                   ("--checkpoint-dir", "unused", "--checkpoint-every", "0")])
def test_incomplete_or_invalid_checkpoint_options_fail_during_assembly(production, extra):
    build, _, _ = production
    with pytest.raises(ValueError, match="checkpoint"):
        build(extra=extra)


def test_quality_resume_targets_one_group_and_restores_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(benchmark.RESUME_ENV, "caller-sentinel")
    path = tmp_path / "production.pkl"
    plan = benchmark.quality_plan("resumed", ["quality_directional_s42"], resume=path)
    options = flags(plan[0]["stage"]["component_overrides"]["production_scheduling"]["argv"])
    assert options["--resume"] == str(path.resolve())
    assert options["--checkpoint-dir"] == str(tmp_path.resolve())
    assert benchmark.os.environ[benchmark.RESUME_ENV] == "caller-sentinel"
    ordinary = benchmark.quality_plan("ordinary", ["quality_directional_s42"])
    assert "--resume" not in ordinary[0]["stage"]["component_overrides"]["production_scheduling"]["argv"]
    with pytest.raises(ValueError, match="exactly one"):
        benchmark.quality_plan("bad", ["quality_directional_s42", "quality_directional_s43"], resume=path)
