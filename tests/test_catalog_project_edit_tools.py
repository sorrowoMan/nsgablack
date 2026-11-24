import json
from copy import deepcopy

import pytest

from nsgablack.catalog.assistant_session_acceptance import create_teaching_project
from nsgablack.catalog.lab_assistant import AssistantProviderError
from nsgablack.catalog.lab_jobs import LabJobError
from nsgablack.catalog.lab_project_assistant import ProjectAssistantRuntime


def prepared(tmp_path, complete=None):
    sources, identity = create_teaching_project(tmp_path)
    runtime = ProjectAssistantRuntime(sources, complete=complete)
    packet = runtime.prepare({"project_id": identity, "instruction": "Implement a new variation without changing the Problem", "history": []})
    return runtime, packet


def answer(edit=None):
    return {"message": {"role": "assistant", "content": json.dumps({"explanation": "Source proposal only; not applied or executed.",
        "questions": [], "proposal_digest": None, "edit_digest": edit})}, "model": "test"}


def test_host_call_contract_types_are_source_bound_and_scoped(tmp_path):
    sources, identity = create_teaching_project(tmp_path)
    path = "cases/hybrid_search/adapter/new_change.py"
    contracts = {path: {"op.request": "nsgablack.adapters.ChangeRequest"}}
    runtime = ProjectAssistantRuntime(sources, edit_call_contracts=contracts)
    packet = runtime.prepare({"project_id": identity, "instruction": "Modify a callback", "history": []})
    assert packet["edit_call_contracts"]["origin"] == "host_declared_caller_abi"
    contracts[path]["op.request"] = "nsgablack.adapters.ChangeSelection"
    assert runtime.edit_call_contracts[path]["op.request"] == "nsgablack.adapters.ChangeRequest"
    source = "def op(request):\n    return request.this_member_does_not_exist()\ndef helper(request):\n    return request.untyped_helper_member()\n"
    result = runtime._dispatch("check_project_edit", {"path": path, "source": source}, packet)
    assert result["check"]["status"] == "rejected"
    assert result["check"]["host_call_parameter_types"] == runtime.edit_call_contracts[path]
    assert result["check"]["binding_assumptions"] == {}
    assert any(row["severity"] == "error" and row["line"] == 2 for row in result["check"]["diagnostics"])
    assert not any(row["severity"] == "error" and row["line"] == 4 for row in result["check"]["diagnostics"])


def test_host_call_contract_can_scope_a_unit_method_without_binding_self(tmp_path):
    sources, identity = create_teaching_project(tmp_path)
    path = "cases/hybrid_search/adapter/new_unit.py"
    runtime = ProjectAssistantRuntime(sources, edit_call_contracts={path: {
        "FreshUnit.on_members_changed.change": "nsgablack.units.population_operations.PopulationChange"}})
    packet = runtime.prepare({"project_id": identity, "instruction": "Add a member field", "history": []})
    source = "class FreshUnit:\n    def on_members_changed(self, change):\n        return change.previous_member_indices()\n"
    result = runtime._dispatch("check_project_edit", {"path": path, "source": source}, packet)
    assert result["check"]["status"] == "rejected"
    assert any(item["line"] == 3 and item["severity"] == "error" for item in result["check"]["diagnostics"])


def test_model_cannot_override_host_call_contract_or_submit_it_in_request(tmp_path):
    sources, identity = create_teaching_project(tmp_path)
    path = "cases/hybrid_search/adapter/new_change.py"
    runtime = ProjectAssistantRuntime(sources, edit_call_contracts={path: {"op.request": "nsgablack.adapters.ChangeRequest"}})
    packet = runtime.prepare({"project_id": identity, "instruction": "Modify a callback", "history": []})
    with pytest.raises(ValueError, match="project_edit_call_contract_conflict"):
        runtime._dispatch("check_project_edit", {"path": path, "source": "def op(request): return request\n",
            "bindings": {"op.request": "nsgablack.adapters.Pool"}}, packet)
    equivalent = runtime._dispatch("check_project_edit", {"path": path,
        "source": "def op(request): return request.max_outputs\n",
        "bindings": {"op.request": "nsgablack.adapters.change.ChangeRequest"}}, packet)
    assert equivalent["check"]["status"] != "rejected"
    with pytest.raises(LabJobError) as rejected:
        runtime.prepare({"project_id": identity, "instruction": "Modify", "history": [], "edit_call_contracts": {}})
    assert rejected.value.code == "invalid_project_request"
    runtime.edit_call_contracts[path]["op.request"] = "nsgablack.adapters.Pool"
    with pytest.raises(AssistantProviderError, match="ai_framework_mismatch"):
        runtime._verify_project_state(packet)


