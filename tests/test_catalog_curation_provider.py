import io
import json
from copy import deepcopy
from urllib.error import HTTPError, URLError

import pytest

from nsgablack.catalog.curation_provider import (
    CurationProviderError, DeepSeekConfig, DeepSeekGenerator, ENDPOINT, PROMPT_VERSION, REVIEW_MODEL,
    SYSTEM_PROMPT, load_deepseek_config,
)


@pytest.mark.parametrize("authorization", [False, None, "true", 1])
@pytest.mark.parametrize("operation", ["generate", "review"])
def test_paid_requests_require_explicit_boolean_opt_in(authorization, operation):
    class NoNetwork:
        def open(self, *args, **kwargs):
            raise AssertionError("No HTTP request is authorized")

    generator = DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=NoNetwork(),
                                 allow_paid_requests=authorization)
    with pytest.raises(CurationProviderError, match="^ai_paid_execution_required$"):
        if operation == "generate":
            generator.generate({"entry_key": "adapter.example"})
        else:
            generator.review({"evidence": []}, {})


def test_default_generator_never_sends_a_paid_request():
    class NoNetwork:
        def open(self, *args, **kwargs):
            raise AssertionError("No HTTP request is authorized")

    with pytest.raises(CurationProviderError, match="^ai_paid_execution_required$"):
        DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=NoNetwork()).generate({})


def test_generator_uses_server_only_json_request_and_returns_usage():
    class Opener:
        def open(self, request, *, timeout):
            assert request.full_url == ENDPOINT
            assert request.headers["Authorization"] == "Bearer test-only-key"
            body = json.loads(request.data)
            assert body["response_format"] == {"type": "json_object"}
            assert body["model"] == "deepseek-flash"
            assert body["thinking"] == {"type": "enabled"}
            assert body["reasoning_effort"] == "low"
            assert body["max_tokens"] == 16384
            assert "temperature" not in body
            assert "test-only-key" not in body["messages"][1]["content"]
            return io.BytesIO(json.dumps({"model": "deepseek-flash", "choices": [{"finish_reason": "stop",
                "message": {"content": '{"summary":"说明"}', "reasoning_content": "PRIVATE REASONING"}}],
                "usage": {"total_tokens": 10, "private": "hidden"}}).encode())

    config = DeepSeekConfig("test-only-key")
    assert "test-only-key" not in repr(config)
    assert DeepSeekGenerator(config, opener=Opener(), allow_paid_requests=True).generate({"entry_key": "a"}) == {
        "note": {"summary": "说明"}, "usage": {"total_tokens": 10, "generation_thinking_calls": 1},
        "actual_model": "deepseek-flash"}


@pytest.mark.parametrize("error", [HTTPError(ENDPOINT, 401, "secret-containing-body", {}, None), URLError("private-address")])
def test_errors_do_not_disclose_provider_or_configuration_details(error):
    class Opener:
        def open(self, *args, **kwargs):
            raise error
    with pytest.raises(CurationProviderError) as caught:
        DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate({})
    assert "secret" not in str(caught.value)
    assert "private-address" not in str(caught.value)
    assert caught.value.diagnostics == {}


@pytest.mark.parametrize("payload", [b'{}', b'not-json', json.dumps({"choices": [{"finish_reason": "length"}]}).encode()])
def test_incomplete_or_malformed_response_is_rejected(payload):
    class Opener:
        def open(self, *args, **kwargs):
            return io.BytesIO(payload)
    with pytest.raises(CurationProviderError):
        DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate({})


def test_config_file_refuses_extra_endpoints_and_never_echoes_values(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "test-only-key", "endpoint": "https://untrusted.invalid"}))
    with pytest.raises(CurationProviderError, match="^ai_config_invalid$"):
        load_deepseek_config(path)


