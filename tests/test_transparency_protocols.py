"""公开覆盖口径及候选/事件协议的真实运行与恢复。"""
import pytest

from benchmarks.transparency_core import run_pair
from benchmarks.transparency_protocols import specs
from benchmarks.transparency_registry import by_name, coverage_report, export_inventory, specs as all_specs


@pytest.mark.parametrize("spec", specs(), ids=lambda spec: spec.name)
@pytest.mark.parametrize("seed", [3, 17])
def test_nonempty_protocol_case_matches_independent_reference_and_real_resume(spec, seed):
    result = run_pair(spec, seed=seed, work_dir="runs/evidence/transparency_protocol_tests")
    assert result["semantics"]["status"] == "passed", result["semantics"]
    assert result["recovery"]["status"] == "passed", result["recovery"]
    semantics = result["semantics"]
    state = semantics["framework_state"]
    if spec.name == "candidate_proposer_contract":
        assert semantics["framework_evaluations"] == 18
        assert state["distinct_candidate_tokens"] == state["retained_count"] == 3
        assert state["units"][0]["values"] == state["units"][1]["values"]
        assert state["units"][0]["lane"] != state["units"][1]["lane"]
        assert semantics["framework_trace"][0]["state"]["units"][0]["values"] == [1.0, 0.35]
    elif spec.name == "async_event_driven_cases":
        assert semantics["framework_evaluations"] == 12
        assert state["active_case"] == "late" and state["active_since"] == 3
        assert state["last_exit"] == {"early": 3}
        assert len(state["queue"]) == 3 and len(state["archive"]) == 4
        assert state["stats"]["early"]["completed"] == state["stats"]["late"]["completed"] == 6.0
        assert state["children"]["early"]["unit_counter"] == 9
        assert state["children"]["early"]["retained_count"] == 2
    else:
        assert 18 <= semantics["framework_evaluations"] <= 24
        assert state["active_case"] is None
        assert len(state["queue"]) == 7 and len(state["archive"]) == 6
        assert state["stats"]["early"]["completed"] > 0
        assert state["stats"]["late"]["completed"] > 0
        assert sum(row["completed"] for row in state["stats"].values()) == semantics["framework_evaluations"]
        assert any(row["kind"] == "dispatch" and row["accepted"] == 0 for row in state["history"])


def test_registry_classifies_every_public_export_and_never_counts_abstract_as_passed():
    from nsgablack import adapters

    inventory = export_inventory()
    assert [row["name"] for row in inventory] == adapters.__all__
    report = coverage_report()
    assert report["summary"]["concrete_uncovered"] == 0
    assert report["summary"]["concrete_passed"] == 0
    assert {row["name"] for row in report["abstract_adapters"]} == {
        "AlgorithmAdapter", "UnitBackedAdapter", "CandidateProposerAdapter"}
    assert all(not row["counted_as_passed"] for row in report["abstract_adapters"])
    assert next(row for row in inventory if row["name"] == "Pool")["classification"] == "public_alias"
    assert by_name("candidate_proposer_contract").metadata["counts_as_concrete_algorithm"] is False


def test_coverage_status_requires_actual_semantics_and_recovery_results():
    # These synthetic records exercise only the reporting classifier; they are
    # not benchmark evidence and are never written to a run artifact.
    records = [{"name": spec.name, "semantics": {"status": "passed"}, "quality": {"status": "passed"},
                "recovery": {"status": "passed"}}
               for spec in all_specs()]
    full = coverage_report(records)
    assert full["summary"]["concrete_passed"] == full["summary"]["concrete_adapter_count"]
    failed = next(row for row in records if row["name"] == "async_event_driven_cases")
    failed["recovery"]["status"] = "failed"
    report = coverage_report(records)
    assert next(row for row in report["concrete_adapters"] if row["name"] == "AsyncEventDrivenAdapter")["status"] == "failed"
    assert report["summary"]["concrete_passed"] == report["summary"]["concrete_adapter_count"] - 1


@pytest.mark.parametrize("quality_status", ["unsupported", "failed", None])
def test_coverage_quality_must_pass_even_when_semantics_and_recovery_pass(quality_status):
    # Exercise the classification gate, not a synthetic optimization result.
    records = [{"name": spec.name, "semantics": {"status": "passed"}, "quality": {"status": "passed"},
                "recovery": {"status": "passed"}} for spec in all_specs()]
    target = next(row for row in records if row["name"] == "nsga2_zdt1")
    if quality_status is None:
        del target["quality"]
    else:
        target["quality"]["status"] = quality_status
    report = coverage_report(records)
    assert next(row for row in report["concrete_adapters"] if row["name"] == "NSGA2Adapter")["status"] == "failed"
    assert report["summary"]["concrete_passed"] == report["summary"]["concrete_adapter_count"] - 1
    assert report["required_checks"] == ["semantics", "quality", "recovery"]


def test_registry_profile_only_changes_population_cases():
    defaults = {spec.name: spec for spec in all_specs()}
    expanded = {spec.name: spec for spec in all_specs(population_size=12, steps=8)}
    assert defaults.keys() == expanded.keys()
    for name, spec in expanded.items():
        if spec.metadata.get("family") == "population":
            assert spec.population_size == 12 and spec.steps == 8
            assert spec.metadata["evaluation_budget"] == 96
        else:
            assert spec.steps == defaults[name].steps
            assert spec.population_size == defaults[name].population_size
    configured = by_name("nsga2_zdt1", population_size=12, steps=8)
    assert configured.make_adapter(11).cfg.population_size == 12
    assert by_name("search_plan_serial", population_size=12, steps=8).steps == 4


def test_new_public_adapter_is_reported_as_uncovered(monkeypatch):
    from nsgablack import adapters

    class NewPublicAdapter(adapters.AlgorithmAdapter):
        def propose(self, solver, context):
            return [[0.0]]

        def update(self, solver, candidates, feedback, context):
            pass

    monkeypatch.setattr(adapters, "NewPublicAdapter", NewPublicAdapter, raising=False)
    monkeypatch.setattr(adapters, "__all__", [*adapters.__all__, "NewPublicAdapter"])
    report = coverage_report()
    assert report["summary"]["concrete_uncovered"] == 1
    assert next(row for row in report["concrete_adapters"] if row["name"] == "NewPublicAdapter")["status"] == "uncovered"


def test_async_weighted_routing_uses_formal_solver_stream_and_seed_changes_route():
    import numpy as np
    from benchmarks.transparency_core import build_pair_solver

    spec = by_name("async_event_driven_weighted")
    queues = []
    for seed in (17, 17, 3):
        solver, _, _, _ = build_pair_solver(spec, seed)
        solver.setup()
        expected_seed = int(np.random.default_rng(seed).integers(0, 2**63 - 1))
        assert solver.adapter._rng.bit_generator.state == np.random.default_rng(expected_seed).bit_generator.state
        assert solver.step().committed
        queues.append([event["strategy"] for event in solver.adapter._queue])
    assert queues[0] == queues[1]
    assert queues[0] != queues[2]