@pytest.mark.parametrize("contracts", [[], {"../x.py": {}}, {"cases/x/y.py": {"request": "Pool"}}])
def test_invalid_host_call_contract_is_not_accepted(contracts):
    with pytest.raises(ValueError, match="project_edit_call_contract_invalid"):
        ProjectAssistantRuntime(None, edit_call_contracts=contracts)


def test_protocol_rejection_returns_to_same_model_without_executing_text(tmp_path):
    count = 0
    raw = "<DSML>not an executable tool call</DSML>"
    def complete(_generator, messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return {"model": "test", "message": {"role": "assistant", "content": raw},
                "protocol_error": {"code": "ai_project_tool_protocol_invalid"}}
        assert messages[-2] == {"role": "assistant", "content": raw}
        assert json.loads(messages[-1]["content"])["code"] == "ai_project_tool_protocol_invalid"
        return answer()
    runtime, packet = prepared(tmp_path, complete)
    result = runtime.generate(packet, object())
    assert count == 2 and result["tool_trace"] == []


def test_protocol_rejection_is_bounded_not_an_automatic_retry(tmp_path):
    calls = []
    def complete(*_):
        calls.append(1)
        return {"model": "test", "message": {"role": "assistant", "content": "invalid JSON"},
            "protocol_error": {"code": "ai_project_tool_protocol_invalid"}}
    runtime, packet = prepared(tmp_path, complete)
    runtime.max_model_calls = 1
    with pytest.raises(AssistantProviderError, match="ai_project_tool_protocol_invalid"):
        runtime.generate(packet, object())
    assert len(calls) == 1


def test_host_selected_protocol_is_bound_before_model_call(tmp_path):
    sources, identity = create_teaching_project(tmp_path)
    runtime = ProjectAssistantRuntime(sources, tool_protocol="json", complete=lambda *_: answer())
    packet = runtime.prepare({"project_id": identity, "instruction": "Discuss", "history": []})
    assert packet["tool_protocol"] == runtime.capabilities()["tool_protocol"] == "json"
    runtime.tool_protocol = "native"
    with pytest.raises(AssistantProviderError, match="ai_project_protocol_invalid"):
        runtime.generate(packet, object())


def test_compaction_preserves_source_backed_field_value_contract():
    contract = {"kind": "instance", "symbol": "nsgablack.units.contracts.UnitSchema",
                "basis": "declared_factory_return_annotation", "runtime_validated": False,
                "sources": [{"path": "units/structures.py", "sha256": "a" * 64}]}
    messages = [{"role": "system", "content": "host"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "old", "type": "function",
            "function": {"name": "framework_api", "arguments": '{"symbol":"PopulationUnit"}'}}]},
        {"role": "tool", "tool_call_id": "old", "content": json.dumps({"schema": "nsgablack.lab_api/v1",
            "status": "found", "symbol": "PopulationUnit", "source_scope": "framework",
            "fields": [{"name": "schema", "kind": "declared_field", "annotation": "ClassVar",
                        "value_contract": contract, "default": "x" * 9000}]})},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "new", "type": "function",
            "function": {"name": "project_files", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "new", "content": '{"files":[]}'}]
    ProjectAssistantRuntime._compact_context(messages, target_bytes=2500)
    compacted = json.loads(messages[2]["content"])
    assert compacted["context_evicted"] is True
    assert compacted["fields"][0]["value_contract"] == contract


def test_project_budget_is_computed_from_saved_source_without_running_case(tmp_path):
    runtime, packet = prepared(tmp_path)
    result = runtime._dispatch("project_config_values", {"path": "cases/hybrid_search/config.py", "symbol": "DemoConfig",
        "values": {"ga_steps": 7, "population_size": 50, "elite_count": 3, "local_steps": 2,
                   "refinement_source": "elite", "schedule": "plan", "rounds": 4},
        "properties": ["refinement_count", "max_steps"]}, packet)
    assert result["properties"] == {"refinement_count": 3, "max_steps": 57}
    assert result["source"]["path"] == "cases/hybrid_search/config.py"
    api = runtime._dispatch("framework_api", {"symbol": "DemoConfig", "member": "max_steps",
        "project_path": "cases/hybrid_search/config.py"}, packet)
    assert "ga_steps" in json.dumps(api) and api["status"] == "found"