def tutorial_payload():
    return {"tutorial": {
        "scenario": "对现有数值调用增加一项偏移。",
        "preparation": ["调用方传入一个数值。"],
        "placement": "组件的调用函数。",
        "code": "def adjusted(value):\n    return value + 1",
        "language": "python",
        "execution_flow": ["调用方传入数值，函数返回加一结果。"],
        "result_checks": ["adjusted(2)返回3。"],
        "extensions": [{"title": "由调用方声明偏移", "purpose": "不同调用使用不同偏移。",
                        "placement": "替换原调用函数。",
                        "code": "def adjusted(value, offset):\n    return value + offset",
                        "language": "python", "effect": "偏移来自显式参数。",
                        "limits": ["调用方必须提供offset。"], "evidence_ids": ["e1"]}],
        "evidence_ids": ["e1"],
    }}


def generate_payload(payload, packet):
    class Opener:
        def open(self, request, *, timeout):
            body = json.loads(request.data)
            assert body["thinking"] == {"type": "enabled"}
            assert body["reasoning_effort"] == "low"
            assert body["max_tokens"] == 16384
            submitted = json.loads(body["messages"][1]["content"])
            assert {k: v for k, v in submitted.items() if k != "task_focus"} == packet
            focus = "\n".join(submitted["task_focus"])
            assert "同版完整guide" in focus and "文件路径、启用值和结果读法" in focus
            assert "不复述算法内核" in focus and "不能用它引入新API" in focus
            assert "必须修正对应错误" in focus
            response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}]}
            return io.BytesIO(json.dumps(response).encode())
    return DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate(packet)["note"]


@pytest.fixture
def evidence_packet(tmp_path):
    from nsgablack.catalog.curation import prepare_packet
    from nsgablack.catalog.registry import CatalogEntry

    (tmp_path / "component.py").write_text("class Example:\n    def act(self, value):\n        return value + 1\n", encoding="utf-8")
    entry = CatalogEntry(key="tool.example", title="Example", kind="tool", import_path="sample.component:Example")
    return prepare_packet(entry, [entry], {"sample": tmp_path})


def test_v7_tutorial_only_derives_indexes_without_inventing_relations_or_review(evidence_packet):
    from nsgablack.catalog.curation import validate_note

    payload = tutorial_payload()
    note = generate_payload(payload, evidence_packet)
    checked = validate_note(note, evidence_packet)
    assert PROMPT_VERSION.startswith("catalog-tutorial-reviewed-zh-v")
    assert note["tutorial"] == payload["tutorial"] == checked["tutorial"]
    assert note["summary"] == payload["tutorial"]["scenario"]
    assert note["use_when"] == [payload["tutorial"]["scenario"]]
    assert note["assembly_steps"] == payload["tutorial"]["execution_flow"]
    assert note["pitfalls"] == payload["tutorial"]["extensions"][0]["limits"]
    assert note["missing_information"] == evidence_packet["gaps"]
    assert note["related_keys"] == []
    assert payload["tutorial"]["result_checks"][0] in note["inputs_outputs"]
    assert "tutorial_review" not in note


def test_v7_keeps_all_tutorial_evidence_and_does_not_shorten_the_detailed_text():
    payload = tutorial_payload()
    payload["tutorial"]["evidence_ids"] = [f"e{i}" for i in range(1, 19)]
    payload["tutorial"]["execution_flow"] = ["处理输入。" * 250]
    packet = {"known_entry_keys": ["tool.example", "tool.unrelated"], "gaps": ["来源未给出调用者。"]}
    note = generate_payload(payload, packet)
    assert note["evidence_ids"] == payload["tutorial"]["evidence_ids"]
    assert note["tutorial"] == payload["tutorial"]
    assert len(note["assembly_steps"][0]) <= 1200
    assert len(note["tutorial"]["execution_flow"][0]) > 1200
    assert note["missing_information"] == packet["gaps"]
    assert note["related_keys"] == []


