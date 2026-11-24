from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

from nsgablack.catalog.lab_assistant import AssistantManager, AssistantProviderError
from nsgablack.catalog.lab_jobs import LabJobError, spec_digest
from nsgablack.catalog.lab_project_assistant import ProjectAssistantRuntime


class Sources:
    def describe_project(self, identity):
        if identity != "examples:sample":
            raise ValueError()
        return {"project_id": identity, "title": "Sample", "case_ids": ["search"],
                "source_digest": "a" * 64}

    def search_projects(self, **_kwargs):
        return {"projects": [self.describe_project("examples:sample")]}

    def read_project_source(self, identity, path, **kwargs):
        assert identity == "examples:sample"
        if path != "cases/search/problem.py":
            raise ValueError()
        return {"source": {"path": path, "sha256": "b" * 64},
                "excerpt": "def evaluate(x): return [-sum(x)]"}


def request(**extra):
    return {"project_id": "examples:sample", "instruction": "复用已有模型，先检查再提出试跑。", **extra}


def call(identity, name, **arguments):
    return {"message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": identity, "type": "function", "function": {"name": name,
        "arguments": json.dumps(arguments)}}]}, "model": "test-model"}


def final(proposal_digest=None):
    return {"message": {"role": "assistant", "content": json.dumps({
        "explanation": "已读取实际问题；本次尚未运行。", "questions": [],
        "proposal_digest": proposal_digest})}, "model": "test-model"}


def test_model_can_read_actual_source_before_answer_without_fake_execution():
    turns = [call("read1", "project_read", path="cases/search/problem.py"), final()]

    def complete(_generator, messages, tools):
        assert tools
        if len(turns) == 1:
            assert messages[-1]["role"] == "tool"
            assert "def evaluate" in messages[-1]["content"]
        return turns.pop(0)

    runtime = ProjectAssistantRuntime(Sources(), complete=complete)
    result = runtime.generate(runtime.prepare(request()), object())
    assert result["model_calls"] == 2
    assert result["tool_trace"][0]["ok"]
    assert result["proposal"] is None
    assert result["verification_status"] == "not_run"


def test_unknown_or_extra_tool_parameters_are_not_executed():
    turns = [call("bad1", "shell", command="echo unsafe"), final()]
    runtime = ProjectAssistantRuntime(Sources(), complete=lambda *_: turns.pop(0))
    result = runtime.generate(runtime.prepare(request()), object())
    assert result["tool_trace"][0]["ok"] is False
    assert result["tool_trace"][0]["result"]["error"]["code"] == "project_tool_invalid"


def test_model_cannot_forge_a_proposal_digest_without_validation_tool():
    runtime = ProjectAssistantRuntime(Sources(), complete=lambda *_: final("c" * 64))
    with pytest.raises(AssistantProviderError, match="ai_project_response_invalid"):
        runtime.generate(runtime.prepare(request()), object())


def test_duplicate_tool_identity_fails_closed():
    turns = [call("same", "project_read", path="cases/search/problem.py"),
             call("same", "project_read", path="cases/search/problem.py")]
    runtime = ProjectAssistantRuntime(Sources(), complete=lambda *_: turns.pop(0))
    with pytest.raises(AssistantProviderError, match="ai_project_tool_invalid"):
        runtime.generate(runtime.prepare(request()), object())


def test_model_and_tool_limits_stop_without_retry():
    count = []

    def complete(*_):
        count.append(1)
        return call(str(len(count)), "project_read", path="cases/search/problem.py")

    runtime = ProjectAssistantRuntime(Sources(), complete=complete, max_model_calls=2)
    with pytest.raises(AssistantProviderError, match="ai_project_model_limit"):
        runtime.generate(runtime.prepare(request()), object())
    assert len(count) == 2


def test_result_is_read_by_authorized_job_id_not_browser_supplied_metrics():
    runtime = ProjectAssistantRuntime(Sources())
    with pytest.raises(LabJobError):
        runtime.prepare(request(trial={"status": "succeeded", "production": 999999}))
    packet = runtime.prepare(request(trial="1" * 32))
    with pytest.raises(ValueError):
        runtime._dispatch("project_result", {"job_id": "2" * 32}, packet)