def test_three_known_object_errors_have_source_based_automatic_answers(tmp_path):
    runtime, packet = prepared(tmp_path)
    for symbol, member in (("SolutionPool", "subpool"), ("DecompositionUnit", "nr")):
        result = runtime._dispatch("framework_api", {"symbol": symbol, "member": member}, packet)
        assert result["member_status"] in {"not_declared", "unknown"}
        assert member not in result.get("member_names", [])
    real = runtime._dispatch("framework_api", {"symbol": "MOEADConfig", "member": "nr"}, packet)
    assert real["member_status"] == "found"


def test_invalid_pool_method_is_rejected_and_cannot_be_final_edit(tmp_path):
    runtime, packet = prepared(tmp_path)
    args = {"path": "cases/hybrid_search/adapter/novel.py",
        "source": "from nsgablack.core.state.solution_pool import SolutionPool\ndef choose(pool: SolutionPool):\n    return pool.subpool('archive').random(2)\n"}
    result = runtime._dispatch("check_project_edit", args, packet)
    assert result["check"]["status"] == "rejected"
    assert not result["applied"] and not result["executed"]
    runtime.complete = lambda *_: answer(result["edit_digest"])
    with pytest.raises(AssistantProviderError, match="ai_project_response_invalid"):
        runtime.generate(packet, object())


def test_actual_source_proposal_is_hash_bound_but_still_needs_behavior_validation(tmp_path):
    calls = 0
    source = "from nsgablack.core.state.solution_pool import SolutionPool\ndef refs(pool: SolutionPool, name):\n    return pool.subpool_refs(name)\n"
    def complete(_generator, messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"model": "test", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "edit1", "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
                    "path": "cases/hybrid_search/adapter/novel.py", "source": source})}}]}}
        checked = json.loads(messages[-1]["content"])
        return answer(checked["edit_digest"])
    runtime, packet = prepared(tmp_path, complete)
    result = runtime.generate(packet, object())
    edit = result["edit_proposal"]
    assert edit["source"] == source
    assert edit["check"]["status"] == "needs_runtime_validation"
    assert result["verification_status"] == "not_run"
    assert not edit["applied"] and not edit["executed"]
    assert not (runtime.sources.resolve_project(packet["project_id"]) / edit["path"]).exists()


@pytest.mark.parametrize("path", ["../outside.py", "project_config.py", "cases/missing/adapter/a.py", "cases/hybrid_search/absent/new.py"])
def test_edit_checks_do_not_introduce_new_paths_or_cases(tmp_path, path):
    runtime, packet = prepared(tmp_path)
    with pytest.raises(ValueError):
        runtime._dispatch("check_project_edit", {"path": path, "source": "pass\n"}, packet)


def test_dynamic_interface_evidence_drift_during_model_turn_refuses_delivery(tmp_path, monkeypatch):
    from nsgablack.catalog import lab_api
    turns = 0
    def complete(*_):
        nonlocal turns
        turns += 1
        if turns == 1:
            return {"model": "test", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "api1", "type": "function", "function": {"name": "framework_api", "arguments": '{"symbol":"SolutionPool"}'}}]}}
        def changed(_):
            raise ValueError("drift")
        monkeypatch.setattr(lab_api, "verify_api_sources", changed)
        return answer()
    runtime, packet = prepared(tmp_path, complete)
    with pytest.raises(AssistantProviderError, match="ai_framework_mismatch"):
        runtime.generate(packet, object())


def test_context_eviction_keeps_resolved_api_signatures_instead_of_forcing_requery():
    messages = [{"role": "system", "content": "base"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "old", "function": {"name": "framework_api"}}]},
        {"role": "tool", "tool_call_id": "old", "content": json.dumps({"schema": "nsgablack.lab_api/v1",
            "symbol": "nsgablack.core.state.solution_pool.SolutionPool", "source_scope": "framework",
            "member_names": ["read", "subpool_refs"], "methods": [{"name": "subpool_refs", "signature": "subpool_refs(self, name)",
                "parameters": [{"name": "name"}], "source": {"path": "core/state/solution_pool.py", "sha256": "a" * 64}}],
            "member": {"name": "subpool_refs", "signature": "subpool_refs(self, name)", "excerpt": "x" * 20000}})},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "latest", "function": {"name": "project_read"}}]},
        {"role": "tool", "tool_call_id": "latest", "content": "{}"}]
    ProjectAssistantRuntime._compact_context(messages, target_bytes=2000)
    retained = json.loads(messages[2]["content"])
    assert retained["context_evicted"]
    assert retained["member"]["signature"] == "subpool_refs(self, name)"
    assert retained["member_names"] == ["read", "subpool_refs"]
    assert "excerpt" not in retained["member"]