@pytest.mark.parametrize("change", ["extra_top", "author_review", "wrong_inner", "missing_inner", "wrong_type"])
def test_v7_unknown_shapes_are_not_silently_made_valid(evidence_packet, change):
    from nsgablack.catalog.curation import CurationValidationError, validate_note

    payload = tutorial_payload()
    if change == "extra_top":
        payload["summary"] = "额外字段不能被忽略。"
    elif change == "author_review":
        payload["tutorial_review"] = {"decision": "publish"}
    elif change == "wrong_inner":
        payload["tutorial"]["baseline"] = payload["tutorial"].pop("code")
    elif change == "missing_inner":
        payload["tutorial"].pop("placement")
    else:
        payload["tutorial"]["preparation"] = {"input": "不是列表"}
    original = deepcopy(payload)
    note = generate_payload(payload, evidence_packet)
    assert note == original
    with pytest.raises(CurationValidationError):
        validate_note(note, evidence_packet)


def test_v7_malformed_extension_is_left_for_publisher_validation(evidence_packet):
    from nsgablack.catalog.curation import CurationValidationError, validate_note

    payload = tutorial_payload()
    payload["tutorial"]["extensions"][0]["limits"] = None
    note = generate_payload(payload, evidence_packet)
    assert note["tutorial"] == payload["tutorial"]
    with pytest.raises(CurationValidationError, match="extensions.limits"):
        validate_note(note, evidence_packet)


def test_v7_tutorial_only_still_needs_separate_review_before_put(evidence_packet):
    from nsgablack.catalog.curate import curate_packets
    from nsgablack.catalog.tutorial_review import SYSTEM_PROMPT as REVIEW_PROMPT

    requests = []
    payload = tutorial_payload()

    class Opener:
        def open(self, request, *, timeout):
            body = json.loads(request.data)
            requests.append(body)
            if len(requests) == 1:
                assert body["thinking"] == {"type": "enabled"}
                assert body["reasoning_effort"] == "low"
                assert body["max_tokens"] == 16384
                answer = payload
            else:
                assert body["messages"][0]["content"] == REVIEW_PROMPT
                assert body["model"] == REVIEW_MODEL == "deepseek-v4-pro"
                assert body["thinking"] == {"type": "disabled"}
                assert "reasoning_effort" not in body
                assert body["max_tokens"] == 12288
                submitted = json.loads(body["messages"][1]["content"])
                assert submitted["tutorial"]["tutorial"] == payload["tutorial"]
                assert "tutorial_review" not in submitted["tutorial"]
                answer = {"decision": "publish", "issues": [], "checks": ["输入来自函数参数。", "结果由调用方读取。", "变体明确声明偏移参数。"],
                          "evidence_ids": ["e1"]}
            response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}]}
            return io.BytesIO(json.dumps(response).encode())

    class Store:
        saved = None

        def get(self, *args, **kwargs):
            return None

        def put(self, record):
            assert len(requests) == 2
            assert record["note"]["tutorial_review"]["decision"] == "publish"
            self.saved = record
            return record

    store = Store()
    generator = DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True)
    result = curate_packets({evidence_packet["entry_key"]: evidence_packet}, store, generator, model="deepseek-flash", workers=1)
    assert result["ok"] and result["generated"] == 1
    assert store.saved["note"]["tutorial"] == payload["tutorial"]


