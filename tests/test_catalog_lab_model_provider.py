"""Independent inference backends retain the assistant's existing trust gate."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import threading
import time
from urllib.error import HTTPError, URLError

import pytest

from nsgablack.catalog.curation_provider import DeepSeekConfig, ENDPOINT
from nsgablack.catalog.lab_assistant import (
    AssistantManager, AssistantProviderError, DeepSeekAssemblyGenerator,
    MAX_RESPONSE_BYTES, assistant_messages,
)
from nsgablack.catalog.lab_model_provider import (
    CompatibleAssistantConfig, CompatibleAssemblyGenerator,
    create_assistant_generator, load_assistant_model_config,
)


def _completion(value):
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps(value, ensure_ascii=False)}}]}, ensure_ascii=False).encode()


@pytest.mark.parametrize("names,expected", [
    (["check_project_edit"], {"type": "function", "function": {"name": "check_project_edit"}}),
    (["framework_api", "check_project_edit"], "auto"),
    ([], "none"),
])
def test_source_phase_controls_native_tool_choice_in_provider_request(names, expected):
    from nsgablack.catalog.lab_model_provider import complete_project_turn
    captured = []
    class Opener:
        def open(self, request, timeout):
            captured.append(json.loads(request.data))
            return _Response(_completion({"explanation": "not run", "questions": [], "proposal_digest": None}), url=ENDPOINT)
    owner = DeepSeekAssemblyGenerator(DeepSeekConfig(api_key="test-only-api-key"), opener=Opener())
    tools = [{"type": "function", "function": {"name": name, "parameters": {"type": "object"}}} for name in names]
    complete_project_turn(owner, [{"role": "user", "content": "source task"}], tools)
    assert captured[0]["tool_choice"] == expected
    if not names:
        assert "tools" not in captured[0]
        assert captured[0]["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in captured[0]


class _Response(io.BytesIO):
    def __init__(self, data, url="https://models.example/v1/chat/completions"):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


def _project_json_turn(reply, tools, *, messages=None, raw=False, finish_reason="stop", native_calls=None,
                       feedback_protocol_errors=False, model="deepseek-flash"):
    from nsgablack.catalog.lab_model_provider import complete_project_turn
    captured = []
    class Opener:
        def open(self, request, **kwargs):
            captured.append(json.loads(request.data))
            message = {"role": "assistant", "content": reply if raw else json.dumps(reply)}
            if native_calls is not None:
                message["tool_calls"] = native_calls
            response = {"model": model, "choices": [
                {"finish_reason": finish_reason, "message": message}]}
            return _Response(json.dumps(response).encode(), url=ENDPOINT)
    owner = DeepSeekAssemblyGenerator(DeepSeekConfig(api_key="test-only-api-key"), opener=Opener())
    result = complete_project_turn(owner, messages or [{"role": "user", "content": "task"}],
                                   tools, protocol="json", feedback_protocol_errors=feedback_protocol_errors)
    return result, captured[0]


def _project_tool(name="framework_api"):
    return {"type": "function", "function": {"name": name, "parameters": {
        "type": "object", "properties": {"symbol": {"type": "string", "minLength": 1}},
        "required": ["symbol"], "additionalProperties": False}}}


def test_project_json_protocol_is_explicit_and_preserves_configuration_and_exact_arguments():
    import hashlib
    source = 'class Example:\n    text = "DSML is data here"\n'
    tool = {"type": "function", "function": {"name": "check_project_edit", "parameters": {
        "type": "object", "properties": {"source": {"type": "string"}},
        "required": ["source"], "additionalProperties": False}}}
    reply = {"type": "tool_calls", "calls": [{"name": "check_project_edit", "arguments": {"source": source}}]}
    result, body = _project_json_turn(reply, [tool])
    assert body["model"] == result["model"] == "deepseek-flash"
    assert body["thinking"] == {"type": "disabled"}
    assert body["temperature"] == 0.1 and body["stream"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert "tools" not in body and "tool_choice" not in body
    assert '"choice":"check_project_edit"' in body["messages"][-1]["content"]
    assert result["protocol"] == "json" and result["finish_reason"] == "tool_calls"
    assert result["protocol_receipt"]["native_tool_calls"] is False
    assert result["protocol_receipt"]["wire_request_sha256"] == hashlib.sha256(
        json.dumps(body, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    assert result["protocol_receipt"]["wire_messages_sha256"] == hashlib.sha256(
        json.dumps(body["messages"], ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
    assert json.loads(result["message"]["tool_calls"][0]["function"]["arguments"])["source"] == source


def test_project_json_history_keeps_original_message_text_ids_and_results_losslessly():
    from copy import deepcopy
    source = 'print("中文 \\n")\n'
    call = {"id": "earlier-id", "type": "function", "function": {
        "name": "check_project_edit", "arguments": json.dumps({"source": source}, ensure_ascii=False)}}
    messages = [{"role": "system", "content": "original system"},
                {"role": "assistant", "content": "original assistant text", "tool_calls": [call]},
                {"role": "tool", "tool_call_id": "earlier-id", "content": '{"error":"actual failure"}'},
                {"role": "user", "content": "repair"}]
    original = deepcopy(messages)
    result, body = _project_json_turn({"type": "tool_calls", "calls": [
        {"name": "framework_api", "arguments": {"symbol": "Pool"}},
        {"name": "framework_api", "arguments": {"symbol": "ChangePool"}}]}, [_project_tool()], messages=messages)
    assert messages == original
    assert body["messages"][0] == original[0] and body["messages"][3] == original[3]
    assert json.loads(body["messages"][1]["content"])["message"] == original[1]
    assert json.loads(body["messages"][2]["content"])["message"] == original[2]
    assert body["messages"][2]["role"] == "user"
    assert all(m["role"] != "tool" and "tool_calls" not in m for m in body["messages"])
    ids = [c["id"] for c in result["message"]["tool_calls"]]
    assert len(set(ids)) == 2 and "earlier-id" not in ids
    repeated, _ = _project_json_turn({"type": "tool_calls", "calls": [
        {"name": "framework_api", "arguments": {"symbol": "Pool"}}]}, [_project_tool()],
        messages=messages + [result["message"], {"role": "tool", "tool_call_id": ids[0], "content": "again"}])
    assert repeated["message"]["tool_calls"][0]["id"] not in ids


def test_project_json_final_unwraps_existing_runtime_fields_without_inventing_edit_digest():
    answer = {"explanation": "尚未通过", "questions": [], "proposal_digest": None}
    result, body = _project_json_turn({"type": "final", "answer": answer}, [])
    assert json.loads(result["message"]["content"]) == answer
    assert result["finish_reason"] == "stop" and "tool_calls" not in result["message"]
    assert '"choice":"final_only"' in body["messages"][-1]["content"]


@pytest.mark.parametrize("reply", [
    {"type": "tool_calls", "calls": [{"name": "obsolete_tool", "arguments": {"symbol": "Pool"}}]},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {}}]},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": 1}}]},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": ""}}]},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "Pool", "include_body": True}}]},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": '{"symbol":"Pool"}'}]},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "Pool"}, "id": "model-owned"}]},
    {"type": "tool_calls", "calls": []},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "Pool"}}] * 9},
    {"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "Pool"}}], "answer": {}},
    {"type": "final", "answer": []},
    {"type": "final", "answer": {}, "calls": []},
])
def test_project_json_rejects_nonconforming_complete_envelopes(reply):
    with pytest.raises(AssistantProviderError, match="ai_project_protocol_invalid"):
        _project_json_turn(reply, [_project_tool()])


@pytest.mark.parametrize("raw", [
    '</｜DSML｜parameter></｜DSML｜invoke></｜DSML｜calls>',
    '```json\n{"type":"final","answer":{}}\n```',
    'text {"type":"final","answer":{}}',
    '{"type":"final","answer":{}} extra',
    '{"type":"final","type":"tool_calls","answer":{}}',
    '{"type":"final","answer":{"x":NaN}}',
    '{"type":"final","answer":{"x":1e400}}',
])
def test_project_json_never_extracts_repairs_or_executes_arbitrary_text(raw):
    with pytest.raises(AssistantProviderError, match="ai_project_protocol_invalid"):
        _project_json_turn(raw, [], raw=True)


@pytest.mark.parametrize("reply,tools", [
    ({"type": "final", "answer": {}}, [_project_tool("check_project_edit")]),
    ({"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "Pool"}}]}, [_project_tool("check_project_edit")]),
    ({"type": "tool_calls", "calls": [{"name": "framework_api", "arguments": {"symbol": "Pool"}}]}, []),
])
def test_project_json_enforces_current_host_choice(reply, tools):
    with pytest.raises(AssistantProviderError, match="ai_project_protocol_invalid"):
        _project_json_turn(reply, tools)


def test_project_json_rejects_provider_native_calls_instead_of_silently_switching_protocol():
    with pytest.raises(AssistantProviderError, match="ai_project_protocol_invalid"):
        _project_json_turn({"type": "final", "answer": {}}, [], native_calls=[{
            "id": "foreign", "type": "function", "function": {"name": "framework_api", "arguments": "{}"}}])


@pytest.mark.parametrize("content", [
    '</｜DSML｜parameter></｜DSML｜invoke></｜DSML｜calls>',
    '{"type":"tool_calls","calls":[{"name":"obsolete","arguments":{}}]}',
    '{"type":"tool_calls","calls":[{"name":"framework_api","arguments":{"symbol":5}}]}',
])
def test_host_opt_in_protocol_feedback_preserves_text_without_accepting_or_executing_it(content):
    import hashlib
    turn, _ = _project_json_turn(content, [_project_tool()], raw=True, feedback_protocol_errors=True)
    assert turn["message"] == {"role": "assistant", "content": content}
    assert turn["model"] == "deepseek-flash" and turn["protocol"] == "json"
    assert turn["protocol_error"]["code"] == "ai_project_tool_protocol_invalid"
    assert turn["protocol_error"]["allowed_tools"] == ["framework_api"]
    assert turn["protocol_receipt"]["accepted"] is False
    assert turn["protocol_receipt"]["executed"] is False
    assert turn["protocol_receipt"]["wire_content_sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert turn["protocol_receipt"]["content_truncated"] is False
    assert "tool_calls" not in turn["message"]


def test_protocol_feedback_is_bounded_and_records_full_content_identity():
    import hashlib
    content = "not JSON " + "x" * (26 * 1024)
    turn, _ = _project_json_turn(content, [], raw=True, feedback_protocol_errors=True)
    assert len(turn["message"]["content"].encode()) == 24 * 1024
    receipt = turn["protocol_receipt"]
    assert receipt["content_truncated"] is True and receipt["wire_content_bytes"] == len(content.encode())
    assert receipt["wire_content_sha256"] == hashlib.sha256(content.encode()).hexdigest()


def test_json_audit_preserves_exact_public_wire_content_on_success_and_feedback_error():
    import hashlib
    contents = ['  {"type":"final", "answer":{"explanation":"中文", "questions":[], "proposal_digest":null}}\n',
                "invalid envelope " + "x" * (26 * 1024)]
    for content in contents:
        turn, _ = _project_json_turn(content, [], raw=True, feedback_protocol_errors=True)
        assert turn["protocol_wire_content"] == content
        assert turn["protocol_receipt"]["wire_content_sha256"] == hashlib.sha256(
            turn["protocol_wire_content"].encode("utf-8")).hexdigest()


@pytest.mark.parametrize("model", [None, "", "another-model"])
def test_protocol_feedback_never_hides_missing_or_changed_model_identity(model):
    with pytest.raises(AssistantProviderError, match="ai_response_invalid"):
        _project_json_turn("not JSON", [], raw=True, feedback_protocol_errors=True, model=model)


def test_protocol_feedback_keeps_truncation_and_invalid_response_shell_as_errors():
    with pytest.raises(AssistantProviderError, match="ai_response_incomplete"):
        _project_json_turn("not JSON", [], raw=True, feedback_protocol_errors=True, finish_reason="length")
    with pytest.raises(AssistantProviderError, match="ai_response_invalid"):
        _project_json_turn("   ", [], raw=True, feedback_protocol_errors=True)


@contextmanager
def _serve(callback):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            calls.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(raw)})
            status, headers, data = callback(calls[-1])
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def _config_file(tmp_path, value):
    path = tmp_path / "assistant-model.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize("provider", [None, "deepseek"])
def test_old_deepseek_config_and_explicit_provider_remain_supported(tmp_path, provider):
    value = {"api_key": "test-only-deepseek-key", "model": "deepseek-flash"}
    if provider is not None:
        value["provider"] = provider
    config = load_assistant_model_config(_config_file(tmp_path, value))
    assert isinstance(config, DeepSeekConfig)
    assert isinstance(create_assistant_generator(config), DeepSeekAssemblyGenerator)
    assert "test-only-deepseek-key" not in repr(config)


def test_compatible_config_is_independent_and_never_inherits_a_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-be-used")
    monkeypatch.setenv("OPENAI_API_KEY", "also-must-not-be-used")
    config = load_assistant_model_config(_config_file(tmp_path, {
        "provider": "compatible", "base_url": "http://127.0.0.1:9000/v1", "model": "org/framework-lora"}))
    assert isinstance(config, CompatibleAssistantConfig) and config.api_key is None
    assert "127.0.0.1" not in repr(config)
    assert isinstance(create_assistant_generator(config), CompatibleAssemblyGenerator)
    assert isinstance(create_assistant_generator(tmp_path / "assistant-model.json"), CompatibleAssemblyGenerator)


@pytest.mark.parametrize("url", [
    "http://models.example/v1", "http://10.0.0.1/v1", "http://127.0.0.1.models.example/v1",
    "http://localhost.models.example/v1", "http://2130706433/v1", "http://0x7f000001/v1",
    "https://user:password@models.example/v1", "https://models.example/v1?key=secret",
    "https://models.example/v1?", "https://models.example/v1#fragment", "https://models.example/v1#",
    "https://models.example/v1/../admin", "https://models.example/v1/chat/completions",
    "https://models.example/%76%31", "https://models.example//v1", "https://models.example:0/v1",
    "https://models.example:65536/v1", "ftp://models.example/v1", "file:///tmp/model",
    "https://models.example\\@evil.example/v1", " https://models.example/v1",
    "https://models.example/v1\n", "https://models..example/v1", "https://-models.example/v1",
    "https://models.example:/v1", "http://[::1%25zone]:9000/v1", "https://模型.example/v1",
])
def test_endpoint_rejects_ambiguous_paths_untrusted_plaintext_and_embedded_secrets(url):
    with pytest.raises(ValueError, match="invalid_assistant_endpoint") as exc:
        CompatibleAssistantConfig(url, "framework", api_key="test-only-key")
    assert url not in str(exc.value)


@pytest.mark.parametrize("url", ["http://127.0.0.1:9000/v1", "http://localhost:9000/", "http://[::1]:9000"])
def test_only_loopback_endpoints_may_omit_an_explicit_credential(url):
    assert CompatibleAssistantConfig(url, "framework").api_key is None
    with pytest.raises(ValueError, match="assistant_credential_required"):
        CompatibleAssistantConfig("https://models.example/v1", "framework")


@pytest.mark.parametrize("url, endpoint", [
    ("https://models.example:443/v1/", "https://models.example:443/v1/chat/completions"),
    ("https://192.0.2.1/v1", "https://192.0.2.1/v1/chat/completions"),
    ("https://[2001:db8::1]:9443/", "https://[2001:db8::1]:9443/chat/completions"),
    ("https://xn--fiqs8s.example/v1", "https://xn--fiqs8s.example/v1/chat/completions"),
])
def test_trusted_https_accepts_explicit_dns_and_ip_origins_without_network(url, endpoint):
    config = CompatibleAssistantConfig(url, "framework", api_key="test-only-key")
    assert CompatibleAssemblyGenerator(config)._endpoint == endpoint
    assert "test-only-key" not in repr(config) and url not in repr(config)


@pytest.mark.parametrize("override", [
    {"api_key": ""}, {"api_key": "Bearer\nsecret"}, {"api_key": "space key"},
    {"model": ""}, {"model": "bad\nmodel"}, {"model": "../../model"},
    {"model": "https://model"}, {"max_output_tokens": True}, {"max_output_tokens": 4097},
    {"timeout_seconds": 61}, {"timeout_seconds": False}, {"json_mode": "true"},
])
def test_server_model_parameters_are_explicit_and_validated(override):
    value = {"base_url": "http://127.0.0.1:9000/v1", "model": "framework"}
    with pytest.raises(ValueError):
        CompatibleAssistantConfig(**{**value, **override})


@pytest.mark.parametrize("value", [
    {"provider": "other"}, {"provider": None}, {"provider": "compatible", "model": "x"},
    {"provider": "compatible", "base_url": "http://127.0.0.1", "model": "x", "thinking": "disabled"},
    {"provider": "deepseek", "api_key": "test-only-key", "base_url": "https://models.example"},
    {"provider": "compatible", "base_url": "https://models.example/v1", "model": "x"},
    [], "private-key-canary", None,
])
def test_loader_fails_closed_with_one_safe_error(tmp_path, value):
    with pytest.raises(AssistantProviderError) as exc:
        load_assistant_model_config(_config_file(tmp_path, value))
    assert str(exc.value) == "ai_config_invalid"


def test_loader_rejects_duplicate_fields_oversized_or_missing_files(tmp_path):
    path = tmp_path / "model.json"
    for raw in ('{"provider":"deepseek","provider":"compatible"}', "x" * 16385):
        path.write_text(raw)
        with pytest.raises(AssistantProviderError, match="ai_config_invalid"):
            load_assistant_model_config(path)
    with pytest.raises(AssistantProviderError, match="ai_config_invalid"):
        load_assistant_model_config(tmp_path / "missing.json")


def test_request_uses_current_shared_messages_and_no_vendor_specific_thinking(monkeypatch):
    import nsgablack.catalog.lab_model_provider as module
    handlers, calls = [], []
    packet = {"instruction": "说明 Pool 与 Unit", "base_url": "https://attacker.invalid", "model": "untrusted"}

    class Opener:
        def open(self, request, *, timeout):
            calls.append(request)
            assert request.full_url == "https://models.example/v1/chat/completions"
            assert request.headers["Authorization"] == "Bearer separate-test-key"
            assert timeout == 60
            body = json.loads(request.data)
            assert body["model"] == "org/framework-lora"
            assert body["messages"] == assistant_messages(packet)
            assert body["response_format"] == {"type": "json_object"}
            assert "thinking" not in body and body["stream"] is False
            assert "separate-test-key" not in json.dumps(body)
            return _Response(_completion({"draft": None}))

    def build(*items):
        handlers.extend(items)
        return Opener()

    monkeypatch.setattr(module, "build_opener", build)
    generator = CompatibleAssemblyGenerator(CompatibleAssistantConfig(
        "https://models.example/v1", "org/framework-lora", api_key="separate-test-key"))
    assert generator.generate(packet) == {"draft": None}
    assert handlers[0].proxies == {}
    with pytest.raises(AssistantProviderError, match="ai_redirect_refused"):
        handlers[1].redirect_request(None, None, 302, "", {}, "https://attacker.invalid")
    assert len(calls) == 1


def test_json_mode_may_be_disabled_without_relaxing_json_reply_contract():
    class Opener:
        def open(self, request, **kwargs):
            assert "response_format" not in json.loads(request.data)
            return _Response(_completion({"draft": None}))

    config = CompatibleAssistantConfig("https://models.example/v1", "framework", api_key="key", json_mode=False)
    assert CompatibleAssemblyGenerator(config, opener=Opener()).generate({}) == {"draft": None}


@pytest.mark.parametrize("failure, code", [
    (HTTPError(ENDPOINT, 429, "secret-body-key", {}, None), "ai_provider_refused"),
    (HTTPError(ENDPOINT, 503, "secret-body-key", {}, None), "ai_provider_refused"),
    (URLError("secret-body-key"), "ai_transport_failed"),
    (TimeoutError("secret-body-key"), "ai_transport_failed"),
])
def test_provider_errors_never_retry_or_expose_provider_data(failure, code):
    calls = []

    class Opener:
        def open(self, *_args, **_kwargs):
            calls.append(1)
            raise failure

    config = CompatibleAssistantConfig("https://models.example/v1", "framework", api_key="key")
    with pytest.raises(AssistantProviderError) as caught:
        CompatibleAssemblyGenerator(config, opener=Opener()).generate({})
    assert str(caught.value) == code and calls == [1]


@pytest.mark.parametrize("raw, code", [
    (b"{}", "ai_response_invalid"), (b"not-json", "ai_response_invalid"),
    (b"x" * (MAX_RESPONSE_BYTES + 1), "ai_response_invalid"),
    (b'{"choices":[{"finish_reason":"length"}]}', "ai_response_incomplete"),
    (_completion([]), "ai_response_invalid"),
    (b'{"choices":[{"finish_reason":"stop","message":{"content":"{\\"x\\":NaN}"}}]}', "ai_response_invalid"),
    (b'{"choices":[{"finish_reason":"stop","message":{"content":"{\\"x\\":1,\\"x\\":2}"}}]}', "ai_response_invalid"),
], ids=["missing-choice", "non-json", "oversized", "truncated", "non-object", "nan", "duplicate"])
def test_invalid_or_truncated_provider_reply_is_refused(raw, code):
    class Opener:
        def open(self, *_args, **_kwargs):
            return _Response(raw)

    config = CompatibleAssistantConfig("https://models.example/v1", "framework", api_key="key")
    with pytest.raises(AssistantProviderError, match=code):
        CompatibleAssemblyGenerator(config, opener=Opener()).generate({})


def test_wrong_guide_or_oversized_packet_is_refused_before_network():
    class Opener:
        def open(self, *_args, **_kwargs):
            pytest.fail("invalid packet reached network")

    generator = CompatibleAssemblyGenerator(CompatibleAssistantConfig("http://127.0.0.1", "framework"), opener=Opener())
    with pytest.raises(AssistantProviderError, match="ai_guide_mismatch"):
        generator.generate({"guide_metadata": {"fake": "version"}})
    with pytest.raises(AssistantProviderError, match="ai_packet_too_large"):
        generator.generate({"instruction": "x" * (128 * 1024)})


def test_real_loopback_model_ignores_proxy_env_and_does_not_receive_other_provider_keys(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "never-copy-this-key")
    with _serve(lambda _: (200, {}, _completion({"draft": None}))) as (url, calls):
        generator = CompatibleAssemblyGenerator(CompatibleAssistantConfig(url + "/v1", "framework"))
        assert generator.generate({"instruction": "解释框架"}) == {"draft": None}
        assert len(calls) == 1 and calls[0]["path"] == "/v1/chat/completions"
        assert "Authorization" not in calls[0]["headers"]
        assert "never-copy-this-key" not in json.dumps(calls)


def test_real_redirect_is_refused_and_never_reaches_second_origin():
    with _serve(lambda _: (200, {}, _completion({}))) as (destination, target_calls):
        with _serve(lambda _: (307, {"Location": destination + "/chat/completions"}, b"")) as (source, calls):
            generator = CompatibleAssemblyGenerator(CompatibleAssistantConfig(source, "framework", api_key="private-key"))
            with pytest.raises(AssistantProviderError, match="ai_redirect_refused"):
                generator.generate({})
            assert len(calls) == 1 and not target_calls


def _done(manager, job):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        value = manager.poll(job)
        if value["status"] in {"succeeded", "failed"}:
            return value
        time.sleep(.01)
    pytest.fail("assistant_did_not_finish")


@pytest.mark.parametrize("invalid", [False, True])
def test_real_model_roundtrip_retains_manager_validation_dedup_and_unlimited_daily_policy(tmp_path, invalid):
    from nsgablack.catalog.lab_assembly import assembly_from_recipe

    def reply(request):
        packet = json.loads(request["body"]["messages"][1]["content"])
        value = {"base_digest": packet["base_digest"], "draft": None,
                 "explanation": "Problem 定义原始评估，Bias 提供选择偏好。", "changes": [],
                 "questions": [], "evidence_keys": []}
        if invalid:
            value["extra"] = "provider-secret-canary"
        return 200, {}, _completion(value)

    with _serve(reply) as (url, calls):
        manager = AssistantManager(CompatibleAssemblyGenerator(
            CompatibleAssistantConfig(url + "/v1", "framework")), state_path=tmp_path / "requests.json")
        try:
            spec = assembly_from_recipe("ga")
            job = manager.submit(spec, instruction="解释当前装配", request_id="c" * 32)
            done = _done(manager, job["job_id"])
            duplicate = manager.submit(spec, instruction="解释当前装配", request_id="c" * 32)
            assert duplicate["job_id"] == job["job_id"] and len(calls) == 1
            assert manager.capabilities()["limits"]["requests_per_utc_day"] is None
            assert manager.capabilities()["quota"]["remaining"] is None
            if invalid:
                assert done["status"] == "failed" and done["error"]["code"] == "ai_draft_invalid"
                assert "provider-secret-canary" not in json.dumps(done)
            else:
                assert done["status"] == "succeeded", done
                assert done["result"]["verification_status"] == "not_run"
        finally:
            manager.close()


def test_service_selects_configured_backend_without_changing_runner_or_loading_env(monkeypatch, tmp_path):
    from nsgablack.catalog import lab_service
    config = _config_file(tmp_path, {"provider": "compatible", "base_url": "http://127.0.0.1:9000/v1", "model": "framework"})
    worker = tmp_path / "worker.json"
    worker.write_text(json.dumps({"token": "a" * 64}))
    captured = []

    class Server:
        def __init__(self, address, **kwargs):
            captured.append(kwargs)

        def __enter__(self):
            return self

        def serve_forever(self):
            assert isinstance(captured[0]["jobs"]._generator, CompatibleAssemblyGenerator)

        def __exit__(self, *_args):
            captured[0]["jobs"].close()

    monkeypatch.setattr(lab_service, "LabHTTPServer", Server)
    lab_service.main(["--role", "assistant", "--config", str(worker), "--ai-config", str(config),
                      "--state-path", str(tmp_path / "requests.json")])
    assert captured[0]["role"] == "assistant"


def test_no_arbitrary_config_object_can_select_a_backend():
    with pytest.raises(AssistantProviderError, match="ai_config_invalid"):
        create_assistant_generator({"provider": "compatible", "base_url": "https://attacker.invalid"})