def test_budget_reserves_real_check_and_final_phases_instead_of_only_prompting(tmp_path):
    offered = []
    def complete(_owner, _messages, tools):
        offered.append({tool["function"]["name"] for tool in tools})
        if len(offered) < 3:
            return {"model": "test", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": str(len(offered)), "type": "function", "function": {"name": "framework_api", "arguments": '{"symbol":"SolutionPool"}'}}]}}
        return answer()
    runtime, packet = prepared(tmp_path, complete)
    runtime.max_model_calls = 3
    result = runtime.generate(packet, object())
    assert "framework_api" in offered[0]
    assert offered[1] == {"check_project_edit", "propose_project_trial", "project_result"}
    assert offered[2] == set()
    assert result["tool_trace"][1]["ok"] is False
    assert result["edit_proposal"] is None and result["verification_status"] == "not_run"


def test_host_validator_returns_real_behavior_failure_to_model_then_checks_repair(tmp_path):
    checks = []
    def validator(proposal):
        namespace = {}
        # These two fixed, harmless test fixtures exercise the host callback;
        # the public assistant never supplies an executor through a request.
        exec(proposal["source"], namespace)
        passed = namespace["transform"](3) == 4
        checks.append(passed)
        return {"status": "passed" if passed else "failed", "code_sha256": proposal["code_sha256"],
                "executed": True, "error": None if passed else "transform(3) was not 4"}
    calls = 0
    def complete(_owner, messages, _tools):
        nonlocal calls
        calls += 1
        if calls <= 2:
            if calls == 2:
                feedback = json.loads(messages[-1]["content"])
                assert feedback["validation"]["status"] == "failed"
                assert feedback["validation"]["error"] == "transform(3) was not 4"
            source = "def transform(value):\n    return value " + ("- 1\n" if calls == 1 else "+ 1\n")
            return {"model": "test", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": str(calls), "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
                    "path": "cases/hybrid_search/adapter/novel.py", "source": source})}}]}}
        checked = json.loads(messages[-1]["content"])
        return answer(checked["edit_digest"])
    runtime, packet = prepared(tmp_path, complete)
    runtime.edit_validator = validator
    result = runtime.generate(packet, object())
    assert checks == [False, True]
    assert result["edit_proposal"]["validation"]["status"] == "passed"
    assert result["edit_proposal"]["executed"] is True
    assert result["edit_proposal"]["original_project_changed"] is False
    assert result["verification_status"] == "not_run"


def test_failed_behavior_digest_cannot_be_delivered_as_an_accepted_edit(tmp_path):
    calls = 0
    def complete(_owner, messages, _tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"model": "test", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "bad", "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
                    "path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"})}}]}}
        return answer(json.loads(messages[-1]["content"])["edit_digest"])
    runtime, packet = prepared(tmp_path, complete)
    runtime.edit_validator = lambda proposal: {"status": "failed", "code_sha256": proposal["code_sha256"]}
    with pytest.raises(AssistantProviderError, match="ai_project_response_invalid"):
        runtime.generate(packet, object())


def test_validation_receipt_for_other_source_is_rejected(tmp_path):
    runtime, packet = prepared(tmp_path)
    runtime.edit_validator = lambda proposal: {"status": "passed", "code_sha256": "0" * 64}
    with pytest.raises(ValueError, match="project_edit_validation_unbound"):
        runtime._dispatch("check_project_edit", {"path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"}, packet)


def test_validator_exception_is_failed_feedback_without_exception_secrets(tmp_path):
    runtime, packet = prepared(tmp_path)
    def broken(_):
        raise RuntimeError("secret-detail-must-not-leak")
    runtime.edit_validator = broken
    checked = runtime._dispatch("check_project_edit", {"path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"}, packet)
    assert checked["validation"]["status"] == "failed"
    assert "secret-detail" not in json.dumps(checked)