@pytest.mark.parametrize("decision", ["publish", "revise"])
def test_review_uses_calibrated_scope_and_model_without_overriding_either_verdict(decision):
    from nsgablack.catalog.tutorial_review import SYSTEM_PROMPT as REVIEW_PROMPT
    packet, note = {"evidence": [{"id": "e1"}]}, {"tutorial": {"code": "candidate kept unchanged"}}
    original = deepcopy((packet, note))
    issue = {"location": "code", "problem": "Tuple discards candidate source identity",
             "required_change": "Return the supported change result", "evidence_ids": ["e1"]}
    answer = {"decision": decision, "issues": [issue] if decision == "revise" else [],
              "checks": ["Actual binding checked", "Input contract checked", "Result identity checked"],
              "evidence_ids": ["e1"]}
    calls = []
    class Opener:
        def open(self, request, **kwargs):
            body = json.loads(request.data)
            calls.append(body)
            assert body["model"] == REVIEW_MODEL
            assert body["thinking"] == {"type": "disabled"} and "reasoning_effort" not in body
            assert body["messages"][0]["content"] == REVIEW_PROMPT
            submitted = json.loads(body["messages"][1]["content"])
            assert submitted["source"] == packet and submitted["tutorial"] == note
            scope = submitted["review_scope"]
            assert set(scope) == {"purpose", "source_policy", "local_code", "scenario", "blocking_basis"}
            assert "既有v5有限证据" in scope["purpose"]
            assert "同版完整人工指南与正式Case就是有效证据" in scope["source_policy"]
            assert "不要要求仓库已有同名helper" in scope["local_code"]
            assert "只审本例实际启用的参数和分支" in scope["scenario"]
            assert "身份丢失、结果语义混淆仍必须拒绝" in scope["blocking_basis"]
            return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps(answer), "reasoning_content": "PRIVATE REASONING"}}],
                "usage": {"total_tokens": 10}}).encode())
    result = DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).review(packet, note)
    assert result == {"note": answer, "usage": {"total_tokens": 10, "review_format_repairs": 0},
                      "actual_model": REVIEW_MODEL}
    assert len(calls) == 1 and (packet, note) == original


@pytest.mark.parametrize("override", ["deepseek-unknown", "https://private.invalid", "", 3, []])
def test_unknown_model_override_is_refused_before_network(override):
    class Opener:
        def open(self, *args, **kwargs):
            raise AssertionError("invalid model must not make a request")
    generator = DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True)
    with pytest.raises(CurationProviderError, match="^ai_model_override_invalid$"):
        generator._complete([], model=override)


@pytest.mark.parametrize("metadata,expected", [(None, REVIEW_MODEL), ({"model": "private model"}, REVIEW_MODEL),
                                               ({"model": "deepseek-v4-pro-actual"}, "deepseek-v4-pro-actual")])
def test_model_override_actual_metadata_uses_requested_model_as_fallback(metadata, expected):
    class Opener:
        def open(self, request, **kwargs):
            assert json.loads(request.data)["model"] == REVIEW_MODEL
            response = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
            response.update(metadata or {})
            return io.BytesIO(json.dumps(response).encode())
    result = DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True)._complete([], model=REVIEW_MODEL)
    assert result["actual_model"] == expected


def test_generation_prompt_does_not_seed_internal_transaction_names():
    assert "Solver自动负责" in SYSTEM_PROMPT
    assert all(name not in SYSTEM_PROMPT for name in (
        "begin_attempt", "prepare_publication", "commit_attempt", "abort_attempt",
    ))
    assert "运行和验证状态由平台统一显示" in SYSTEM_PROMPT
    assert all(word not in SYSTEM_PROMPT for word in ("已验证", "未验证", "verified", "validated", "tested"))


def test_generation_focus_preserves_guide_reference_and_real_feedback_without_mutating_packet():
    packet = {"entry_key": "adapter.example", "source_guide_reference": {"evidence_ids": ["e1"], "code": "def callback(x):\n    return x"},
              "editor_feedback": {"validation_issue": "Use the actual callback consumer"}}
    original = deepcopy(packet)
    generate_payload(tutorial_payload(), packet)
    assert packet == original


