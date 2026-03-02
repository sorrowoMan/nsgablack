from __future__ import annotations

import json
from pathlib import Path

from nsgablack.utils.runtime.repro_bundle import (
    apply_bundle_to_solver,
    build_repro_bundle,
    compare_repro_bundle,
    load_repro_bundle,
    write_repro_bundle,
)
import nsgablack.utils.runtime.repro_bundle as repro_bundle_mod


class _DummySolver:
    def __init__(self) -> None:
        self.random_seed = 123
        self.max_generations = 10
        self.max_steps = 20
        self.context_store_backend = "memory"
        self.snapshot_store_backend = "memory"

    def set_random_seed(self, seed: int) -> None:
        self.random_seed = int(seed)


def test_repro_bundle_build_write_load(tmp_path: Path) -> None:
    seq_path = tmp_path / "demo.sequence_graph.json"
    seq_payload = {
        "sequence_records": [
            {"signature": "3:aaa", "count": 2, "events": ["a", "b", "c"]},
            {"signature": "2:bbb", "count": 1, "events": ["a", "d"]},
        ],
        "trace_events": [
            {"thread_id": 1, "task_id": "t0", "token": "a", "status": "ok", "duration_ns": 10},
            {"thread_id": 1, "task_id": "t0", "token": "b", "status": "error", "duration_ns": 20},
        ],
    }
    seq_path.write_text(json.dumps(seq_payload, ensure_ascii=False), encoding="utf-8")

    trace_path = tmp_path / "demo.decision_trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "event_type": "runtime_call",
                        "component": "adapter.propose",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "event_type": "runtime_call",
                        "component": "solver.evaluate_population",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    solver = _DummySolver()
    run_snapshot = {
        "adapter": "NSGA2Adapter",
        "pipeline": {"initializer": "uniform"},
        "strategies": [],
        "biases": [],
        "plugins": [{"name": "sequence_graph", "enabled": True}],
        "context_store": {"backend": "memory"},
        "snapshot_store": {"backend": "memory"},
        "structure_hash": "abc123",
    }
    bundle = build_repro_bundle(
        run_id="demo",
        solver=solver,
        entrypoint=f"{tmp_path / 'build_solver.py'}:build_solver",
        workspace=tmp_path,
        run_snapshot=run_snapshot,
        artifacts={
            "sequence_graph_json": str(seq_path),
            "decision_trace_jsonl": str(trace_path),
        },
        started_at=100.0,
        finished_at=120.0,
    )
    assert bundle["schema_name"] == "repro_bundle"
    assert bundle["schema_version"] == 1
    assert bundle["runtime"]["max_generations"] == 10
    assert bundle["structure_proof"]["sequence_signature_set_hash"]
    assert bundle["structure_proof"]["sequence_trie_fingerprint_hash"]
    assert bundle["structure_proof"]["trace_group_digest_hash"]
    assert bundle["structure_proof"]["decision_trace_digest_hash"]

    out_path = write_repro_bundle(bundle, output_dir=tmp_path, run_id="demo")
    loaded = load_repro_bundle(out_path)
    assert loaded["run_id"] == "demo"
    assert loaded["wiring"]["adapter"] == "NSGA2Adapter"


def test_compare_repro_bundle_detects_drift(tmp_path: Path) -> None:
    solver = _DummySolver()
    bundle = build_repro_bundle(
        run_id="demo",
        solver=solver,
        entrypoint=f"{tmp_path / 'a.py'}:build_solver",
        workspace=tmp_path,
        run_snapshot={"adapter": "A", "structure_hash": "h1"},
        artifacts={},
    )
    current = compare_repro_bundle(
        bundle,
        current_entrypoint=f"{tmp_path / 'b.py'}:build_solver",
        current_workspace=tmp_path,
        current_snapshot={"adapter": "B", "structure_hash": "h2"},
        current_solver=solver,
    )
    assert current["status"] in {"blocked", "drift"}
    assert int(current["blockers"]) >= 1


def test_apply_bundle_to_solver_sets_seed_and_limits(tmp_path: Path) -> None:
    solver = _DummySolver()
    bundle = build_repro_bundle(
        run_id="demo",
        solver=solver,
        entrypoint=f"{tmp_path / 'a.py'}:build_solver",
        workspace=tmp_path,
        run_snapshot={"adapter": "A", "structure_hash": "h1"},
        artifacts={},
    )
    bundle["random"]["effective_seed"] = 999
    bundle["runtime"]["max_generations"] = 77
    bundle["runtime"]["max_steps"] = 88
    applied = apply_bundle_to_solver(solver, bundle)
    assert "seed=999" in applied
    assert "max_generations=77" in applied
    assert "max_steps=88" in applied
    assert solver.random_seed == 999
    assert solver.max_generations == 77
    assert solver.max_steps == 88


def test_run_cmd_handles_non_default_encoded_bytes(monkeypatch) -> None:
    class _Proc:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = b"branch-\xef\xaf\x80\n"
            self.stderr = b""

    def _fake_run(*_args, **_kwargs):
        return _Proc()

    monkeypatch.setattr(repro_bundle_mod.subprocess, "run", _fake_run)
    out = repro_bundle_mod._run_cmd(["git", "rev-parse"], cwd=Path.cwd())
    assert isinstance(out, str)
    assert "branch" in out


def test_run_cmd_supports_chinese_cwd_and_gbk_output(tmp_path: Path, monkeypatch) -> None:
    zh_dir = tmp_path / "中文目录"
    zh_dir.mkdir(parents=True, exist_ok=True)
    expected = "中文输出"

    class _Proc:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = expected.encode("gbk")
            self.stderr = b""

    def _fake_run(*_args, **_kwargs):
        assert Path(str(_kwargs.get("cwd"))).name == "中文目录"
        return _Proc()

    monkeypatch.setattr(repro_bundle_mod.subprocess, "run", _fake_run)
    out = repro_bundle_mod._run_cmd(["git", "status"], cwd=zh_dir)
    assert out == expected