def test_same_source_recheck_failure_invalidates_earlier_passed_receipt(tmp_path):
    checks = 0
    calls = 0
    def validator(proposal):
        nonlocal checks
        checks += 1
        return {"status": "passed" if checks == 1 else "failed", "code_sha256": proposal["code_sha256"]}
    def complete(_owner, messages, _tools):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return {"model": "test", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": str(calls), "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
                    "path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"})}}]}}
        return answer(json.loads(messages[-1]["content"])["edit_digest"])
    runtime, packet = prepared(tmp_path, complete)
    runtime.edit_validator = validator
    with pytest.raises(AssistantProviderError, match="ai_project_response_invalid"):
        runtime.generate(packet, object())
    assert checks == 2


def strict_prepared(tmp_path, complete, validator, *, max_model_calls=12, identity="fixed-transform/v1"):
    sources, project_id = create_teaching_project(tmp_path)
    runtime = ProjectAssistantRuntime(sources, complete=complete, edit_validator=validator,
        require_validated_edit=True, validation_identity=identity,
        max_model_calls=max_model_calls, max_tool_calls=60)
    return runtime, runtime.prepare({"project_id": project_id, "instruction": "Implement and validate a source edit", "history": []})


def source_call(identity, source):
    return {"model": "same-model", "message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": identity, "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
            "path": "cases/hybrid_search/adapter/novel.py", "source": source})}}]}}


def api_call(identity):
    return {"model": "same-model", "message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": identity, "type": "function", "function": {"name": "framework_api", "arguments": '{"symbol":"SolutionPool","member":"read"}'}}]}}


def strict_answer(edit=None):
    result = answer(edit)
    result["model"] = "same-model"
    return result


def transform_validator(proposal):
    namespace = {}
    # Predetermined harmless source fixtures, not an executor exposed to clients.
    exec(proposal["source"], namespace)
    passed = namespace["transform"](3) == 4
    return {"status": "passed" if passed else "failed", "executed": True,
            "code_sha256": proposal["code_sha256"], "executed_source_sha256": proposal["code_sha256"],
            "validation_identity": "fixed-transform/v1", "error": None if passed else "transform(3) was not 4"}


def test_strict_same_model_reads_real_failure_queries_api_repairs_and_delivers(tmp_path):
    calls, owner_ids, feedback = 0, [], []
    def complete(owner, messages, tools):
        nonlocal calls
        owner_ids.append(id(owner))
        calls += 1
        names = {tool["function"]["name"] for tool in tools}
        if calls == 1:
            assert "实际运行" in next(tool["function"]["description"] for tool in tools
                                    if tool["function"]["name"] == "check_project_edit")
            assert "fixed-transform/v1" in messages[-1]["content"]
            return source_call("wrong", "def transform(value):\n    return value - 1\n")
        if calls == 2:
            result = json.loads(messages[-1]["content"])
            feedback.append(result["validation"]["error"])
            assert "framework_api" in names
            return api_call("inspect-error")
        if calls == 3:
            assert any("transform(3) was not 4" in message.get("content", "") for message in messages)
            return source_call("repair", "def transform(value):\n    return value + 1\n")
        assert names == set()
        result = json.loads(messages[-1]["content"])
        return strict_answer(result["edit_digest"])
    runtime, packet = strict_prepared(tmp_path, complete, transform_validator)
    owner = object()
    result = runtime.generate(packet, owner)
    loop = result["closed_loop"]
    assert set(owner_ids) == {id(owner)} and result["models"] == ["same-model"]
    assert feedback == ["transform(3) was not 4"]
    assert [attempt["status"] for attempt in loop["attempts"]] == ["validation_failed", "passed"]
    assert [stage["phase"] for stage in loop["phase_history"]] == ["discovery", "inspect_failure", "inspect_failure", "final"]
    assert loop["status"] == "passed" and loop["model"] == "same-model"
    assert result["edit_proposal"]["validation"]["validation_identity"] == "fixed-transform/v1"
    assert result["edit_verification_status"] == "passed_temporary_project"
    assert result["verification_status"] == "not_run"