@pytest.mark.parametrize("guide_chars,draft_chars,evidence_chars,expected", [
    (20, 20, 20, {}),
    (19496, 30, 30000, {"guide_reference_omitted_for_size": 1}),
    (19496, 45000, 10000, {"guide_reference_omitted_for_size": 1, "prior_draft_omitted_for_size": 1}),
    (0, 45000, 10000, {"prior_draft_omitted_for_size": 1}),
])
def test_generation_wire_budget_omits_only_optional_references_in_order_without_mutating_source(
        guide_chars, draft_chars, evidence_chars, expected):
    packet = {"entry_key": "tool.example", "source_digest": "unchanged-digest",
              "evidence": [{"id": "e1", "text": "源" * evidence_chars + "\nreturn preserved_code"}],
              "editor_feedback": {"validation_issue": "Keep real validation feedback",
                                  "source_review": {"decision": "revise", "issues": ["Keep the actual issue"]},
                                  "instruction": "Correct the actual error",
                                  "previous_tutorial": {"code": "稿" * draft_chars}}}
    if guide_chars:
        packet["source_guide_reference"] = {"code": "指" * guide_chars}
    original, calls = deepcopy(packet), []
    class Opener:
        def open(self, request, **kwargs):
            assert len(request.data) <= 128 * 1024
            body = json.loads(request.data)
            calls.append(json.loads(body["messages"][1]["content"]))
            return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                                          "usage": {"total_tokens": 5}}).encode())
    result = DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate(packet)
    assert result["usage"] == {"total_tokens": 5, "generation_thinking_calls": 1, **expected}
    assert packet == original and len(calls) == 1
    submitted = calls[0]
    assert submitted["evidence"] == packet["evidence"]
    assert submitted["source_digest"] == packet["source_digest"] and submitted["task_focus"]
    expected_feedback = deepcopy(packet["editor_feedback"])
    if "prior_draft_omitted_for_size" in expected:
        expected_feedback.pop("previous_tutorial")
    assert submitted["editor_feedback"] == expected_feedback
    if guide_chars and "guide_reference_omitted_for_size" not in expected:
        assert submitted["source_guide_reference"] == packet["source_guide_reference"]
    else:
        assert "source_guide_reference" not in submitted


def test_generation_wire_budget_never_truncates_evidence_or_feedback_to_make_request_fit():
    packet = {"source_digest": "unchanged", "evidence": [{"id": "e1", "text": "源" * 50000}],
              "source_guide_reference": {"code": "optional guide"},
              "editor_feedback": {"validation_issue": "actual problem", "source_review": {"issues": ["actual issue"]},
                                  "previous_tutorial": {"code": "optional prior draft"}}}
    original = deepcopy(packet)
    class Opener:
        def open(self, *args, **kwargs):
            raise AssertionError("oversized evidence must be rejected before network")
    with pytest.raises(CurationProviderError, match="^ai_packet_too_large$"):
        DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate(packet)
    assert packet == original


def test_complete_default_remains_non_thinking_with_configured_budget():
    class Opener:
        def open(self, request, **kwargs):
            body = json.loads(request.data)
            assert body["thinking"] == {"type": "disabled"}
            assert "reasoning_effort" not in body
            assert body["max_tokens"] == 1024 and body["temperature"] == 0.1
            return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}).encode())
    result = DeepSeekGenerator(DeepSeekConfig("test-only-key", max_output_tokens=1024), opener=Opener(), allow_paid_requests=True)._complete([])
    assert result["note"] == {} and "generation_thinking_calls" not in result["usage"]


@pytest.mark.parametrize("content", [None, "", " \n ", '{"tutorial":'])
def test_thinking_exhaustion_keeps_safe_incomplete_without_budget_retry_or_fallback(content):
    calls = []
    class Opener:
        def open(self, request, **kwargs):
            calls.append(json.loads(request.data))
            return io.BytesIO(json.dumps({"choices": [{"finish_reason": "length", "message": {
                "content": content, "reasoning_content": "PRIVATE REASONING"}}], "usage": {
                "completion_tokens": 16384, "completion_tokens_details": {"reasoning_tokens": 16384}}}).encode())
    with pytest.raises(CurationProviderError, match="^ai_response_incomplete$") as caught:
        DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate({})
    assert len(calls) == 1 and calls[0]["max_tokens"] == 16384
    assert calls[0]["thinking"] == {"type": "enabled"}
    assert caught.value.diagnostics["reasoning_tokens"] == 16384
    assert "PRIVATE REASONING" not in json.dumps(caught.value.diagnostics)


