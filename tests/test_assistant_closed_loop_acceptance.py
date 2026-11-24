"""Fixed behavior and live feedback gates; fixtures never enter model prompts."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nsgablack.catalog.assistant_closed_loop_acceptance import (
    IDEAS, TARGET, execute_candidate, main, review_candidate_source, run_closed_loop,
    source_digest, spec_identity, _observed_repair,
)
from nsgablack.catalog import assistant_closed_loop_acceptance as acceptance
from nsgablack.catalog.assistant_evaluation import content_digest
from nsgablack.catalog.assistant_session_acceptance import create_teaching_project


GRID = '''import numpy as np
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer

def grid_survivors(pool, *, count, rng=None):
    if count < 0 or count > len(pool):
        raise ValueError("invalid count")
    if count == 0:
        return pool.take(())
    values = pool.values
    objectives, violations = pool.selection_feedback()
    cells = {}
    bad = []
    for i in range(len(pool)):
        if violations[i] <= 0:
            cell = tuple(int(v) for v in np.floor(values[i, :2]))
            cells.setdefault(cell, []).append(i)
        else:
            bad.append(i)
    for group in cells.values():
        group.sort(key=lambda i: (objectives[i, 0], i))
    result = []
    depth = 0
    while len(result) < count:
        before = len(result)
        for cell in sorted(cells):
            group = cells[cell]
            if depth < len(group) and len(result) < count:
                result.append(group[depth])
        if before == len(result):
            break
        depth += 1
    bad.sort(key=lambda i: (violations[i], objectives[i, 0], i))
    result.extend(bad[:count-len(result)])
    return pool.take(result)

def build_adapter():
    adapter = NSGA2Adapter(population_size=4, offspring_size=3)
    adapter.set_initializer(UniformInitializer(-4.0, 4.0))
    adapter.set_selector(grid_survivors)
    return adapter
'''


DONOR = '''import numpy as np
from nsgablack.adapters import NSGA2Adapter, ChangeBatchResult, ChangeResult
from nsgablack.representation import UniformInitializer

def donor_direction_change(request, *, rng):
    if request.max_outputs == 0:
        return ChangeBatchResult(())
    if len(request.parents) != 2 or len(request.source_refs) != 2 or request.pool is None:
        raise ValueError("two referenced parents and pool required")
    donors = request.pool.subpool("donor_bank")
    if len(donors) < 2:
        raise ValueError("two donor positions required")
    chosen = donors.take((0, len(donors)-1))
    if chosen.refs[0] == chosen.refs[1]:
        raise ValueError("two donor versions required")
    values = chosen.values
    if values.shape != request.parents.shape:
        raise ValueError("shape mismatch")
    candidate = np.clip((request.parents[0]+request.parents[1])/2 + .25*(values[1]-values[0]), -4., 4.)
    return ChangeBatchResult((ChangeResult(candidate, source_refs=(*request.source_refs, *chosen.refs)),))

def build_adapter():
    adapter = NSGA2Adapter(population_size=4, offspring_size=3)
    adapter.set_initializer(UniformInitializer(-4.0, 4.0))
    adapter.set_change(donor_direction_change)
    return adapter
'''


def proposal(source):
    digest = source_digest(source)
    return {"source": source, "path": TARGET, "code_sha256": digest,
            "check": {"status": "needs_runtime_validation", "code_sha256": digest}}


@pytest.mark.parametrize("idea,source,checks", [(IDEAS[0]["id"], GRID, 13), (IDEAS[1]["id"], DONOR, 12)])
def test_fixed_reference_is_valid_with_actual_pool_types_and_canonical_case(idea, source, checks):
    result = execute_candidate(proposal(source), idea)
    assert result["status"] == "passed", result
    assert result["executed"] is True
    assert result["behavior"]["checks"] == checks
    assert result["formal_case"]["committed_steps"] == 2
    assert result["formal_case"]["evaluations"] == 7
    assert result["formal_case"]["actual_problem_calls"] == 7
    assert result["formal_case"]["evaluation_batches"] == [4, 3]
    assert result["formal_case"]["operation_invocations"] >= 1
    assert result["executed_source_sha256"] == hashlib.sha256(source.encode()).hexdigest()
    assert result["validation_identity"] == spec_identity()


def test_wrong_survivor_order_is_an_actual_behavior_failure():
    source = GRID.replace('return pool.take(result)', 'return pool.take(list(reversed(result)))')
    result = execute_candidate(proposal(source), IDEAS[0]["id"])
    assert result["status"] == "failed" and result["executed"]
    assert result["failed_stage"] == "behavior" and result["error_type"] == "AssertionError"
    assert "traceback" in result and "AssertionError" in result["traceback"]


def test_wrong_direction_sign_is_not_saved_by_successful_static_check():
    source = DONOR.replace('values[1]-values[0]', 'values[0]-values[1]')
    result = execute_candidate(proposal(source), IDEAS[1]["id"])
    assert result["status"] == "failed" and result["failed_stage"] == "behavior"
    assert result["code_sha256"] == source_digest(source)


def test_unused_correct_export_cannot_pass_the_formal_assembly_check():
    source = GRID.replace('adapter.set_selector(grid_survivors)', 'pass')
    result = execute_candidate(proposal(source), IDEAS[0]["id"])
    assert result["status"] == "failed" and result["failed_stage"] == "formal_case"
    assert "different operation" in result["error"]


def test_legacy_unscored_bootstrap_does_not_count_as_declared_seed_evaluation():
    source = GRID.replace('adapter.set_initializer(UniformInitializer(-4.0, 4.0))', 'pass')
    result = execute_candidate(proposal(source), IDEAS[0]["id"])
    assert result["status"] == "failed" and result["failed_stage"] == "formal_case"
    assert "initializer" in result["error"]


@pytest.mark.parametrize("source", [
    'import numpy as np\nnp.testing.assert_array_equal = lambda *args: None',
    'from numpy.testing import assert_array_equal',
    'from nsgablack.adapters import NSGA2Adapter\nNSGA2Adapter.propose = lambda *args: []',
    'import os\nprint(os.environ)',
])
def test_test_integrity_and_import_policy_reject_global_effects(source):
    with pytest.raises(ValueError):
        review_candidate_source(source)


def test_wrong_source_identity_does_not_execute():
    data = proposal(GRID)
    data["code_sha256"] = "0" * 64
    result = execute_candidate(data, IDEAS[0]["id"])
    assert result["status"] == "failed" and result["executed"] is False
    assert result["failed_stage"] == "identity"


def test_observed_repair_requires_actual_failure_in_later_model_input():
    source, new_source = "def current(): return 0\n", "def current(): return 1\n"
    old_sha, new_sha = source_digest(source), source_digest(new_source)
    receipt = {"status": "failed", "executed": True, "code_sha256": old_sha,
        "executed_source_sha256": old_sha, "validation_identity": "current-profile", "failed_stage": "behavior"}
    failed = {"after_request": 2, "code_sha256": old_sha, "result": receipt}
    passed = {"after_request": 4, "code_sha256": new_sha, "result": {"status": "passed", "executed": True,
        "code_sha256": new_sha, "executed_source_sha256": new_sha, "validation_identity": "current-profile"}}
    assert not _observed_repair([failed, passed], [])
    origin = {"request": 2, "status": "received", "messages": [], "tool_calls": [
        {"id": "current-check", "type": "function", "function": {"name": "check_project_edit",
            "arguments": json.dumps({"path": TARGET, "source": source})}}]}
    request = {"request": 3, "messages": [{"role": "tool", "tool_call_id": "current-check", "content": json.dumps({
        "code_sha256": old_sha, "validation": {**receipt, "error": "real exception"}})}]}
    assert _observed_repair([failed, passed], [origin, request])
    assert not _observed_repair([passed], [origin, request])
    assert not _observed_repair([{**failed, "result": {**receipt, "executed": False}}, passed], [origin, request])
    assert not _observed_repair([failed, passed], [request])
    for key, value in [("validation_identity", "old-profile"), ("executed", False),
                       ("executed_source_sha256", "different"), ("failed_stage", "source_review"),
                       ("code_sha256", "different"), ("status", "passed")]:
        unrelated = deepcopy(request)
        unrelated["messages"][0]["content"] = json.dumps({"code_sha256": old_sha, "validation": {**receipt, key: value}})
        assert not _observed_repair([failed, passed], [origin, unrelated]), key
    old_profile_and_call = deepcopy(request)
    old_profile_and_call["messages"][0].update(tool_call_id="historical-check", content=json.dumps({
        "code_sha256": old_sha, "validation": {**receipt, "validation_identity": "old-profile",
            "executed": False, "failed_stage": "source_review"}}))
    assert not _observed_repair([failed, passed], [origin, old_profile_and_call])
    wrong_call = deepcopy(request)
    wrong_call["messages"][0]["tool_call_id"] = "historical-check"
    assert not _observed_repair([failed, passed], [origin, wrong_call])
    wrong_source = deepcopy(origin)
    wrong_source["tool_calls"][0]["function"]["arguments"] = json.dumps({"path": TARGET, "source": new_source})
    assert not _observed_repair([failed, passed], [wrong_source, request])


def test_no_real_execution_or_model_calls_without_explicit_authorization():
    with pytest.raises(ValueError, match="explicit_closed_loop_execution_required"):
        run_closed_loop(object())
    with pytest.raises(SystemExit):
        main(["--out", "unused.json"])


def test_live_validator_failure_is_seen_and_repaired_by_same_scripted_model():
    # This test exercises wiring; actual behavior tests above use real subprocesses.
    calls = 0
    failed_source = "def grid_survivors(pool, *, count, rng=None): return 0\n"
    passed_source = "def grid_survivors(pool, *, count, rng=None): return 1\n"
    def executor(data, _idea):
        success = data["source"] == passed_source
        digest = source_digest(data["source"])
        return {"status": "passed" if success else "failed", "executed": True,
                "code_sha256": digest, "executed_source_sha256": digest,
                "validation_identity": spec_identity(), "failed_stage": None if success else "behavior",
                "error": None if success else "value was zero"}
    def complete(_generator, messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            # No fixture/reference implementation/test values in initial context.
            assert "value was zero" not in json.dumps(messages)
        if calls == 2:
            feedback = json.loads(messages[-1]["content"])
            assert feedback["validation"]["error"] == "value was zero"
        if calls <= 2:
            return {"model": "one-model", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": str(calls), "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
                    "path": TARGET, "source": failed_source if calls == 1 else passed_source})}}]}}
        output = json.loads(messages[-1]["content"])
        return {"model": "one-model", "message": {"role": "assistant", "content": json.dumps({
            "explanation": "Same model used validator feedback.", "questions": [], "proposal_digest": None,
            "edit_digest": output["edit_digest"]})}}
    report = run_closed_loop(object(), complete=complete, allow_code_execution=True,
        executor=executor, case_ids=[IDEAS[0]["id"]], max_model_calls=8)
    assert report["summary"]["passed"] == 1, report
    assert report["summary"]["observed_runtime_repairs"] == 1
    assert report["summary"]["model_request_attempts"] == 3
    assert {x["model"] for x in report["requests"]} == {"one-model"}


def test_global_request_cap_is_hard_even_when_model_keeps_searching():
    calls = 0
    def complete(*_):
        nonlocal calls
        calls += 1
        return {"model": "one-model", "message": {"role": "assistant", "content": "", "tool_calls": [
            {"id": str(calls), "type": "function", "function": {"name": "framework_api", "arguments": '{"symbol":"ChangeRequest"}'}}]}}
    report = run_closed_loop(object(), complete=complete, allow_code_execution=True,
        maximum_requests=2, max_model_calls=8, case_ids=[IDEAS[0]["id"]])
    assert report["summary"]["model_request_attempts"] == calls == 2
    assert report["summary"]["passed"] == 0


def _prior_report(tmp_path, *, legacy=False, bad_project=False):
    sources, pid = create_teaching_project(tmp_path / "prior")
    digest = sources.describe_project(pid)["source_digest"] if not bad_project else "0" * 64
    messages = [{"role": "system", "content": "old system"},
        {"role": "user", "content": json.dumps({"project_id": pid, "project": {"source_digest": digest}})},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "past-read", "type": "function", "function": {
            "name": "project_read", "arguments": '{"path":"cases/hybrid_search/config.py"}'}}]},
        {"role": "tool", "tool_call_id": "past-read", "content": '{"historical_marker":"actual prior tool response"}'}]
    record = {"idea": IDEAS[0]["id"], "request": 24, "messages": messages,
              "messages_sha256": content_digest(messages), "status": "received", "model": "one-model",
              "visible_content": json.dumps({"explanation": "previous public final", "questions": [],
                  "proposal_digest": None, "edit_digest": "f" * 64}), "tool_calls": []}
    report = {"schema": acceptance.SCHEMA, "kind": "same_model_live_validation",
        "validation_identity": spec_identity(), "oracle_math_sha256": acceptance.oracle_math_sha256(),
        "execution_guard_profile": acceptance.execution_guard_profile(), "execution_policy": acceptance.EXECUTION_POLICY,
        "model_configuration": None, "cases": [{"id": IDEAS[0]["id"], "status": "failed", "attempts": [],
            "input": {"project_id": pid, "project": {"source_digest": digest}}}],
        "requests": [record], "summary": {"model_request_attempts": 24}}
    if legacy:
        report.pop("oracle_math_sha256")
        report.pop("execution_guard_profile")
        report["validation_identity"] = "closed_loop:" + content_digest({**acceptance._oracle_descriptor(),
            "execution_policy": acceptance.EXECUTION_POLICY})
    path = tmp_path / "prior.raw.json"
    raw = json.dumps(report, ensure_ascii=False).encode()
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def test_legacy_math_profile_and_exact_paired_public_history_are_preserved(tmp_path):
    path, digest = _prior_report(tmp_path, legacy=True)
    profile = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    history = profile["cases"][0]["history"]
    assert [row["role"] for row in history] == ["assistant", "tool", "assistant"]
    assert history[1]["content"] == '{"historical_marker":"actual prior tool response"}'
    assert history[-1]["content"].find("previous public final") >= 0
    assert profile["cases"][0]["last_response"] == "received_public_final"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert profile["oracle_math_sha256"] == acceptance.oracle_math_sha256()


@pytest.mark.parametrize("field", ["model_id", "source_digest", "history"])
def test_continuation_cannot_substitute_model_project_or_manual_history(tmp_path, field):
    path, digest = _prior_report(tmp_path)
    profile = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    row = profile["cases"][0]
    if field == "history":
        row["history"].append({"role": "user", "content": "manual solution must not enter reconstruction"})
        row["history_sha256"] = content_digest(row["history"])
    else:
        row[field] = "different"
    with pytest.raises(ValueError, match="continuation_original_binding_changed"):
        acceptance._verify_development_continuation(profile)


def test_prior_raw_change_or_math_change_blocks_continuation(tmp_path, monkeypatch):
    path, digest = _prior_report(tmp_path)
    profile = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    old_math = acceptance.oracle_math_sha256()
    monkeypatch.setattr(acceptance, "IDEAS", (*IDEAS[:-1], {**IDEAS[-1], "instruction": "different algorithm"}))
    assert acceptance.oracle_math_sha256() != old_math
    with pytest.raises(ValueError, match="continuation_oracle_changed"):
        acceptance.prepare_development_continuation(path, expected_sha256=digest)
    monkeypatch.undo()
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="continuation_prior_report_changed"):
        acceptance._verify_development_continuation(profile)


def test_guard_identity_changes_without_rewriting_math_oracle(monkeypatch):
    math = acceptance.oracle_math_sha256()
    before = spec_identity()
    def different_guard(source):
        return source
    monkeypatch.setattr(acceptance, "review_execution_source", different_guard)
    assert spec_identity() != before
    assert acceptance.oracle_math_sha256() == math


def test_live_continuation_keeps_old_feedback_but_requires_new_validation(tmp_path):
    path, digest = _prior_report(tmp_path)
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    calls = 0
    source = "def grid_survivors(pool, *, count, rng=None): return 1\n"
    def complete(_owner, messages, _tools):
        nonlocal calls
        calls += 1
        assert sum(message["role"] == "system" for message in messages) == 1
        assert messages[0]["content"].find("old system") == -1
        assert any("actual prior tool response" in row.get("content", "") for row in messages)
        if calls == 1:
            return {"model": "one-model", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "new-check", "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
                    "path": TARGET, "source": source})}}]}}
        output = json.loads(messages[-1]["content"])
        assert output["edit_digest"] != "f" * 64
        return {"model": "one-model", "message": {"role": "assistant", "content": json.dumps({
            "explanation": "Resumed same model and checked this profile.", "questions": [], "proposal_digest": None,
            "edit_digest": output["edit_digest"]})}}
    def executor(data, _):
        return {"status": "passed", "executed": True, "code_sha256": data["code_sha256"],
            "executed_source_sha256": data["code_sha256"], "validation_identity": spec_identity()}
    report = run_closed_loop(object(), complete=complete, executor=executor, development_continuation=continuation,
        allow_code_execution=True, maximum_requests=12, max_model_calls=12, case_ids=[IDEAS[0]["id"]])
    assert report["summary"]["passed"] == 1, report
    assert report["summary"]["model_request_attempts"] == 2
    assert report["summary"]["cumulative_model_request_attempts"] == 26
    assert report["kind"] == "same_model_development_continuation"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_continuation_wrong_current_project_stops_before_model_request(tmp_path):
    path, digest = _prior_report(tmp_path, bad_project=True)
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    def complete(*_):
        pytest.fail("Changed Project must be rejected before a model request")
    report = run_closed_loop(object(), complete=complete, development_continuation=continuation,
        allow_code_execution=True, maximum_requests=12, max_model_calls=6, case_ids=[IDEAS[0]["id"]])
    assert report["summary"]["model_request_attempts"] == 0
    assert report["cases"][0]["error"] == "continuation_original_project_changed"


def test_continuation_budget_and_actual_model_id_are_enforced(tmp_path):
    path, digest = _prior_report(tmp_path)
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    with pytest.raises(ValueError, match="closed_loop_request_budget_invalid"):
        run_closed_loop(object(), development_continuation=continuation, allow_code_execution=True, maximum_requests=25)
    report = run_closed_loop(object(), complete=lambda *_: {"model": "other-model", "message": {"content": "{}"}},
        development_continuation=continuation, allow_code_execution=True, maximum_requests=12, max_model_calls=6,
        case_ids=[IDEAS[0]["id"]])
    assert report["summary"]["passed"] == 0
    assert report["cases"][0]["error"] == "ai_project_model_changed"


def test_restored_history_fits_real_provider_gate_and_preserves_latest_failure(tmp_path):
    from nsgablack.catalog.curation_provider import DeepSeekConfig
    from nsgablack.catalog.lab_assistant import DeepSeekAssemblyGenerator

    path, _ = _prior_report(tmp_path)
    prior = json.loads(path.read_bytes())
    generator = DeepSeekAssemblyGenerator(DeepSeekConfig(
        api_key="unused-local-stub", model="deepseek-flash", max_output_tokens=4000,
        timeout_seconds=90))
    prior["model_configuration"] = acceptance.model_configuration_metadata(generator.config)
    record = prior["requests"][0]
    record["model"] = "deepseek-flash"
    # Historical API data was already compacted by the previous runtime. Its
    # repeated per-method file metadata must not bypass post-restore compaction.
    from nsgablack.catalog.lab_api import inspect_framework_api
    evidence = inspect_framework_api("NSGA2Adapter")
    location = {key: evidence["sources"][0][key] for key in ("path", "sha256")}
    summary = {"schema": "nsgablack.lab_api/v1", "source_scope": "framework", "sources": [location], "context_evicted": True,
        "methods": [{"name": f"method_{i}", "signature": "(self, value)",
            "source": {**location, "line": i + 1, "end_line": i + 2}} for i in range(500)]}
    record["messages"][-1]["content"] = json.dumps(summary)
    latest_source = "def current_candidate():\n    return 3\n"
    latest_failure = {"code_sha256": source_digest(latest_source), "validation": {
        "status": "failed", "executed": True, "code_sha256": source_digest(latest_source),
        "failed_stage": "behavior", "error": "latest real failure marker"}}
    record["messages"].extend([
        {"role": "assistant", "content": "", "tool_calls": [{"id": "latest-check", "type": "function",
            "function": {"name": "check_project_edit", "arguments": json.dumps({"path": TARGET, "source": latest_source})}}]},
        {"role": "tool", "tool_call_id": "latest-check", "content": json.dumps(latest_failure)}])
    record["messages_sha256"] = content_digest(record["messages"])
    path.write_bytes(json.dumps(prior).encode())
    prior_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=prior_sha)

    class LocalStop(Exception):
        pass

    class StubOpener:
        def __init__(self):
            self.bodies = []

        def open(self, request, timeout=None):
            self.bodies.append(request.data)
            raise LocalStop("opener reached locally; no HTTP sent")

    opener = StubOpener()
    generator._opener = opener
    result = run_closed_loop(generator, maximum_requests=12, max_model_calls=12,
        development_continuation=continuation, case_ids=[IDEAS[0]["id"]], allow_code_execution=True)
    assert len(opener.bodies) == 1, result["cases"][0]
    assert len(opener.bodies[0]) <= 128 * 1024
    wire = json.loads(opener.bodies[0])
    messages = wire["messages"]
    latest_call = next(row for row in messages if row.get("tool_calls", [{}])[0].get("id") == "latest-check")
    assert json.loads(latest_call["tool_calls"][0]["function"]["arguments"])["source"] == latest_source
    latest_result = next(row for row in messages if row.get("tool_call_id") == "latest-check")
    assert json.loads(latest_result["content"]) == latest_failure
    old_summary = json.loads(next(row for row in messages if row.get("tool_call_id") == "past-read")["content"])
    assert old_summary["source_metadata_deduplicated"] is True
    assert len(old_summary["source_files"]) == 1
    assert old_summary["source_files"][0] == {"file_id": 0, **location}
    assert old_summary["api_details_evicted"] is True
    assert old_summary["methods_names"] == [f"method_{i}" for i in range(500)]
    assert "定向重新查询" in old_summary["notice"]
    projection = result["cases"][0]["continuation"]["first_request_projection"]
    assert projection["changed"] is True
    assert projection["sent_messages_bytes"] < projection["restored_messages_bytes"]
    assert result["requests"][0]["messages_sha256"] == content_digest(messages)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == prior_sha


@pytest.mark.parametrize("passed,exit_code", [(1, 0), (0, 1)])
def test_cli_selected_case_exit_matches_selected_total(tmp_path, monkeypatch, passed, exit_code):
    report = {"summary": {"passed": passed, "total": 1}}
    monkeypatch.setattr(acceptance, "load_assistant_model_config", lambda _: object())
    monkeypatch.setattr(acceptance, "create_assistant_generator", lambda _: object())
    monkeypatch.setattr(acceptance, "run_closed_loop", lambda *args, **kwargs: report)
    assert main(["--model-config", "local-unused.json", "--allow-paid", "--allow-code-execution",
        "--case", IDEAS[1]["id"], "--out", str(tmp_path / "result.json")]) == exit_code


def test_continuation_rejects_stale_shared_api_source_before_model(tmp_path):
    from nsgablack.catalog.lab_api import inspect_framework_api
    path, _ = _prior_report(tmp_path)
    prior = json.loads(path.read_bytes())
    evidence = inspect_framework_api("CandidateBatch")
    assert any(row["path"] == "@blackbase/types.py" for row in evidence["sources"])
    evidence["sources"][0]["sha256"] = "0" * 64
    record = prior["requests"][0]
    record["messages"][-1]["content"] = json.dumps(evidence)
    record["messages_sha256"] = content_digest(record["messages"])
    path.write_bytes(json.dumps(prior).encode())
    with pytest.raises(ValueError, match="api_source_changed"):
        acceptance.prepare_development_continuation(path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_continuation_rejects_model_call_id_collision_with_history(tmp_path):
    path, digest = _prior_report(tmp_path)
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    def complete(*_):
        return {"model": "one-model", "message": {"content": "", "tool_calls": [
            {"id": "past-read", "type": "function", "function": {"name": "framework_api", "arguments": '{"symbol":"CandidateBatch"}'}}]}}
    report = run_closed_loop(object(), complete=complete, development_continuation=continuation,
        allow_code_execution=True, maximum_requests=12, max_model_calls=12, case_ids=[IDEAS[0]["id"]])
    assert report["cases"][0]["error"] == "ai_project_tool_call_id_collision"


def _continued_report(tmp_path):
    root_path, _ = _prior_report(tmp_path)
    root = json.loads(root_path.read_bytes())
    root["transport"] = {"relay_request_attempts": 24, "records": [{} for _ in range(24)]}
    donor = deepcopy(root["cases"][0])
    donor["id"] = IDEAS[1]["id"]
    root["cases"].append(donor)
    donor_request = deepcopy(root["requests"][0])
    donor_request["idea"] = IDEAS[1]["id"]
    root["requests"].append(donor_request)
    root_path.write_bytes(json.dumps(root).encode())
    root_sha = hashlib.sha256(root_path.read_bytes()).hexdigest()
    link = acceptance.prepare_development_continuation(root_path, expected_sha256=root_sha)
    resumed = deepcopy(donor_request)
    resumed["request"] = 12
    resumed["visible_content"] = "<DSML>invalid final; not an accepted JSON response</DSML>"
    continued = {**root, "kind": "same_model_development_continuation", "cases": [donor], "requests": [resumed],
        "continuation": {key: value for key, value in link.items() if key != "cases"},
        "summary": {"model_request_attempts": 12, "prior_model_request_attempts": 24,
                    "cumulative_model_request_attempts": 36},
        "transport": {"prior_actual_http_requests": 24, "prior_local_preflight_failures": 1,
                      "relay_request_attempts": 12, "records": [{} for _ in range(12)]}}
    path = tmp_path / "continued.raw.json"
    path.write_bytes(json.dumps(continued).encode())
    return root_path, path


def test_chained_continuation_preserves_root_cases_and_separates_http_reservations(tmp_path):
    root, path = _continued_report(tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    profile = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    assert profile["prior_model_request_attempts"] == 36
    assert profile["report_chain"]["actual_http_requests"] == 36
    assert profile["report_chain"]["reservation_history"] == 37
    assert len(profile["report_chain"]["reports"]) == 2
    by_id = {row["id"]: row for row in profile["cases"]}
    assert set(by_id) == {row["id"] for row in IDEAS}
    assert by_id[IDEAS[0]["id"]]["history_report_sha256"] == hashlib.sha256(root.read_bytes()).hexdigest()
    assert by_id[IDEAS[1]["id"]]["history_report_sha256"] == digest
    assert by_id[IDEAS[1]["id"]]["last_response"] == "omitted_invalid_last_final"
    assert "DSML" not in json.dumps(by_id[IDEAS[1]["id"]]["history"])
    assert all(row["role"] != "system" for row in by_id[IDEAS[1]["id"]]["history"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("change,error", [("cumulative", "cumulative_request_accounting"),
    ("actual", "actual_request_accounting"), ("config", "report_chain_binding")])
def test_chained_continuation_rejects_counter_or_configuration_drift(tmp_path, change, error):
    _, path = _continued_report(tmp_path)
    report = json.loads(path.read_bytes())
    if change == "cumulative":
        report["summary"]["cumulative_model_request_attempts"] = 35
    elif change == "actual":
        report["transport"]["prior_actual_http_requests"] = 23
    else:
        report["model_configuration"] = {"model": "different"}
    path.write_bytes(json.dumps(report).encode())
    with pytest.raises(ValueError, match=error):
        acceptance.prepare_development_continuation(path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_chained_ancestor_change_blocks_every_later_request(tmp_path):
    root, path = _continued_report(tmp_path)
    profile = acceptance.prepare_development_continuation(path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    root.write_bytes(root.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="prior_report_changed"):
        acceptance._verify_development_continuation(profile)


def test_protocol_mode_is_host_metadata_and_extended_budget_is_bounded(tmp_path):
    path, digest = _prior_report(tmp_path)
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=digest)
    report = run_closed_loop(object(), complete=lambda *_: {"model": "other-model", "message": {"content": "{}"},
        "protocol": "json", "protocol_error": {"code": "invalid_envelope"},
        "protocol_wire_content": "exact unmodified public response"}, tool_protocol="json",
        development_continuation=continuation, allow_code_execution=True, maximum_requests=24, max_model_calls=14,
        case_ids=[IDEAS[0]["id"]])
    assert report["tool_protocol"] == "json" and report["model_calls_per_task"] == 14
    assert report["model_configuration"] is None
    assert report["requests"][0]["protocol_error"] == {"code": "invalid_envelope"}
    assert report["requests"][0]["protocol_wire_content"] == "exact unmodified public response"
    with pytest.raises(ValueError, match="closed_loop_model_budget_invalid"):
        run_closed_loop(object(), max_model_calls=21, allow_code_execution=True)


def test_declared_api_change_downgrades_old_body_and_requires_exact_hashes(tmp_path):
    from nsgablack.catalog.lab_api import inspect_framework_api
    path, _ = _prior_report(tmp_path)
    prior = json.loads(path.read_bytes())
    evidence = inspect_framework_api("ChangePool")
    source = next(row for row in evidence["sources"] if row["path"] == "adapters/change_pool.py")
    current_sha = source["sha256"]
    for row in evidence["sources"]:
        if row["path"] == source["path"]:
            row["sha256"] = "0" * 64
    request = prior["requests"][0]
    request["messages"][-1]["content"] = json.dumps(evidence)
    request["messages_sha256"] = content_digest(request["messages"])
    path.write_bytes(json.dumps(prior).encode())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    change = {"path": source["path"], "before_sha256": "0" * 64,
        "after_sha256": current_sha, "reason": "Host-declared annotation-only source update."}
    with pytest.raises(ValueError, match="api_source_changed"):
        acceptance.prepare_development_continuation(path, expected_sha256=digest)
    profile = acceptance.prepare_development_continuation(path, expected_sha256=digest, historical_api_changes=[change])
    tool = json.loads(next(row["content"] for row in profile["cases"][0]["history"] if row["role"] == "tool"))
    assert tool["historical_only"] is True and tool["sources"] == []
    assert "methods" not in tool and "member_names" not in tool
    assert tool["declared_source_changes"] == [change]
    assert "必须" in tool["notice"] and "重新查询" in tool["notice"]
    wrong = {**change, "before_sha256": "1" * 64}
    with pytest.raises(ValueError, match="api_source_changed"):
        acceptance.prepare_development_continuation(path, expected_sha256=digest, historical_api_changes=[wrong])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_actual_submitted_stack_context_contains_only_candidate_lines():
    source = GRID.replace("    if count < 0", '    raise ValueError("local context marker")\n    if count < 0', 1)
    result = execute_candidate(proposal(source), IDEAS[0]["id"])
    assert result["status"] == "failed" and result["failed_stage"] == "behavior"
    assert result["candidate_error_context"]
    assert any("local context marker" in row["excerpt"] for row in result["candidate_error_context"])
    assert all("_grid_behavior" not in row["excerpt"] for row in result["candidate_error_context"])


def test_minimal_api_pointer_is_a_stable_compaction_terminal_state():
    pointer = {"schema": "nsgablack.lab_api/v1", "source_scope": "framework", "context_evicted": True,
        "api_pointer_only": True, "symbol": "Example", "sources": [{"path": "source.py", "sha256": "0" * 64}]}
    messages = [{"role": "assistant", "content": "", "tool_calls": [{"id": "old-api", "type": "function",
        "function": {"name": "framework_api", "arguments": '{"symbol":"Example"}'}}]},
        {"role": "tool", "tool_call_id": "old-api", "content": json.dumps(pointer)},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "latest", "type": "function",
            "function": {"name": "check_project_edit", "arguments": '{"source":"current source"}'}}]}]
    before = deepcopy(messages)
    acceptance._compact_restored_context(messages, target_bytes=1)
    acceptance._compact_restored_context(messages, target_bytes=1)
    assert messages == before


def _novel_host_spec():
    from nsgablack.catalog import assistant_novel_acceptance as novel
    return acceptance.HostAcceptanceSpec("three_fresh_components/v1", novel.IDEAS, novel.TARGET,
        novel.INITIALIZATION_CONTRACT, novel.POLICY, novel.spec_identity, novel.oracle_math_sha256,
        novel.execution_guard_profile, novel.__file__, novel._contracts, 36)


def _novel_prior_report(tmp_path):
    spec = _novel_host_spec()
    sources, pid = create_teaching_project(tmp_path / "novel-prior")
    project = {"source_digest": sources.describe_project(pid)["source_digest"]}
    cases, requests = [], []
    for number, idea in enumerate(spec.ideas):
        status = "failed" if number == 2 else "passed"
        cases.append({"id": idea["id"], "status": status, "attempts": [],
                      "input": {"project_id": pid, "project": project}})
        messages = [{"role": "system", "content": "original novel system"},
            {"role": "user", "content": json.dumps({"project_id": pid, "project": project})},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "original-" + idea["id"],
                "type": "function", "function": {"name": "framework_api", "arguments": '{"symbol":"PopulationUnitBuilder"}'}}]},
            {"role": "tool", "tool_call_id": "original-" + idea["id"],
                "content": json.dumps({"historical_marker": "original " + idea["id"] + " " + status})}]
        requests.append({"idea": idea["id"], "request": number + 1 if number < 2 else 26,
            "messages": messages, "messages_sha256": content_digest(messages), "status": "received", "model": "one-model",
            "visible_content": json.dumps({"explanation": "original " + status, "questions": [],
                "proposal_digest": None, "edit_digest": "f" * 64}), "tool_calls": []})
    report = {"schema": acceptance.SCHEMA, "kind": "same_model_live_validation", "acceptance_profile": spec.name,
        "validation_identity": spec.identity(), "oracle_math_sha256": spec.math_identity(),
        "execution_guard_profile": spec.guard_profile(), "execution_policy": spec.execution_policy,
        "model_configuration": None, "cases": cases, "requests": requests,
        "summary": {"total": 3, "passed": 2, "model_request_attempts": 26, "cumulative_model_request_attempts": 26},
        "transport": {"relay_request_attempts": 26, "records": [{} for _ in range(26)]}}
    path = tmp_path / "novel-prior.raw.json"
    path.write_bytes(json.dumps(report).encode())
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), spec


def test_novel_continuation_requires_explicit_host_spec_and_preserves_first_score(tmp_path):
    path, digest, spec = _novel_prior_report(tmp_path)
    with pytest.raises(ValueError, match="continuation_oracle_changed"):
        acceptance.prepare_development_continuation(path, expected_sha256=digest)
    with pytest.raises(ValueError, match="host_acceptance_spec_invalid"):
        acceptance.prepare_development_continuation(path, expected_sha256=digest, acceptance_spec={"name": spec.name})
    value = acceptance.prepare_development_continuation(path, expected_sha256=digest, acceptance_spec=spec)
    assert value["prior_model_request_attempts"] == value["report_chain"]["actual_http_requests"] == 26
    assert value["acceptance_profile"] == spec.name and value["oracle_math_sha256"] == spec.math_identity()
    assert [row["prior_status"] for row in value["cases"]] == ["passed", "passed", "failed"]
    assert json.loads(path.read_bytes())["summary"]["passed"] == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("field", ["name", "math_identity", "identity", "guard_profile"])
def test_novel_continuation_rejects_wrong_host_profile(tmp_path, field):
    from dataclasses import replace
    path, digest, spec = _novel_prior_report(tmp_path)
    wrong = replace(spec, **{field: "other" if field == "name" else lambda: "other"})
    with pytest.raises(ValueError, match="continuation_oracle_changed"):
        acceptance.prepare_development_continuation(path, expected_sha256=digest, acceptance_spec=wrong)


def test_novel_c_continuation_revalidates_and_does_not_import_old_delivery_authority(tmp_path):
    path, digest, spec = _novel_prior_report(tmp_path)
    value = acceptance.prepare_development_continuation(path, expected_sha256=digest, acceptance_spec=spec)
    calls = 0
    source = "class AgePopulationUnit:\n    def on_members_changed(self, change): return {}\n"
    def complete(owner, messages, tools):
        nonlocal calls
        calls += 1
        assert any("original age_population_unit failed" in row.get("content", "") for row in messages)
        assert not any("original center_reflection_expansion passed" in row.get("content", "") for row in messages)
        if calls == 1:
            return {"model": "one-model", "message": {"content": json.dumps({"explanation": "old receipt", "questions": [],
                "proposal_digest": None, "edit_digest": "f" * 64})}}
        if calls == 2:
            return {"model": "one-model", "message": {"content": "", "tool_calls": [
                {"id": "new-age-check", "type": "function", "function": {"name": "check_project_edit",
                    "arguments": json.dumps({"path": spec.target, "source": source})}}]}}
        output = json.loads(messages[-1]["content"])
        assert output["edit_digest"] != "f" * 64
        return {"model": "one-model", "message": {"content": json.dumps({"explanation": "new validated receipt", "questions": [],
            "proposal_digest": None, "edit_digest": output["edit_digest"]})}}
    def execute(data, idea):
        return {"status": "passed", "executed": True, "code_sha256": data["code_sha256"],
            "executed_source_sha256": data["code_sha256"], "validation_identity": spec.identity()}
    report = run_closed_loop(object(), acceptance_spec=spec, complete=complete, executor=execute,
        development_continuation=value, allow_code_execution=True, maximum_requests=10, max_model_calls=10,
        case_ids=["age_population_unit"])
    assert report["summary"]["passed"] == 1, report["cases"][0]
    assert report["summary"]["cumulative_model_request_attempts"] == 29
    assert len(report["cases"][0]["attempts"]) == 1
    assert report["cases"][0]["answer"]["closed_loop"]["delivery_rejections"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_novel_continuation_enforces_remaining_family_budget_before_requests(tmp_path):
    path, digest, spec = _novel_prior_report(tmp_path)
    value = acceptance.prepare_development_continuation(path, expected_sha256=digest, acceptance_spec=spec)
    with pytest.raises(ValueError, match="cumulative_budget_exceeded"):
        run_closed_loop(object(), acceptance_spec=spec, development_continuation=value, allow_code_execution=True,
                        maximum_requests=11, max_model_calls=10, case_ids=["age_population_unit"])


def test_novel_old_api_metadata_is_marked_without_installing_new_field_facts(tmp_path):
    from nsgablack.catalog.lab_api import inspect_framework_api
    path, _, spec = _novel_prior_report(tmp_path)
    prior = json.loads(path.read_bytes())
    record = prior["requests"][-1]
    evidence = inspect_framework_api("PopulationUnitBuilder")
    record["messages"][-1]["content"] = json.dumps(evidence)
    record["messages_sha256"] = content_digest(record["messages"])
    path.write_bytes(json.dumps(prior).encode())
    value = acceptance.prepare_development_continuation(path,
        expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), acceptance_spec=spec)
    history = next(row for row in value["cases"] if row["id"] == "age_population_unit")["history"]
    result = json.loads(next(row["content"] for row in history if row["role"] == "tool"))
    assert result.pop("historical_api_metadata")["status"] == "previous_tool_version"
    assert result == evidence


def test_resume_background_projection_changes_only_rereadable_source_bodies():
    source = {"path": "cases/example/config.py", "sha256": "a" * 64}
    protected = {"path": "cases/example/proposed.py", "sha256": "b" * 64}
    packet = {"instruction": "keep exact algorithm intent", "project_id": "project", "project": {"source_digest": "c" * 64},
        "edit_validation": {"identity": "host"}, "edit_call_contracts": {"function.arg": "ActualType"},
        "project_state": {"source_digest": "c" * 64, "excerpts": [
            {"source": source, "excerpt": "readable background " * 200, "start_line": 1},
            {"source": protected, "excerpt": "latest candidate " * 200}]},
        "framework_context": {"contracts": [{"source": source, "text": "contract source " * 200,
            "code": "framework source " * 200, "summary": "keep this summary"}]}, "unrelated": "x" * 2000}
    host_packet = deepcopy(packet)
    history = [{"role": "assistant", "content": "", "tool_calls": [{"id": "current", "type": "function",
        "function": {"name": "check_project_edit", "arguments": '{"source":"latest source"}'}}]},
        {"role": "tool", "tool_call_id": "current", "content": '{"validation":{"error":"latest failure"}}'}]
    messages = [{"role": "system", "content": "host system"}, {"role": "user", "content": json.dumps(packet)}, *deepcopy(history)]
    result = acceptance._evict_resume_background(messages, protected_paths=(protected["path"],))
    projected = json.loads(messages[1]["content"])
    assert result["changed"] and len(result["evicted_bodies"]) == 3
    pointer = projected["project_state"]["excerpts"][0]["excerpt"]
    assert pointer["path"] == source["path"] and pointer["source_sha256"] == source["sha256"]
    assert pointer["content_sha256"] == source_digest(packet["project_state"]["excerpts"][0]["excerpt"])
    assert projected["project_state"]["excerpts"][1] == packet["project_state"]["excerpts"][1]
    for key in ("instruction", "project_id", "project", "edit_validation", "edit_call_contracts", "unrelated"):
        assert projected[key] == packet[key]
    assert messages[2:] == history and packet == host_packet
    again = acceptance._evict_resume_background(messages, protected_paths=(protected["path"],))
    assert again["changed"] is False


def test_real_novel_c_resume_and_unit_schema_query_fit_provider_with_headroom():
    from io import BytesIO
    from nsgablack.catalog import assistant_novel_acceptance as novel
    from nsgablack.catalog.curation_provider import DeepSeekConfig
    from nsgablack.catalog.lab_assistant import DeepSeekAssemblyGenerator
    path = Path(acceptance.__file__).resolve().parents[1] / "docs/user_guide/evidence/ai-novel-20261123.live-v2.raw.json"
    if not path.is_file():
        pytest.skip("frozen development report is not installed in this test checkout")
    prior_sha = "41ea245583fa5751aa97a42ddb53e25d6b036bb5070b97f3576639f42ddd25cb"
    spec = _novel_host_spec()
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=prior_sha, acceptance_spec=spec)
    history = next(row["history"] for row in continuation["cases"] if row["id"] == "age_population_unit")
    latest = [(call["id"], json.loads(call["function"]["arguments"])["source"])
        for row in history for call in row.get("tool_calls") or () if call["function"]["name"] == "check_project_edit"][-1]
    source_sha = source_digest(latest[1])
    validation = json.loads(next(row["content"] for row in history if row.get("tool_call_id") == latest[0]))["validation"]
    validation_sha = content_digest(validation)
    def contains(value, predicate, depth=0):
        if depth > 14:
            return False
        if isinstance(value, dict):
            return predicate(value) or any(contains(item, predicate, depth + 1) for item in value.values())
        if isinstance(value, list):
            return any(contains(item, predicate, depth + 1) for item in value)
        if isinstance(value, str) and value.startswith(("{", "[")):
            try:
                return contains(json.loads(value), predicate, depth + 1)
            except (ValueError, TypeError):
                pass
        return False
    class Response(BytesIO):
        def __init__(self, data, url):
            super().__init__(data)
            self.url = url
        def geturl(self): return self.url
    class LocalOpener:
        def __init__(self): self.bodies = []
        def open(self, request, timeout=None):
            self.bodies.append(request.data)
            if len(self.bodies) == 1:
                envelope = {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "UnitSchema"}}]}
                response = {"model": "deepseek-flash", "choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant", "content": json.dumps(envelope)}}]}
                return Response(json.dumps(response).encode(), request.full_url)
            raise RuntimeError("local test stops before HTTP")
    opener = LocalOpener()
    generator = DeepSeekAssemblyGenerator(DeepSeekConfig(api_key="unused-local-stub", model="deepseek-flash",
                                                       max_output_tokens=4096, timeout_seconds=60), opener=opener)
    report = novel.run_novel_acceptance(generator, tool_protocol="json", maximum_requests=10, max_model_calls=10,
        case_ids=["age_population_unit"], development_continuation=continuation, allow_code_execution=True)
    assert len(opener.bodies) == 2, report["cases"][0].get("error")
    assert all(len(body) <= 128 * 1024 - 10 * 1024 for body in opener.bodies)
    packet = report["cases"][0]["input"]
    assert isinstance(packet["project_state"]["excerpts"][0]["excerpt"], str)
    for request, body in zip(report["requests"], opener.bodies):
        projected = json.loads(request["messages"][1]["content"])
        for key in ("instruction", "project_id", "project", "edit_validation", "host_edit_validation", "edit_call_contracts"):
            if key in packet:
                assert projected[key] == packet[key]
        wire = json.loads(body)
        assert contains(wire, lambda data: isinstance(data.get("source"), str) and source_digest(data["source"]) == source_sha)
        assert contains(wire, lambda data: isinstance(data.get("validation"), dict) and content_digest(data["validation"]) == validation_sha)
    projection = report["cases"][0]["continuation"]["initial_background_projection"]
    assert projection["changed"] and projection["evicted_bodies"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == prior_sha


def test_latest_readonly_api_projection_preserves_semantics_and_edit_evidence():
    location = {"path": "units/contracts.py", "sha256": "a" * 64, "line": 1, "end_line": 50}
    contract = {"type": "UnitSchema", "callable": False, "source": location}
    leaf = {"name": "factory", "kind": "method", "owner": "Example", "source": location,
        "signature": "(self, value: int = 1) -> UnitSchema", "returns": "UnitSchema",
        "parameters": [{"name": "value", "annotation": "int", "default": "1"}],
        "return_contract": contract, "excerpt": "return UnitSchema(value)"}
    api = {"schema": "nsgablack.lab_api/v1", "status": "found", "query": "Example", "symbol": "Example",
        "source_scope": "framework", "source": location, "sources": [location], "member": leaf,
        "methods": [{key: value for key, value in leaf.items() if key not in {"return_contract", "excerpt"}}],
        "fields": [{"name": "schema", "annotation": "UnitSchema", "value_contract": contract, "source": location}],
        "excerpt": "long source body\n" * 200}
    edit = {"role": "assistant", "content": "", "tool_calls": [{"id": "edit", "type": "function",
        "function": {"name": "check_project_edit", "arguments": '{"path":"current.py","source":"latest candidate"}'}}]}
    error = {"role": "tool", "tool_call_id": "edit", "content": '{"validation":{"error":"latest error","code_sha256":"exact"}}'}
    messages = [{"role": "system", "content": "host"}, {"role": "user", "content": '{"instruction":"exact","edit_call_contracts":{"arg":"Type"}}'},
        deepcopy(edit), deepcopy(error), {"role": "assistant", "content": "", "tool_calls": [{"id": "api", "type": "function",
            "function": {"name": "framework_api", "arguments": '{"symbol":"Example"}'}}]},
        {"role": "tool", "tool_call_id": "api", "content": json.dumps(api)}]
    protected = deepcopy(messages[:5])
    acceptance._compact_restored_context(messages, target_bytes=1)
    result = json.loads(messages[-1]["content"])
    assert messages[:5] == protected
    assert result["member"]["signature"] == leaf["signature"]
    assert result["member"]["return_contract"] == contract
    assert result["member"]["excerpt"] == leaf["excerpt"]
    assert result["fields"][0]["annotation"] == "UnitSchema"
    assert result["fields"][0]["value_contract"] == contract
    assert result["excerpt"]["context_evicted"] is True
    assert result["excerpt"]["content_sha256"] == source_digest(api["excerpt"])
    assert any(row["path"] == location["path"] and row["sha256"] == location["sha256"] for row in result["source_files"])


def test_real_three_round_trace_and_next_resume_fit_after_api_projection():
    from io import BytesIO
    from nsgablack.catalog import assistant_novel_acceptance as novel
    from nsgablack.catalog.curation_provider import DeepSeekConfig
    from nsgablack.catalog.lab_assistant import DeepSeekAssemblyGenerator
    from nsgablack.catalog.lab_model_provider import complete_project_turn
    path = Path(acceptance.__file__).resolve().parents[1] / "docs/user_guide/evidence/ai-novel-20261123.unit-continuation.raw.json"
    if not path.is_file():
        pytest.skip("frozen development trace is not installed")
    digest = "b6666f539af5f59de3c033e9d88cc8bd370fb289cd08a7c1471916615b8a66ab"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    trace = json.loads(path.read_bytes())
    class Stop:
        def __init__(self): self.bodies = []
        def open(self, request, timeout=None):
            self.bodies.append(request.data)
            raise RuntimeError("local stop before HTTP")
    opener = Stop()
    generator = DeepSeekAssemblyGenerator(DeepSeekConfig(api_key="unused-local-stub", model="deepseek-flash",
        max_output_tokens=4096, timeout_seconds=60), opener=opener)
    with pytest.raises(Exception, match="ai_packet_too_large"):
        complete_project_turn(generator, deepcopy(trace["requests"][-1]["messages"]), trace["requests"][-1]["tools"], protocol="json")
    assert opener.bodies == []
    def source_ids(value):
        if not isinstance(value, dict): return set()
        files = {row["file_id"]: row for row in value.get("source_files", ())}
        result = set()
        for row in value.get("sources", ()):
            source = files[row["file_id"]] if "file_id" in row else row
            result.add((source["path"], source["sha256"]))
        return result
    def facts(value):
        out = {}
        for row in [*value.get("methods", ()), *value.get("fields", ()), value.get("member", {})]:
            if isinstance(row, dict) and "name" in row:
                out.setdefault(row["name"], {}).update({key: row[key] for key in
                    ("signature", "returns", "annotation", "value_contract", "return_contract") if key in row})
        return out
    measured = []
    for request in trace["requests"]:
        messages = deepcopy(request["messages"])
        original = deepcopy(messages)
        acceptance._evict_resume_background(messages, protected_paths=(novel.TARGET,))
        acceptance._compact_restored_context(messages, target_bytes=48 * 1024)
        latest = max(i for i, row in enumerate(original) if row.get("tool_calls"))
        before_sources, after_sources = set(), set()
        for index, (before, after) in enumerate(zip(original, messages)):
            assert before.get("tool_calls") == after.get("tool_calls")
            assert before.get("tool_call_id") == after.get("tool_call_id")
            if before.get("role") != "tool": continue
            try: first, second = json.loads(before["content"]), json.loads(after["content"])
            except (ValueError, TypeError): continue
            if first.get("schema") == "nsgablack.lab_api/v1":
                before_sources.update(source_ids(first)); after_sources.update(source_ids(second))
                if index >= latest:
                    expected, actual = facts(first), facts(second)
                    for name, values in expected.items():
                        for key, value in values.items():
                            assert actual[name][key] == value, (name, key)
            elif "validation" in first:
                assert first["validation"] == second["validation"]
        assert before_sources == after_sources
        with pytest.raises(Exception, match="ai_response_invalid"):
            complete_project_turn(generator, messages, request["tools"], protocol="json", feedback_protocol_errors=True)
        measured.append(len(opener.bodies[-1]))
    assert len(measured) == 3 and max(measured) < 118000, measured
    spec = _novel_host_spec()
    continuation = acceptance.prepare_development_continuation(path, expected_sha256=digest, acceptance_spec=spec)
    assert continuation["report_chain"]["actual_http_requests"] == 28
    assert continuation["report_chain"]["reservation_history"] == 29
    with pytest.raises(ValueError, match="cumulative_budget_exceeded"):
        novel.run_novel_acceptance(object(), maximum_requests=8, max_model_calls=7, development_continuation=continuation,
            case_ids=["age_population_unit"], allow_code_execution=True)
    class Response(BytesIO):
        def __init__(self, data, url): super().__init__(data); self.url = url
        def geturl(self): return self.url
    class LookupThenStop:
        def __init__(self): self.bodies = []
        def open(self, request, timeout=None):
            self.bodies.append(request.data)
            if len(self.bodies) == 1:
                content = {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "UnitSchema"}}]}
                return Response(json.dumps({"model": "deepseek-flash", "choices": [{"finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(content)}}]}).encode(), request.full_url)
            raise RuntimeError("local stop before HTTP")
    lookup = LookupThenStop(); generator._opener = lookup
    report = novel.run_novel_acceptance(generator, maximum_requests=7, max_model_calls=7, development_continuation=continuation,
        case_ids=["age_population_unit"], allow_code_execution=True, tool_protocol="json")
    assert len(lookup.bodies) == 2, report["cases"][0].get("error")
    assert max(map(len, lookup.bodies)) < 118000, list(map(len, lookup.bodies))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
