"""Responses protocol and real MCP wiring; no paid model calls in these tests."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import pytest

from nsgablack.catalog.lab_assistant import AssistantProviderError
from nsgablack.catalog.lab_openai_provider import (
    ENDPOINT, OpenAIAssistantConfig, OpenAIAssemblyGenerator,
)
from nsgablack.catalog.lab_model_provider import (
    complete_project_turn, create_assistant_generator, load_assistant_model_config,
)


class Response(io.BytesIO):
    def geturl(self):
        return ENDPOINT


class Transport:
    def __init__(self, *replies):
        self.replies = iter(replies)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(json.loads(request.data))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return Response(json.dumps(reply).encode())


def reply(*output, status="completed"):
    return {"model": "test-openai-model-1", "status": status, "output": list(output)}


def final(text='{"explanation":"done","questions":[],"proposal_digest":null}'):
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}


def call(name, arguments, call_id="call-1"):
    return {"type": "function_call", "name": name, "arguments": json.dumps(arguments), "call_id": call_id}


def tool(name="framework_api"):
    return {"type": "function", "function": {"name": name, "parameters": {
        "type": "object", "properties": {"symbol": {"type": "string"}, "member": {"type": "string"}},
        "required": ["symbol"], "additionalProperties": False}}}


def owner(transport):
    return OpenAIAssemblyGenerator(OpenAIAssistantConfig("offline-test-credential"), opener=transport)


def test_config_selects_responses_and_metadata_never_contains_secret(tmp_path, monkeypatch):
    from nsgablack.catalog.assistant_evaluation import model_configuration_metadata
    path = tmp_path / "private.json"
    path.write_text(json.dumps({"provider": "openai", "api_key": "offline-private-canary"}))
    cfg = load_assistant_model_config(path)
    assert isinstance(create_assistant_generator(cfg), OpenAIAssemblyGenerator)
    assert "offline-private-canary" not in repr(cfg)
    assert "offline-private-canary" not in json.dumps(model_configuration_metadata(cfg))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-implicitly-load")
    path.write_text('{"provider":"openai"}')
    with pytest.raises(AssistantProviderError, match="ai_config_invalid"):
        load_assistant_model_config(path)
    path.write_text('{"provider":"openai","api_key":"test","base_url":"https://attacker.invalid"}')
    with pytest.raises(AssistantProviderError, match="ai_config_invalid"):
        load_assistant_model_config(path)


def test_stateless_reasoning_and_exact_tool_pairing_survive_next_request():
    reasoning = {"type": "reasoning", "id": "rs-1", "summary": [], "encrypted_content": "opaque"}
    transport = Transport(reply(reasoning, call("framework_api", {"symbol": "Pool"})), reply(final()))
    generator = owner(transport)
    messages = [{"role": "system", "content": "Return JSON"}, {"role": "user", "content": "inspect"}]
    first = complete_project_turn(generator, messages, [tool()])
    messages += [first["message"], {"role": "tool", "tool_call_id": "call-1", "content": '{"error":"repair-needed"}'}]
    original = deepcopy(messages)
    complete_project_turn(generator, messages, [])
    assert messages == original
    body = transport.requests[1]
    assert body["input"][2] == reasoning
    assert body["input"][3] == {"type": "function_call", "call_id": "call-1", "name": "framework_api",
                                  "arguments": '{"symbol": "Pool"}'}
    assert body["input"][4] == {"type": "function_call_output", "call_id": "call-1",
                                  "output": '{"error":"repair-needed"}'}
    assert body["store"] is False and "previous_response_id" not in body
    assert body["tool_choice"] == "none" and "tools" not in body
    assert body["text"] == {"format": {"type": "json_object"}}
    assert "temperature" not in body and "thinking" not in body
    first_body = transport.requests[0]
    assert first_body["tools"][0]["strict"] is False
    assert first_body["tools"][0]["parameters"]["required"] == ["symbol"]


def test_host_forced_edit_phase_and_json_protocol_do_not_silently_fallback():
    transport = Transport(reply(call("check_project_edit", {"source": "x"})))
    generator = owner(transport)
    complete_project_turn(generator, [], [tool("check_project_edit")])
    assert transport.requests[0]["tool_choice"] == {"type": "function", "name": "check_project_edit"}
    with pytest.raises(AssistantProviderError, match="ai_project_protocol_invalid"):
        complete_project_turn(generator, [], [], protocol="json")
    assert len(transport.requests) == 1


@pytest.mark.parametrize("status,code,expected", [
    (403, "unsupported_country_region_territory", "ai_region_unsupported"),
    (401, "invalid_api_key", "ai_credential_rejected"),
    (429, "insufficient_quota", "ai_quota_exhausted"),
    (429, "rate_limit_exceeded", "ai_rate_limited"),
    (500, "unknown", "ai_provider_refused"),
])
def test_provider_failures_are_redacted_and_never_retried(status, code, expected):
    error = HTTPError(ENDPOINT, status, "sensitive-provider-text", {},
                      io.BytesIO(json.dumps({"error": {"code": code, "message": "secret-canary"}}).encode()))
    transport = Transport(error)
    with pytest.raises(AssistantProviderError, match=expected) as caught:
        owner(transport).complete([], [])
    assert str(caught.value) == expected and len(transport.requests) == 1


@pytest.mark.parametrize("output", [
    reply(final(), status="incomplete"), reply(call("unknown", {})),
    reply(call("framework_api", {}, "dup"), call("framework_api", {}, "dup")),
    reply({"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "no"}]}),
    reply({"type": "web_search_call"}), reply(),
])
def test_incomplete_refused_or_unadvertised_actions_never_become_tools(output):
    transport = Transport(output)
    with pytest.raises(AssistantProviderError):
        owner(transport).complete([], [tool()])
    assert len(transport.requests) == 1


def test_packet_limit_prevents_network_and_transport_failure_has_no_retry():
    transport = Transport(URLError("secret-canary"))
    with pytest.raises(AssistantProviderError, match="ai_packet_too_large"):
        owner(transport).complete([{"role": "user", "content": "x" * 131072}], [])
    assert not transport.requests
    with pytest.raises(AssistantProviderError, match="ai_transport_failed"):
        owner(transport).complete([], [])
    assert len(transport.requests) == 1


def test_responses_transport_real_mcp_fixed_source_failure_repair_delivery(tmp_path):
    anyio = pytest.importorskip("anyio")
    pytest.importorskip("mcp")
    from mcp import Client, StdioServerParameters
    from nsgablack.catalog.assistant_session_acceptance import create_teaching_project
    _, project_id = create_teaching_project(tmp_path)
    program = "\n".join([
        "import anyio",
        "from nsgablack.catalog.mcp_server import FrameworkWorkspace, serve_stdio",
        "from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry",
        "from nsgablack.catalog.assistant_novel_acceptance import execute_candidate, spec_identity",
        f"sources=ProjectSourceRegistry({{'acceptance': {str(tmp_path)!r}}})",
        "workspace=FrameworkWorkspace(sources, edit_validator=lambda p: execute_candidate(p, 'age_population_unit'), validation_identity=spec_identity())",
        "anyio.run(serve_stdio, workspace)",
    ])
    evidence = Path(__file__).resolve().parents[1] / "docs/user_guide/evidence"
    sources = [(evidence / f"ai-novel-20261123.unit-continuation-v2.age_population_unit.check{i}.py").read_text(encoding="utf-8") for i in (1, 2)]

    async def exercise():
        async with Client(StdioServerParameters(command=sys.executable, args=["-c", program]), read_timeout_seconds=100) as client:
            opened = (await client.call_tool("open_project", {"project_id": project_id})).structured_content
            session = opened["session_id"]
            definitions = (await client.list_tools()).tools
            tools = [{"type": "function", "function": {"name": t.name, "description": t.description,
                        "parameters": t.input_schema}} for t in definitions]
            path = "cases/hybrid_search/adapter/novel_ops.py"
            transport = Transport(reply(call("check_project_edit", {"session_id": session, "path": path, "source": sources[0]}, "first")),
                                  reply(call("check_project_edit", {"session_id": session, "path": path, "source": sources[1]}, "repair")),
                                  reply(final()))
            generator = owner(transport)
            messages = [{"role": "user", "content": "Offline fixed-source wire replay, not AI generation."}]
            results = []
            for _ in range(2):
                turn = complete_project_turn(generator, messages, tools)
                messages.append(turn["message"])
                for requested in turn["message"]["tool_calls"]:
                    actual = await client.call_tool(requested["function"]["name"], json.loads(requested["function"]["arguments"]))
                    assert not actual.is_error
                    results.append(actual.structured_content)
                    messages.append({"role": "tool", "tool_call_id": requested["id"], "content": json.dumps(actual.structured_content)})
            assert results[0]["validation"]["status"] == "failed"
            assert results[1]["validation"]["status"] == "passed"
            assert "Population member field age must align" in json.dumps(transport.requests[1])
            delivery = (await client.call_tool("edit_result", {"session_id": session, "path": path,
                "edit_digest": results[1]["edit_digest"]})).structured_content
            assert delivery["verification_status"] == "passed"
            assert delivery["result"]["validation"]["partial_acceptance"]["committed_steps"] == 2
            assert delivery["result"]["validation"]["failed_step_rollback"]["committed_steps"] == 1
            assert not (tmp_path / "session_design" / path).exists()
            complete_project_turn(generator, messages, [])
    anyio.run(exercise)