@pytest.mark.parametrize("reason,expected", [("length", "length"), ("content_filter", "content_filter"),
                                            ("tool_calls", "tool_calls"),
                                            ("insufficient_system_resource", "insufficient_system_resource"),
                                            ("aborted", "aborted"), ("private-key-fragment", "unknown"),
                                            (None, "unknown")])
@pytest.mark.parametrize("operation", ["generate", "review"])
def test_nonstop_response_still_rejects_and_exposes_only_safe_metadata(reason, expected, operation):
    content = json.dumps(tutorial_payload(), ensure_ascii=False) + "PRIVATE-CONTENT"
    reasoning = "PRIVATE-REASONING test-only-key"
    response = {"choices": [{"finish_reason": reason,
                             "message": {"content": content, "reasoning_content": reasoning,
                                         "headers": {"Authorization": "Bearer test-only-key"}}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 12288, "total_tokens": 12388,
                          "completion_tokens_details": {"reasoning_tokens": 12000, "private": "PRIVATE-DETAIL"},
                          "api_key": "test-only-key", "arbitrary": 999},
                "request": "PRIVATE-REQUEST"}

    class Opener:
        def open(self, request, **kwargs):
            body = json.loads(request.data)
            if operation == "review":
                assert body["thinking"] == {"type": "disabled"}
                assert "reasoning_effort" not in body
                assert body["max_tokens"] == 12288
            else:
                assert body["thinking"] == {"type": "enabled"}
                assert body["reasoning_effort"] == "low"
                assert body["max_tokens"] == 16384
            return io.BytesIO(json.dumps(response).encode())

    with pytest.raises(CurationProviderError, match="^ai_response_incomplete$") as caught:
        generator = DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True)
        generator.review({}, {}) if operation == "review" else generator.generate({})
    assert caught.value.diagnostics == {
        "finish_reason": expected, "prompt_tokens": 100, "completion_tokens": 12288,
        "total_tokens": 12388, "reasoning_tokens": 12000,
        "content_chars": len(content), "content_non_whitespace_chars": len("".join(content.split())),
        "reasoning_chars": len(reasoning),
    }
    visible = repr(caught.value) + json.dumps(caught.value.diagnostics)
    assert all(value not in visible for value in (
        "test-only-key", "PRIVATE-CONTENT", "PRIVATE-REASONING", "PRIVATE-DETAIL", "PRIVATE-REQUEST",
        "private-key-fragment", "Authorization", "headers",
    ))


def test_error_constructor_filters_untrusted_diagnostics_types_keys_and_bounds():
    source = {"finish_reason": ["length", "private"], "prompt_tokens": True, "completion_tokens": -1,
              "total_tokens": 1.5, "reasoning_tokens": 10**100, "content_chars": 0, "reasoning_chars": 123,
              "content": "private", "headers": {"Authorization": "test-only-key"}}
    error = CurationProviderError("ai_response_incomplete", diagnostics=source)
    assert error.diagnostics == {"finish_reason": "unknown", "content_chars": 0, "reasoning_chars": 123}
    source["reasoning_chars"] = 456
    assert error.diagnostics["reasoning_chars"] == 123
    assert CurationProviderError("ai_response_invalid").diagnostics == {}


def test_incomplete_response_tolerates_missing_message_and_malformed_usage_without_echoing_them():
    response = {"choices": [{"finish_reason": "length", "message": {"content": None, "reasoning_content": []}}],
                "usage": {"prompt_tokens": "PRIVATE", "completion_tokens": False,
                          "reasoning_tokens": 120, "total_tokens": 2_000_000,
                          "completion_tokens_details": "PRIVATE"}}

    class Opener:
        def open(self, *args, **kwargs):
            return io.BytesIO(json.dumps(response).encode())

    with pytest.raises(CurationProviderError) as caught:
        DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate({})
    assert str(caught.value) == "ai_response_incomplete"
    assert caught.value.diagnostics == {"finish_reason": "length", "content_chars": 0, "content_non_whitespace_chars": 0,
                                        "reasoning_chars": 0, "reasoning_tokens": 120}


