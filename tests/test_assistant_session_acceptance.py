"""Acceptance plumbing must never grade its own model's prose as understanding."""
import copy
import json

import pytest

from nsgablack.catalog.assistant_session_acceptance import (
    CASES, RequestBudget, attach_reviews, create_teaching_project, main, run_acceptance,
)
from nsgablack.catalog.curation_provider import DeepSeekConfig
from nsgablack.catalog.lab_assistant import AssistantProviderError
from nsgablack.catalog.lab_knowledge import read_framework_basics


class FixtureGenerator:
    config = DeepSeekConfig(api_key="test-placeholder-not-a-real-key", model="deepseek-flash")

    def __init__(self):
        self.packets = []

    def generate(self, packet):
        self.packets.append(copy.deepcopy(packet))
        return {"base_digest": packet["base_digest"], "draft": None,
                "explanation": "这是离线夹具回答，尚未运行求解。", "changes": [],
                "questions": [], "evidence_keys": ["adapter.nsga2"]}


def fixture_complete(seen):
    def complete(_generator, messages, tools):
        seen.append(copy.deepcopy(messages))
        assert tools
        return {"message": {"role": "assistant", "content": json.dumps({
            "explanation": "这是离线夹具的方案讨论，没有应用或执行。",
            "questions": [], "proposal_digest": None})}, "model": "fixture-not-model-inference"}
    return complete


def run_fixture(tmp_path, maximum=20):
    sources, project_id = create_teaching_project(tmp_path)
    generator, seen = FixtureGenerator(), []
    result = run_acceptance(generator, sources=sources, project_id=project_id,
        maximum_requests=maximum, project_complete=fixture_complete(seen))
    return result, generator, seen


def test_fresh_sessions_have_no_chat_but_followup_retains_local_conversation(tmp_path):
    report, generator, seen = run_fixture(tmp_path)
    assert report["summary"] == {"total": 8, "http_requests": 8, "new_http_requests": 8, "protocol_passed": 8,
        "semantic_passed": 0, "semantic_failed": 0, "semantic_pending": 8}
    assert [len(packet["guide_context"]["history"]) for packet in generator.packets] == [0, 2, 0, 0]
    assert [row["history_messages"] for row in report["cases"]] == [0, 2, 0, 0] * 2
    assert len(seen) == 4
    basics = read_framework_basics()
    for packet in generator.packets:
        assert "review_points" not in json.dumps(packet, ensure_ascii=False)
        assert packet["framework_basics"] == basics["metadata"]
    for messages in seen:
        assert "review_points" not in json.dumps(messages, ensure_ascii=False)
        assert messages[0]["content"].startswith(basics["content"])
        payload = json.loads(next(message["content"] for message in reversed(messages) if message["role"] == "user"))
        assert payload["framework_basics"] == basics["metadata"]
        assert "DESIGN.md" in json.dumps(payload["project_state"], ensure_ascii=False)
    assert "test-placeholder-not-a-real-key" not in json.dumps(report, ensure_ascii=False)
    assert all(row["response_sha256"] for row in report["cases"])
    assert report["kind"] == "development_acceptance"


def test_request_budget_is_shared_between_both_official_entry_points(tmp_path):
    report, generator, seen = run_fixture(tmp_path, maximum=5)
    assert len(generator.packets) == 4 and len(seen) == 1
    assert report["summary"]["http_requests"] == 5
    assert report["summary"]["protocol_passed"] == 5
    assert all(row.get("error") == "acceptance_request_limit" for row in report["cases"][5:])


def test_review_requires_exact_response_digest_and_is_not_an_automatic_score(tmp_path):
    report, _, _ = run_fixture(tmp_path)
    row = report["cases"][0]
    review = {row["id"]: {"response_sha256": row["response_sha256"],
                         "decision": "pass", "reason": "按源码及完整回答核对的外部审阅记录。"}}
    revised = attach_reviews(report, review, reviewer="test-reviewer")
    assert revised["summary"]["semantic_passed"] == 1
    assert report["summary"]["semantic_passed"] == 0
    review[row["id"]]["response_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="review_mismatch"):
        attach_reviews(report, review, reviewer="test-reviewer")


def test_cli_does_not_start_inference_without_explicit_model_and_paid_switch(tmp_path):
    with pytest.raises(SystemExit):
        main(["--out", str(tmp_path / "report.json")])
    assert not (tmp_path / "report.json").exists()


def test_budget_is_positive_bounded_and_does_not_silently_retry():
    for value in (0, 21, True):
        with pytest.raises(ValueError):
            RequestBudget(value)
    budget = RequestBudget(1)
    budget.reserve()
    with pytest.raises(AssistantProviderError, match="acceptance_request_limit"):
        budget.reserve()
    assert budget.used == 1


def test_invalid_project_final_output_is_visible_for_diagnosis_without_private_reasoning(tmp_path):
    sources, project_id = create_teaching_project(tmp_path)

    def invalid(*_):
        return {"message": {"role": "assistant", "content": '{"unexpected": "field"}',
                            "reasoning_content": "private-reasoning-not-for-report"}, "model": "fixture"}

    report = run_acceptance(FixtureGenerator(), sources=sources, project_id=project_id,
                            project_complete=invalid)
    assert report["summary"]["protocol_passed"] == 4
    records = [row for row in report["request_records"] if row["entry"] == "project"]
    assert all(row["assistant_content"] == '{"unexpected": "field"}' for row in records)
    assert all(row["case_id"].startswith("project.") for row in records)
    assert "private-reasoning-not-for-report" not in json.dumps(report)


def test_development_followup_keeps_prior_budget_and_selects_only_requested_cases(tmp_path):
    sources, project_id = create_teaching_project(tmp_path)
    seen = []
    report = run_acceptance(FixtureGenerator(), sources=sources, project_id=project_id,
        entries=("project",), case_ids=("ga_final_members", "ga_second_parent", "direction_coarse_fine"),
        already_used=13, source_report_sha256="a" * 64, project_model_calls=2, project_complete=fixture_complete(seen))
    assert report["kind"] == "development_followup"
    assert report["summary"]["http_requests"] == 16
    assert report["summary"]["new_http_requests"] == 3
    assert report["source_report_sha256"] == "a" * 64
    assert [row["history_messages"] for row in report["cases"]] == [0, 2, 0]
    assert len(seen) == 3
    assert report["project_limits"]["model_calls_per_delivery"] == 2


def test_failed_parent_does_not_spend_another_request_on_a_fake_continuation(tmp_path):
    sources, project_id = create_teaching_project(tmp_path)
    seen = []

    def invalid(*_):
        seen.append(1)
        return {"message": {"role": "assistant", "content": '{}'}, "model": "fixture",
                "finish_reason": "stop"}

    report = run_acceptance(FixtureGenerator(), sources=sources, project_id=project_id,
        entries=("project",), case_ids=("ga_final_members", "ga_second_parent"),
        already_used=19, project_complete=invalid)
    assert len(seen) == 1 and report["summary"]["http_requests"] == 20
    assert report["cases"][1]["error"] == "acceptance_parent_delivery_unavailable"
    assert report["request_records"][0]["finish_reason"] == "stop"


def test_new_cases_are_different_tasks_with_explicit_review_criteria():
    assert len(CASES) == 4 and len({row["id"] for row in CASES}) == 4
    assert len([row for row in CASES if row["history"] == "fresh"]) == 3
    assert all(len(row["review_points"]) == 3 for row in CASES)
