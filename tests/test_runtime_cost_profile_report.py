"""Analyze synthetic profiles only; never import or execute model code."""
import cProfile
import importlib.util
import json
from pathlib import Path
import time

import pytest


REPORT = Path(__file__).resolve().parents[1] / "examples/cases/runtime_cost_probe/profiling/report.py"


def _module():
    spec = importlib.util.spec_from_file_location("runtime_cost_profile_report", REPORT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_source(path, source, namespace):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    exec(compile(source, str(path), "exec"), namespace)


def test_full_profile_identity_separates_pool_comprehensions_and_domain_methods(tmp_path):
    report = _module()
    pool = tmp_path / "nsgablack/core/state/solution_pool.py"
    _synthetic_source(pool, "def _index_state():\n    return [x for x in range(3)]\n\ndef put():\n    return [x for x in range(3)]\n", {})
    assert report.classify_function((str(pool), 2, "<listcomp>")) == "pool_index"
    assert report.classify_function((str(pool), 5, "<listcomp>")) == "pool_values"
    domain = tmp_path / "examples/cases/production_scheduling/cases/production_scheduling/pipeline/schedule_pipeline.py"
    _synthetic_source(domain, "class SupplyAwareScheduleRepair:\n    def _balance_forward(self):\n        return 1\n", {})
    assert report.classify_function((str(domain), 2, "_balance_forward")) == "domain_repair"
    assert report.classify_function((str(tmp_path / "unrelated.py"), 2, "repair")) == "unclassified"
    assert report.classify_function(("<frozen importlib._bootstrap>", 1176, "_find_and_load")) == "cold_import"
    assert report.classify_function(("~", 0, "<method 'tolist' of 'numpy.ndarray' objects>")) == "native_numpy"
    with pytest.raises(ValueError, match="absolute"):
        report.analyze_run("relative/run")


@pytest.mark.parametrize("timer", ["time.thread_time", "cProfile.default_elapsed"])
def test_synthetic_profile_report_self_partition_and_non_additive_boundaries(tmp_path, capsys, timer):
    report = _module()
    namespace = {}
    # Windows thread_time can have a coarse clock tick. Use a bounded loop
    # without generator callbacks so both supported timers record nonzero work.
    _synthetic_source(tmp_path / "blackbase/context/redis_codec.py", "def encode():\n    total = 0\n    for x in range(2000000):\n        total += x*x\n    return total\n", namespace)
    _synthetic_source(tmp_path / "nsgablack/core/state/solution_pool.py", "def put():\n    return encode()\n\ndef _index_state():\n    return put()\n", namespace)
    _synthetic_source(tmp_path / "nsgablack/units/contracts.py", "def dump():\n    return _index_state()\n", namespace)
    run_root = tmp_path / "run"
    profiles = run_root / "profiles"
    profiles.mkdir(parents=True)
    profile = cProfile.Profile(timer=time.thread_time) if timer == "time.thread_time" else cProfile.Profile()
    profile.runcall(namespace["dump"])
    profile.dump_stats(str(profiles / "process-123.prof"))
    metadata = {"pid": 123, "parent_pid": 1, "entry": "synthetic", "timer": timer,
                "wall_seconds": 1.0, "process_cpu_seconds": .5, "main_thread_cpu_seconds": .4,
                "coverage": "main thread of this process only"}
    (profiles / "process-123.json").write_text(json.dumps(metadata), encoding="utf-8")

    assert report.main(["--run-root", str(run_root)]) == 0
    output = json.loads((run_root / "profile_analysis.json").read_text(encoding="utf-8"))
    process, = output["processes"]
    assert process["metadata"] == metadata
    assert process["profile_timer"] == timer
    assert process["profile_clock_kind"] == ("main_thread_cpu" if timer == "time.thread_time" else "elapsed")
    assert process["grouped_self_profile_clock_seconds"] == pytest.approx(process["total_self_profile_clock_seconds"])
    assert sum(row["fraction_of_profile_self"] for row in process["self_groups"]) == pytest.approx(1.0)
    groups = {row["group"]: row for row in process["self_groups"]}
    assert all(groups[key]["function_count"] for key in (
        "unit_codec_runtime_capture", "pool_index", "pool_values", "shared_wire_copy_json",
    ))
    boundaries = process["key_boundaries_non_additive"]
    assert any(row["function"] == "dump" and row["inclusive_profile_clock_seconds_non_additive"] > row["self_profile_clock_seconds"] for row in boundaries)
    assert any(edge["caller"]["function"] == "_index_state" and edge["callee"]["function"] == "put"
               for edge in process["top20_caller_callee_edges_non_additive"])
    assert all({"filename", "line", "function"} <= row.keys() for row in process["top20_self"])
    assert json.loads(capsys.readouterr().out)["process_count"] == 1

    metadata["timer"] = "time.perf_counter"
    (profiles / "process-123.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="timer"):
        report.analyze_run(run_root)