def test_strict_bounded_discovery_forces_first_test_and_keeps_repair_reads(tmp_path):
    calls, offered = 0, []
    def complete(_owner, messages, tools):
        nonlocal calls
        calls += 1
        names = {tool["function"]["name"] for tool in tools}
        offered.append(names)
        if calls <= 3:
            return api_call(str(calls))
        if calls == 4:
            assert names == {"check_project_edit"}
            return source_call("first", "def transform(value):\n    return value - 1\n")
        if calls <= 6:
            assert "framework_api" in names
            return api_call(str(calls))
        if calls == 7:
            assert names == {"check_project_edit"}
            return source_call("fixed", "def transform(value):\n    return value + 1\n")
        return strict_answer(json.loads(messages[-1]["content"])["edit_digest"])
    runtime, packet = strict_prepared(tmp_path, complete, transform_validator)
    result = runtime.generate(packet, object())
    assert len(offered) == 8
    assert result["closed_loop"]["attempts"][1]["model_call"] == 7


def test_strict_early_unverified_final_is_feedback_in_same_conversation(tmp_path):
    calls = 0
    def complete(_owner, messages, _tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            return strict_answer()
        if calls == 2:
            feedback = json.loads(messages[-1]["content"])
            assert feedback["code"] == "validated_edit_required"
            assert messages[-2]["role"] == "assistant"
            return source_call("valid", "def transform(value):\n    return value + 1\n")
        return strict_answer(json.loads(messages[-1]["content"])["edit_digest"])
    runtime, packet = strict_prepared(tmp_path, complete, transform_validator)
    result = runtime.generate(packet, object())
    assert result["model_calls"] == 3
    assert result["closed_loop"]["delivery_rejections"] == [{"model_call": 1, "code": "validated_edit_required"}]


@pytest.mark.parametrize("validation", [{"status": "passed", "executed": False}, {"status": "not_run", "executed": False}])
def test_strict_static_or_unexecuted_receipt_cannot_succeed_at_budget_limit(tmp_path, validation):
    calls = 0
    def complete(*_):
        nonlocal calls
        calls += 1
        return (source_call(str(calls), "pass\n") if calls == 1 else strict_answer())
    def validator(proposal):
        return {**validation, "code_sha256": proposal["code_sha256"]}
    runtime, packet = strict_prepared(tmp_path, complete, validator, max_model_calls=5)
    with pytest.raises(AssistantProviderError, match="ai_project_validated_edit_missing"):
        runtime.generate(packet, object())
    assert calls == 5


def test_strict_rejects_model_switch_without_accepting_rescued_answer(tmp_path):
    calls = 0
    def complete(*_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return api_call("first")
        turn = strict_answer()
        turn["model"] = "another-model"
        return turn
    runtime, packet = strict_prepared(tmp_path, complete, transform_validator)
    with pytest.raises(AssistantProviderError, match="ai_project_model_changed"):
        runtime.generate(packet, object())
    assert calls == 2


def test_strict_configuration_and_profile_are_not_client_installed(tmp_path):
    runtime, _ = prepared(tmp_path)
    for values in ({"edit_validator": None, "max_model_calls": 12, "validation_identity": "x"},
                   {"edit_validator": transform_validator, "max_model_calls": 4, "validation_identity": "x"},
                   {"edit_validator": transform_validator, "max_model_calls": 12}):
        with pytest.raises(ValueError):
            ProjectAssistantRuntime(runtime.sources, require_validated_edit=True, **values)
    with pytest.raises(Exception):
        runtime.prepare({"project_id": "unused", "instruction": "x", "edit_validator": "install"})
    a, pa = strict_prepared(tmp_path / "a", None, transform_validator, identity="tests/v1")
    b = ProjectAssistantRuntime(a.sources, edit_validator=transform_validator,
        require_validated_edit=True, validation_identity="tests/v2")
    pb = b.prepare({"project_id": pa["project_id"], "instruction": pa["instruction"], "history": []})
    assert pa["base_digest"] != pb["base_digest"]
    with pytest.raises(AssistantProviderError, match="ai_project_validation_profile_mismatch"):
        b.generate(pa, object())


def test_multiple_large_failed_candidates_compact_without_erasing_latest_source_or_error():
    sources = ["# candidate-" + str(i) + "\n" + "#" * 23000 for i in range(3)]
    messages = [{"role": "system", "content": "fixed basics"}]
    for index, source in enumerate(sources):
        turn = source_call(str(index), source)["message"]
        messages.append(turn)
        messages.append({"role": "tool", "tool_call_id": str(index), "content": json.dumps({
            "edit_digest": str(index) * 64, "code_sha256": str(index) * 64,
            "path": "cases/search/adapter/operator.py", "check": {"status": "needs_runtime_validation", "unresolved": ["x" * 20000]},
            "validation": {"status": "failed", "executed": True, "error": "latest real traceback" if index == 2 else "older failure"}})})
    messages.append(api_call("last-read")["message"])
    messages.append({"role": "tool", "tool_call_id": "last-read", "content": "{}"})
    original_trace = deepcopy(messages)
    ProjectAssistantRuntime._compact_context(messages, target_bytes=64 * 1024)
    old = json.loads(messages[1]["tool_calls"][0]["function"]["arguments"])
    latest = json.loads(messages[5]["tool_calls"][0]["function"]["arguments"])
    assert old["source"].startswith("# context_evicted:")
    assert latest["source"] == sources[-1]
    assert json.loads(messages[6]["content"])["validation"]["error"] == "latest real traceback"
    assert len(json.dumps(messages).encode()) < 128 * 1024
    assert json.loads(original_trace[1]["tool_calls"][0]["function"]["arguments"])["source"] == sources[0]


def test_model_feedback_keeps_real_validation_and_errors_while_full_trace_stays_complete():
    original = {"check": {"status": "needs_runtime_validation", "diagnostics":
        [{"severity": "unknown", "message": "x" * 1000} for _ in range(80)] +
        [{"severity": "error", "code": "actual_missing_method", "message": "real failure"}],
        "unresolved": ["x" * 1000] * 80},
        "validation": {"status": "failed", "error": "CandidateBatch is not iterable", "code_sha256": "a" * 64}}
    bounded = ProjectAssistantRuntime._edit_tool_feedback(original)
    assert bounded["validation"] == original["validation"]
    assert bounded["check"]["diagnostics"][0]["code"] == "actual_missing_method"
    assert len(json.dumps(bounded).encode()) < 17 * 1024
    assert len(original["check"]["diagnostics"]) == 81


def test_minimum_strict_budget_keeps_api_read_between_failure_and_repair(tmp_path):
    calls = 0
    def complete(_owner, messages, tools):
        nonlocal calls
        calls += 1
        names = {tool["function"]["name"] for tool in tools}
        if calls == 1:
            return api_call("discover")
        if calls == 2:
            assert names == {"check_project_edit"}
            return source_call("wrong", "def transform(value):\n    return value - 1\n")
        if calls == 3:
            assert "framework_api" in names
            assert json.loads(messages[-1]["content"])["validation"]["status"] == "failed"
            return api_call("after-failure")
        if calls == 4:
            assert names == {"check_project_edit"}
            return source_call("fixed", "def transform(value):\n    return value + 1\n")
        assert tools == []
        return strict_answer(json.loads(messages[-1]["content"])["edit_digest"])
    runtime, packet = strict_prepared(tmp_path, complete, transform_validator, max_model_calls=5)
    result = runtime.generate(packet, object())
    assert calls == 5 and result["closed_loop"]["status"] == "passed"


def test_executed_source_identity_cannot_disagree_with_submitted_source(tmp_path):
    def validator(proposal):
        return {"status": "passed", "executed": True, "code_sha256": proposal["code_sha256"],
                "executed_source_sha256": "0" * 64}
    runtime, packet = strict_prepared(tmp_path, None, validator)
    with pytest.raises(ValueError, match="project_edit_validation_unbound"):
        runtime._dispatch("check_project_edit", {"path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"}, packet)


@pytest.mark.parametrize("missing", ["executed_source_sha256", "validation_identity"])
def test_strict_passed_receipt_must_supply_actual_child_hash_and_validation_profile(tmp_path, missing):
    def validator(proposal):
        receipt = {"status": "passed", "executed": True, "code_sha256": proposal["code_sha256"],
                   "executed_source_sha256": proposal["code_sha256"], "validation_identity": "fixed-transform/v1"}
        receipt.pop(missing)
        return receipt
    runtime, packet = strict_prepared(tmp_path, None, validator)
    with pytest.raises(ValueError, match="project_edit_validation_(unbound|profile_mismatch)"):
        runtime._dispatch("check_project_edit", {"path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"}, packet)


def test_non_strict_legacy_validator_does_not_require_child_hash_or_profile(tmp_path):
    runtime, packet = prepared(tmp_path)
    runtime.edit_validator = lambda proposal: {"status": "passed", "executed": True,
                                               "code_sha256": proposal["code_sha256"]}
    result = runtime._dispatch("check_project_edit", {"path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"}, packet)
    assert result["validation"]["status"] == "passed"


def test_preexecution_failure_can_return_unknown_child_hash_without_losing_error_feedback(tmp_path):
    def validator(proposal):
        return {"status": "failed", "executed": False, "code_sha256": proposal["code_sha256"],
                "executed_source_sha256": None, "error": "source import was rejected before execution"}
    runtime, packet = strict_prepared(tmp_path, None, validator)
    result = runtime._dispatch("check_project_edit", {"path": "cases/hybrid_search/adapter/novel.py", "source": "pass\n"}, packet)
    assert result["validation"]["error"] == "source import was rejected before execution"
    assert runtime._validated_edit(result) is False


def test_phase_and_argument_diagnostics_lead_same_loop_to_source_submission(tmp_path):
    calls, seen = 0, []
    def complete(_owner, messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            description = next(tool["function"]["description"] for tool in tools
                               if tool["function"]["name"] == "framework_api")
            assert "自动返回该方法正文" in description and "无include_body/include_source参数" in description
            result = api_call("bad-extra")
            result["message"]["tool_calls"][0]["function"]["arguments"] = json.dumps({
                "symbol": "SolutionPool", "member": "read", "include_body": "private-argument-sentinel"})
            return result
        if calls in (2, 3):
            if calls == 2:
                error = json.loads(messages[-1]["content"])["error"]
                seen.append(error)
                assert error["code"] == "project_tool_arguments_invalid"
                assert error["allowed_fields"] == ["member", "project_path", "symbol"]
                assert error["required_fields"] == ["symbol"]
                assert "private-argument-sentinel" not in json.dumps(error)
            return {"model": "same-model", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": str(calls), "type": "function", "function": {"name": "project_files",
                    "arguments": '{"limit":1}'}}]}}
        if calls == 4:
            assert {tool["function"]["name"] for tool in tools} == {"check_project_edit"}
            return api_call("phase-is-closed")
        if calls == 5:
            error = json.loads(messages[-1]["content"])["error"]
            seen.append(error)
            assert error["code"] == "project_tool_phase_closed"
            assert error["phase"] == "propose_and_test"
            assert error["allowed_tools"] == ["check_project_edit"]
            assert "查询阶段已结束" in error["message"] and "完整 Python source" in error["message"]
            return source_call("submit", "def transform(value):\n    return value + 1\n")
        return strict_answer(json.loads(messages[-1]["content"])["edit_digest"])
    runtime, packet = strict_prepared(tmp_path, complete, transform_validator)
    result = runtime.generate(packet, object())
    assert calls == 6 and result["closed_loop"]["status"] == "passed"
    assert len(seen) == 2