def test_incomplete_json_whitespace_is_distinguishable_without_retaining_content():
    response = {"choices": [{"finish_reason": "length", "message": {"content": " \t\n\u3000 "}}],
                "usage": {"completion_tokens": 12288}}

    class Opener:
        def open(self, *args, **kwargs):
            return io.BytesIO(json.dumps(response).encode())

    with pytest.raises(CurationProviderError) as caught:
        DeepSeekGenerator(DeepSeekConfig("test-only-key"), opener=Opener(), allow_paid_requests=True).generate({})
    assert caught.value.diagnostics == {"finish_reason": "length", "completion_tokens": 12288,
                                        "content_chars": 5, "content_non_whitespace_chars": 0, "reasoning_chars": 0}


@pytest.mark.parametrize("initial_decision", ["revise", "publish"])
def test_review_format_repair_cannot_clear_substantive_findings_on_the_same_candidate(monkeypatch, initial_decision):
    generator = DeepSeekGenerator(DeepSeekConfig("test-only-key"))
    calls = []
    issue = {"location": "code", "problem": "Constructor has a wrong parameter",
             "required_change": "Use the declared constructor", "evidence_ids": ["e1"]}
    def complete(messages, **kwargs):
        assert kwargs == {"thinking": False, "max_tokens": 12288, "model": REVIEW_MODEL}
        calls.append(messages)
        response = ({"decision": initial_decision, "issues": [issue], "checks": [],
                     "evidence_ids": ["e1"], "version": "unsupported"} if len(calls) == 1 else
                    {"decision": "publish", "issues": [], "checks": ["Input checked", "Output checked", "Extension checked"],
                     "evidence_ids": ["e1"]})
        return {"note": response, "usage": {"total_tokens": 5}}
    monkeypatch.setattr(generator, "_complete", complete)
    with pytest.raises(CurationProviderError, match="^ai_review_format_discarded_findings$"):
        generator.review({"evidence": [{"id": "e1"}]}, {"tutorial": {"code": "same candidate"}})
    assert len(calls) == 2 and calls[0][:2] == calls[1][:2]


def test_review_format_repairs_rejection_without_changing_candidate_or_losing_usage(monkeypatch):
    generator = DeepSeekGenerator(DeepSeekConfig("test-only-key"))
    valid = {"decision": "revise", "issues": [{"location": "code", "problem": "Wrong constructor",
        "required_change": "Use actual signature", "evidence_ids": ["e1"]}],
        "checks": ["Constructor checked"], "evidence_ids": ["e1"]}
    calls = []
    def complete(messages, **kwargs):
        assert kwargs == {"thinking": False, "max_tokens": 12288, "model": REVIEW_MODEL}
        calls.append(messages)
        return {"note": {**valid, **({"version": "unsupported"} if len(calls) == 1 else {})},
                "usage": {"total_tokens": 5}}
    monkeypatch.setattr(generator, "_complete", complete)
    result = generator.review({"evidence": [{"id": "e1"}]}, {"tutorial": {"code": "same candidate"}})
    assert result["note"] == valid and result["usage"]["total_tokens"] == 10
    assert result["usage"]["review_format_repairs"] == 1
    assert calls[0][:2] == calls[1][:2]


def test_review_format_failure_is_a_safe_provider_error_after_exactly_two_attempts(monkeypatch):
    generator = DeepSeekGenerator(DeepSeekConfig("test-only-key"))
    calls = []
    def complete(messages, **kwargs):
        assert kwargs == {"thinking": False, "max_tokens": 12288, "model": REVIEW_MODEL}
        calls.append(messages)
        return {"note": {"unsupported": "PRIVATE REVIEW CONTENT"}, "usage": {"total_tokens": 5}}
    monkeypatch.setattr(generator, "_complete", complete)
    with pytest.raises(CurationProviderError, match="^ai_review_format_invalid$") as caught:
        generator.review({"evidence": [{"id": "e1"}]}, {"tutorial": {"code": "same candidate"}})
    assert len(calls) == 2 and "PRIVATE" not in str(caught.value)