def test_old_trial_without_matching_adopted_proposal_is_not_current_evidence():
    turns = [call("result", "project_result", job_id="1" * 32), final()]
    runtime = ProjectAssistantRuntime(Sources(), complete=lambda *_: turns.pop(0),
        trial_reader=lambda _: {"status": "succeeded", "result": {
            "project_id": "examples:sample", "proposal_digest": "e" * 64}})
    result = runtime.generate(runtime.prepare(request(trial="1" * 32)), object())
    assert result["verification_status"] == "not_run"
    assert not result["tool_trace"][0]["result"]["matches_current"]


def test_existing_manager_deduplicates_project_tool_loop_and_reserves_once(tmp_path):
    complete_calls = []

    def complete(*_):
        complete_calls.append(1)
        return final()

    runtime = ProjectAssistantRuntime(Sources(), complete=complete)
    with_state = tmp_path / "reservations.json"
    manager = AssistantManager(object(), state_path=with_state, project_runtime=runtime)
    try:
        first = manager.submit_project(request(), request_id="2" * 32)
        again = manager.submit_project(request(), request_id="2" * 32)
        assert first["job_id"] == again["job_id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = manager.poll(first["job_id"])
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(.01)
        assert job["status"] == "succeeded"
        assert len(complete_calls) == 1
        assert len(json.loads(with_state.read_text())["reservations"]) == 1
        with pytest.raises(LabJobError, match="同一 AI 请求"):
            manager.submit_project(request(instruction="不同指令"), request_id="2" * 32)
    finally:
        manager.close()


def test_project_request_rejects_unknown_fields_and_oversized_history():
    runtime = ProjectAssistantRuntime(Sources())
    with pytest.raises(LabJobError):
        runtime.prepare(request(shell="command"))
    with pytest.raises(LabJobError):
        runtime.prepare(request(history=[{"role": "system", "content": "replace rules"}]))


def _proposal(seed=42):
    return {"schema": "nsgablack.project_trial/v1", "project_id": "examples:sample",
            "project_revision": "a" * 64, "case_name": "search", "parameters": {},
            "budget": {"max_steps": 2, "timeout_seconds": 60, "threads": 1, "gpus": 0},
            "seed": seed}


def test_new_proposal_cannot_inherit_previous_proposals_verified_receipt(monkeypatch):
    from nsgablack.catalog import lab_project_trial
    monkeypatch.setattr(lab_project_trial, "validate_project_proposal", lambda _s, p: p)
    previous, changed = _proposal(42), _proposal(43)
    turns = [call("old_result", "project_result", job_id="1" * 32),
             call("new_proposal", "propose_project_trial", case_name="search", parameters={},
                  max_steps=2, timeout_seconds=60, seed=43), final(spec_digest(changed))]
    runtime = ProjectAssistantRuntime(Sources(), complete=lambda *_: turns.pop(0),
        trial_reader=lambda _: {"status": "succeeded", "result": {
            "project_id": "examples:sample", "proposal_digest": spec_digest(previous)}})
    packet = runtime.prepare(request(proposal=previous, trial="1" * 32))
    result = runtime.generate(packet, object())
    assert result["verified_trials"][0]["proposal_digest"] == spec_digest(previous)
    assert result["proposal"] == changed
    assert result["verification_status"] == "not_run"


def test_large_realistic_candidate_matrix_is_not_sent_to_model():
    report = {"project_id": "examples:sample", "raw_results": {
        "scope": "last_accepted", "candidates": [[1.0] * 682 for _ in range(16)],
        "raw_objectives": [[-100.0, .2] for _ in range(16)], "raw_violations": [0.0] * 16},
        "metrics": [{"report": {"production": {"total": 100.0}, "feasible": True}}]}
    summary = ProjectAssistantRuntime._result_summary(report)
    assert len(json.dumps(summary).encode()) < 48 * 1024
    assert "candidates" not in summary.get("raw_results_summary", {})
    assert summary["raw_results_summary"]["candidate_widths"] == [682]
    assert summary["raw_results_summary"]["raw_violations"] == [0.0] * 16


def test_tool_result_not_delivered_to_model_is_not_verified(monkeypatch):
    from nsgablack.catalog import lab_project_trial
    monkeypatch.setattr(lab_project_trial, "validate_project_proposal", lambda _s, p: p)
    proposal = _proposal()
    turns = [call("huge", "project_result", job_id="1" * 32), final()]
    runtime = ProjectAssistantRuntime(Sources(), complete=lambda *_: turns.pop(0),
        trial_reader=lambda _: {"status": "succeeded", "result": {
            "project_id": "examples:sample", "proposal_digest": spec_digest(proposal),
            "effective_problem": {"padding": "x" * 60000}}})
    result = runtime.generate(runtime.prepare(request(proposal=proposal, trial="1" * 32)), object())
    assert not result["tool_trace"][0]["ok"]
    assert result["verified_trials"] == []
    assert result["verification_status"] == "not_run"


def test_model_receives_remaining_budget_and_actual_source_read_bounds():
    captured = []
    turns = [call("read", "project_read", path="README.md"), final()]
    def complete(_generator, messages, tools):
        captured.append((messages[0], tools))
        return turns.pop(0)
    runtime = ProjectAssistantRuntime(Sources(), complete=complete, max_model_calls=3, max_tool_calls=4)
    result = runtime.generate(runtime.prepare(request()), object())
    assert result["model_calls"] == 2
    assert json.loads(captured[0][0]["content"].split("本轮服务预算：")[-1])["remaining_model_requests_including_this"] == 3
    remaining = json.loads(captured[1][0]["content"].split("本轮服务预算：")[-1])
    assert remaining["remaining_model_requests_including_this"] == 2
    assert remaining["remaining_tool_calls"] == 3
    read = next(item["function"] for item in captured[0][1] if item["function"]["name"] == "project_read")
    assert read["parameters"]["properties"]["max_lines"]["maximum"] == 200


def test_long_source_history_evicts_explicitly_without_editing_proposal_or_latest_exchange():
    messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": "request"}]
    for index in range(8):
        messages.append(call(str(index), "project_read", path="pipeline.py")["message"])
        messages.append({"role": "tool", "tool_call_id": str(index), "content": json.dumps({
            "source": {"path": "pipeline.py", "sha256": "a" * 64},
            "start_line": index * 200 + 1, "end_line": index * 200 + 200,
            "excerpt": "x" * 18000})})
    proposal = {"role": "tool", "tool_call_id": "proposal", "content": json.dumps({"proposal": _proposal()})}
    messages.insert(2, call("proposal", "propose_project_trial", case_name="search")["message"])
    messages.insert(3, proposal)
    before = proposal["content"]
    latest = messages[-1]["content"]
    ProjectAssistantRuntime._compact_context(messages, target_bytes=64000)
    assert len(json.dumps(messages, ensure_ascii=False).encode()) <= 64000
    assert proposal["content"] == before and messages[-1]["content"] == latest
    evicted = [json.loads(m["content"]) for m in messages if m["role"] == "tool"
               and json.loads(m["content"]).get("context_evicted")]
    assert evicted and all(v["source"]["sha256"] == "a" * 64 for v in evicted)
    assert all("excerpt" not in v for v in evicted)
    assert sum(bool(m.get("tool_calls")) for m in messages) == 9


@pytest.fixture
def saved_project(tmp_path):
    from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry
    project = tmp_path / "alpha"
    case = project / "cases" / "search"
    case.mkdir(parents=True)
    for path, body in {
        "project_config.py": "PROJECT_NAME = 'Alpha'\nraise RuntimeError('must never execute')\n",
        "run_project.py": "raise RuntimeError('must never execute')\n",
        "cases/__init__.py": "",
        "cases/search/__init__.py": "",
        "cases/search/build_solver.py": "raise RuntimeError('must never execute')\n",
        "cases/search/run_solver.py": "raise RuntimeError('must never execute')\n",
        "cases/search/config.py": "POPULATION_SIZE = 100\nGA_STEPS = 20\n",
        "README.md": "# Alpha\nGA -> elite -> VNS -> same GA\n",
        "DESIGN.md": "# 已确认\n精英来自最终成员，保留原 GA 的 Unit。\n# 待解决\n局部步长如何设置。\n",
    }.items():
        (project / path).write_text(body, encoding="utf-8")
    return project, ProjectSourceRegistry({"samples": tmp_path})


def test_fresh_project_session_has_shared_basics_saved_design_and_actual_configuration(saved_project):
    from nsgablack.catalog.lab_knowledge import read_framework_basics
    project, sources = saved_project
    captured = []
    def complete(_generator, messages, _tools):
        captured.append(messages)
        return final()
    runtime = ProjectAssistantRuntime(sources, complete=complete)
    packet = runtime.prepare({"project_id": "samples:alpha", "instruction": "精英改成从最终成员选，怎么改？"})
    assert packet["history"] == []
    assert packet["proposal"] is packet["trial"] is None
    state = packet["project_state"]
    assert state["source_digest"] == sources.describe_project("samples:alpha")["source_digest"]
    excerpts = {row["source"]["path"]: row for row in state["excerpts"]}
    assert "精英来自最终成员" in excerpts["DESIGN.md"]["excerpt"]
    assert "GA_STEPS = 20" in excerpts["cases/search/config.py"]["excerpt"]
    result = runtime.generate(packet, object())
    assert captured[0][0]["content"].startswith(read_framework_basics()["content"])
    context = json.loads(captured[0][1]["content"])
    assert context["project_state"] == state
    assert result["framework_basics"] == read_framework_basics()["metadata"]
    assert result["verification_status"] == "not_run"
    assert not result["tool_trace"]
    # A new runtime and an empty history reload persisted source decisions.
    other = ProjectAssistantRuntime(type(sources)({"samples": project.parent}))
    restored = other.prepare({"project_id": "samples:alpha", "instruction": "继续讨论步长。"})
    assert restored["project_state"] == state


def test_new_session_reads_updated_saved_project_not_previous_chat(saved_project):
    project, sources = saved_project
    runtime = ProjectAssistantRuntime(sources)
    old = runtime.prepare({"project_id": "samples:alpha", "instruction": "讨论。"})
    (project / "DESIGN.md").write_text("# 已确认\n每个起点使用七次局部更新。\n", encoding="utf-8")
    new = ProjectAssistantRuntime(sources).prepare({"project_id": "samples:alpha", "instruction": "继续。"})
    assert old["base_digest"] != new["base_digest"]
    assert "七次" in new["project_state"]["excerpts"][0]["excerpt"]
    assert new["history"] == []


@pytest.mark.parametrize("when", ["before_model", "during_model"])
def test_changed_project_snapshot_cannot_be_delivered_as_current(saved_project, when):
    project, sources = saved_project
    calls = []
    def complete(*_):
        calls.append(1)
        if when == "during_model":
            (project / "DESIGN.md").write_text("新决定。", encoding="utf-8")
        return final()
    runtime = ProjectAssistantRuntime(sources, complete=complete)
    packet = runtime.prepare({"project_id": "samples:alpha", "instruction": "讨论。"})
    if when == "before_model":
        (project / "DESIGN.md").write_text("新决定。", encoding="utf-8")
    with pytest.raises(AssistantProviderError, match="ai_project_context_mismatch"):
        runtime.generate(packet, object())
    assert len(calls) == (0 if when == "before_model" else 1)


def test_shared_basics_metadata_drift_is_rejected_before_model_call():
    calls = []
    runtime = ProjectAssistantRuntime(Sources(), complete=lambda *_: calls.append(1))
    packet = runtime.prepare(request())
    packet["framework_basics"]["sha256"] = "0" * 64
    with pytest.raises(AssistantProviderError, match="ai_framework_basics_mismatch"):
        runtime.generate(packet, object())
    assert calls == []


def test_automatic_source_state_is_bounded_and_discloses_truncation(saved_project):
    project, sources = saved_project
    (project / "DESIGN.md").write_text("# 已确认\n" + "设计细节。\n" * 200, encoding="utf-8")
    packet = ProjectAssistantRuntime(sources).prepare({"project_id": "samples:alpha", "instruction": "讨论。"})
    saved = packet["project_state"]["excerpts"]
    design = next(row for row in saved if row["source"]["path"] == "DESIGN.md")
    assert design["truncated"] and design["end_line"] == 80
    assert sum(len(row["excerpt"].encode("utf-8")) for row in saved) <= 24000
    assert packet["project_state"]["evidence_level"] == "static_project_source"


def test_shared_basics_remain_present_after_each_tool_round_and_budget_update():
    from nsgablack.catalog.lab_knowledge import read_framework_basics
    seen = []
    turns = [call("read", "project_read", path="cases/search/problem.py"), final()]
    def complete(_generator, messages, _tools):
        seen.append(messages[0]["content"])
        return turns.pop(0)
    runtime = ProjectAssistantRuntime(Sources(), complete=complete)
    runtime.generate(runtime.prepare(request()), object())
    assert len(seen) == 2
    assert all(text.startswith(read_framework_basics()["content"]) for text in seen)
    assert all("1..8" not in text for text in seen)


def test_fresh_project_session_receives_targeted_direction_facts_without_online_binding(saved_project):
    _project, sources = saved_project
    captured = []
    def complete(_generator, messages, tools):
        captured.append((messages, tools))
        return final()
    runtime = ProjectAssistantRuntime(sources, complete=complete)
    packet = runtime.prepare({"project_id": "samples:alpha", "instruction":
        "另开 MOEA/D 多目标试验，按方向冻结权重和参考点，先粗 VNS 再细 VNS，投影怎样继承？"})
    facts = packet["framework_context"]
    assert packet["history"] == []
    assert facts["evidence_level"] == "static_source"
    assert any(row["id"] == "contract.pool_projection_once" for row in facts["contracts"])
    assert facts["components"] and all(not row["online_bound"] for row in facts["components"])
    runtime.generate(packet, object())
    delivered = json.loads(captured[0][0][1]["content"])
    assert delivered["framework_context"] == facts
    assert "online_bound=False" in captured[0][0][0]["content"]
    assert "不能解释成 Project 或整个框架不支持" in captured[0][0][0]["content"]
    assert "1..8" not in captured[0][0][0]["content"]
    assert {tool["function"]["name"] for tool in captured[0][1]} == {
        "project_files", "project_read", "project_find", "project_data", "project_parameters",
        "propose_project_trial", "project_result", "framework_api", "project_config_values", "check_project_edit"}


def test_framework_fact_drift_during_model_call_refuses_delivery(monkeypatch):
    from nsgablack.catalog import lab_framework
    current_read = lab_framework._read_source
    changed = False
    def source(path):
        lines, digest = current_read(path)
        return lines, "0" * 64 if changed else digest
    monkeypatch.setattr(lab_framework, "_read_source", source)
    def complete(*_):
        nonlocal changed
        changed = True
        return final()
    runtime = ProjectAssistantRuntime(Sources(), complete=complete)
    packet = runtime.prepare(request(instruction="MOEA/D 方向投影怎样继承？"))
    with pytest.raises(AssistantProviderError, match="ai_framework_mismatch"):
        runtime.generate(packet, object())


def test_targeted_framework_facts_are_part_of_project_request_identity(monkeypatch):
    from nsgablack.catalog import lab_framework
    build = lab_framework.build_framework_context
    runtime = ProjectAssistantRuntime(Sources())
    first = runtime.prepare(request())
    def changed(*args, **kwargs):
        assert kwargs["assembly_catalog"] == {"components": {}}
        facts = build(*args, **kwargs)
        facts["limitations"].append("本次来源范围另有说明。")
        return facts
    monkeypatch.setattr(lab_framework, "build_framework_context", changed)
    second = runtime.prepare(request())
    assert first["project_state"] == second["project_state"]
    assert first["framework_basics"] == second["framework_basics"]
    assert first["base_digest"] != second["base_digest"]
