"""容量探针使用正式单 Case、共享资源上限和独立运行预算，不求解实数据。"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import threading

import pytest

from blackbase.project import ProjectL0Runtime, load_project_runtime_config
from blackbase.resources import ResourceBudgetError


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/supply_adjustment_nested"
INLINE = "NSGABLACK_SUPPLY_CAPACITY_PROFILE_JSON"
FILE = "NSGABLACK_SUPPLY_CAPACITY_PROFILE"


def profile(node="local", threads=1):
    parent, child = {"local": (1536, 1024), "risk": (2048, 1536), "data": (3072, 2560)}[node]
    return {"schema": "supply_adjustment_nested.capacity_profile/v1", "node": node,
            "inner_threads": threads, "parent_memory_mb": parent, "inner_memory_mb": child}


def load(monkeypatch, value=None):
    monkeypatch.delenv(FILE, raising=False)
    monkeypatch.delenv(INLINE, raising=False)
    monkeypatch.setenv("BLACKBASE_JOINT_NAMESPACE", "capacity:test:shared")
    monkeypatch.setenv("BLACKBASE_JOINT_REDIS_URL", "")
    monkeypatch.delenv("NSGABLACK_SUPPLY_CASE_ARGV", raising=False)
    if value is not None:
        monkeypatch.setenv(INLINE, json.dumps(value))
    return execute_config()


def execute_config():
    spec = importlib.util.spec_from_file_location("supply_capacity_configuration", PROJECT / "project_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def option(argv, name):
    assert argv.count(name) == 1
    return argv[argv.index(name) + 1]


def test_no_probe_input_keeps_existing_groups_and_original_limits(monkeypatch):
    module = load(monkeypatch)
    assert module.CAPACITY_PROBE_PROFILE is None
    assert "capacity_probe" not in module.GROUPS
    assert module.L0["offer"]["threads"] == 1
    assert module.L0["budgets"] == {"evaluations": 20000, "audit_evaluations": 100}
    assert module.GROUPS["default"]["stages"] == ["baseline"]
    assert len(module.GROUPS["event_recovery_comparison"]["stages"]) == 11


@pytest.mark.parametrize("node,threads", [("local", 1), ("local", 4), ("local", 8), ("risk", 2), ("data", 1)])
def test_probe_declares_effective_resources_and_bounded_same_workload(monkeypatch, node, threads):
    original = load(monkeypatch)
    module = load(monkeypatch, profile(node, threads))
    assert module.STAGES[:-1] == original.STAGES
    assert {k: v for k, v in module.GROUPS.items() if k != "capacity_probe"} == original.GROUPS
    assert module.L0["offer"]["threads"] == 11
    assert module.L0["offer"]["metadata"]["memory_mb"] == 6656
    assert module.L0["offer"]["metadata"]["scope"] == "cluster_aggregate"
    assert module.L0["policy"]["max_workers"] == 3
    assert module.L0["budgets"] == {"evaluations": 2 * (512 + 1), "audit_evaluations": 2}
    stage = module.STAGES[-1]
    assert stage["name"] == "capacity_probe" and stage["mode"] == "build"
    assert stage["cases"] == ["supply_adjustment_nested"]
    assert "input_artifacts" not in stage
    request = stage["resource_requests"]["supply_adjustment_nested"]
    assert request == module.L0["default_request"] and request["threads"] == threads
    assert "supplycapacity:" + node in request["capabilities"]
    assert stage["timeout_seconds"] == 1500
    argv = stage["component_overrides"]["supply_adjustment_nested"]["argv"]
    for key, value in {"--seed": "42", "--inner-seed": "42", "--pop-size": "200", "--generations": "100",
            "--max-evaluations": "2", "--inner-pop-size": "200", "--inner-generations": "100",
            "--inner-max-evaluations": "512", "--inner-parallel-workers": str(threads),
            "--nested-task-timeout-seconds": "600"}.items():
        assert option(argv, key) == value
    assert "--parallel" in argv and "--no-profiler" in argv and "--no-decision-trace" in argv


@pytest.mark.parametrize("change", [
    {"node": "other"}, {"inner_threads": True}, {"inner_threads": 9}, {"parent_memory_mb": 1537},
    {"inner_memory_mb": 1025}, {"parent_memory_mb": 1024}, {"unknown_option": 8},
    {"capabilities": ["production_inner", "nested_eval"]},
])
def test_probe_rejects_invalid_or_excessive_deployment_input(monkeypatch, change):
    with pytest.raises(ValueError):
        load(monkeypatch, {**profile(), **change})


def test_profile_file_and_inline_are_explicit_and_do_not_silently_fallback(monkeypatch, tmp_path):
    load(monkeypatch)
    path = tmp_path / "capacity.json"
    path.write_text(json.dumps(profile("risk", 2)), encoding="utf-8-sig")
    monkeypatch.setenv(FILE, str(path))
    assert execute_config().CAPACITY_PROBE_PROFILE["node"] == "risk"
    monkeypatch.setenv(INLINE, json.dumps(profile()))
    with pytest.raises(ValueError, match="not both"):
        execute_config()
    monkeypatch.delenv(FILE)
    monkeypatch.delenv("BLACKBASE_JOINT_NAMESPACE")
    with pytest.raises(ValueError, match="explicit shared"):
        execute_config()


def test_three_controllers_share_aggregate_leases_but_have_independent_budget_scopes(monkeypatch, tmp_path):
    modules = [load(monkeypatch, profile(node, threads)) for node, threads in (("local", 8), ("risk", 2), ("data", 1))]
    assert all(module.L0["offer"] == modules[0].L0["offer"] for module in modules)
    runtimes = [ProjectL0Runtime(replace(load_project_runtime_config(module), lease_path="shared.sqlite"),
        project_root=tmp_path) for module in modules]
    scopes = [runtime.budget_authority_metadata["scope"] for runtime in runtimes]
    assert len(set(scopes)) == 3
    assert all(runtime.budget_authority_metadata["namespace"] == "capacity:test:shared" for runtime in runtimes)
    ready, release = threading.Barrier(4), threading.Event()

    def hold(runtime):
        lease = runtime.acquire_case("supply_adjustment_nested", stage_name="capacity_probe")
        try:
            ready.wait(timeout=5)
            assert release.wait(timeout=5)
            return lease.lease_id
        finally:
            runtime.release(lease)

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(hold, runtime) for runtime in runtimes]
            try:
                ready.wait(timeout=5)
                active = runtimes[0].allocator.lease_store.list()
                assert len(active) == 3
                assert sum(lease.resources["threads"] for lease in active) == 11
                assert sum(lease.resources["memory_mb"] for lease in active) == 6656
                with pytest.raises(ResourceBudgetError):
                    runtimes[0].acquire_case("fourth_case")
            finally:
                release.set()
            assert len({future.result() for future in futures}) == 3
        assert not runtimes[0].allocator.lease_store.list()
    finally:
        for runtime in runtimes:
            runtime.close()