@pytest.mark.parametrize("arguments,reason", [
    ({"member": "read"}, "unexpected_or_missing_fields"),
    ({"symbol": {"private": "argument-sentinel"}}, "invalid_type_or_size"),
])
def test_argument_contract_feedback_contains_schema_names_not_argument_values(tmp_path, arguments, reason):
    runtime, packet = prepared(tmp_path)
    with pytest.raises(ValueError) as captured:
        runtime._dispatch("framework_api", arguments, packet)
    feedback = captured.value.feedback
    assert feedback["code"] == "project_tool_arguments_invalid"
    assert feedback["allowed_fields"] == ["member", "project_path", "symbol"]
    assert feedback["required_fields"] == ["symbol"]
    assert feedback["reason"] == reason
    assert "argument-sentinel" not in json.dumps(feedback)


def test_noncontract_tool_exception_keeps_generic_safe_feedback(tmp_path):
    calls = 0
    def complete(_owner, messages, _tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            return api_call("internal-failure")
        error = json.loads(messages[-1]["content"])["error"]
        assert error["code"] == "project_tool_invalid"
        assert set(error) == {"code", "message"}
        assert "private-internal-sentinel" not in json.dumps(error)
        return strict_answer()
    runtime, packet = prepared(tmp_path, complete)
    def broken(*_):
        raise RuntimeError("private-internal-sentinel")
    runtime._dispatch = broken
    runtime.generate(packet, object())
