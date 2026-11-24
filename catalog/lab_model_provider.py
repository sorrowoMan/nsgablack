"""Server-owned model backends for the existing assembly assistant protocol.

This is an inference bridge, not model training or an additional agent loop.
Every backend returns a draft to AssistantManager's existing validation gate.
Neither a browser request nor a generated draft may configure its endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import re
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import ProxyHandler, Request, build_opener

from .curation_provider import DeepSeekConfig
from .lab_openai_provider import OpenAIAssistantConfig, OpenAIAssemblyGenerator
from .lab_assistant import (
    AssistantProviderError, DeepSeekAssemblyGenerator, MAX_RESPONSE_BYTES,
    ENDPOINT, _NoRedirect, _json, assistant_messages,
)


def _endpoint(base_url: str) -> tuple[str, bool]:
    """Return a normalized, fixed completion endpoint and its loopback status."""
    if (not isinstance(base_url, str) or not 1 <= len(base_url) <= 2048
            or any(ord(char) < 33 or ord(char) > 126 for char in base_url)
            or any(char in base_url for char in "\\%?#")):
        raise ValueError("invalid_assistant_endpoint")
    try:
        parsed = urlsplit(base_url)
        host = parsed.hostname
        if (parsed.scheme not in {"http", "https"} or not host
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or parsed.netloc.endswith(":")
                or parsed.path not in {"", "/", "/v1", "/v1/"}):
            raise ValueError()
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
            loopback = address.is_loopback
            normalized_host = f"[{address.compressed}]" if address.version == 6 else str(address)
        except ValueError:
            if (len(host) > 253 or not re.fullmatch(
                    r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host)
                    or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                           for part in host.split("."))):
                raise ValueError()
            loopback = host.lower() == "localhost"
            normalized_host = host.lower()
        if parsed.scheme == "http" and not loopback:
            raise ValueError()
        authority = normalized_host + (f":{port}" if port is not None else "")
        path = "/v1/chat/completions" if parsed.path.startswith("/v1") else "/chat/completions"
        return urlunsplit((parsed.scheme, authority, path, "", "")), loopback
    except (ValueError, UnicodeError):
        raise ValueError("invalid_assistant_endpoint") from None


@dataclass(frozen=True)
class CompatibleAssistantConfig:
    """An operator-selected chat-completion model with its own credential.

    HTTPS origins are trusted by the operator who writes the private service
    configuration. HTTP and omitted credentials are restricted to loopback.
    No environment or DeepSeek credential fallback is consulted.
    """

    base_url: str = field(repr=False)
    model: str
    api_key: str | None = field(default=None, repr=False)
    max_output_tokens: int = 4096
    timeout_seconds: int = 60
    json_mode: bool = True

    def __post_init__(self):
        _, loopback = _endpoint(self.base_url)
        if (not isinstance(self.model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", self.model)
                or ".." in self.model or "//" in self.model):
            raise ValueError("invalid_assistant_model")
        if (self.api_key is not None and (not isinstance(self.api_key, str)
                or not 1 <= len(self.api_key) <= 4096
                or any(ord(char) < 33 or ord(char) > 126 for char in self.api_key))):
            raise ValueError("invalid_assistant_credential")
        if not loopback and self.api_key is None:
            raise ValueError("assistant_credential_required")
        if type(self.max_output_tokens) is not int or not 256 <= self.max_output_tokens <= 4096:
            raise ValueError("invalid_assistant_token_limit")
        if type(self.timeout_seconds) is not int or not 5 <= self.timeout_seconds <= 60:
            raise ValueError("invalid_assistant_timeout")
        if type(self.json_mode) is not bool:
            raise ValueError("invalid_assistant_json_mode")


def load_assistant_model_config(path: str | Path) -> DeepSeekConfig | CompatibleAssistantConfig | OpenAIAssistantConfig:
    """Load a private service file; absent provider preserves the old format."""
    try:
        source = Path(path)
        if not source.is_file() or source.stat().st_size > 16384:
            raise ValueError()
        value = _json(source.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError()
        provider = value.get("provider", "deepseek")
        data = {key: item for key, item in value.items() if key != "provider"}
        if provider == "deepseek":
            if set(data) - {"api_key", "model", "max_output_tokens", "timeout_seconds"}:
                raise ValueError()
            return DeepSeekConfig(**data)
        if provider == "compatible":
            if set(data) - {"base_url", "model", "api_key", "max_output_tokens", "timeout_seconds", "json_mode"}:
                raise ValueError()
            return CompatibleAssistantConfig(**data)
        if provider == "openai":
            if set(data) - {"model", "api_key", "max_output_tokens", "timeout_seconds", "reasoning_effort"}:
                raise ValueError()
            return OpenAIAssistantConfig(**data)
        raise ValueError()
    except Exception:
        raise AssistantProviderError("ai_config_invalid") from None


class CompatibleAssemblyGenerator:
    """One completion request using the live shared framework system prompt."""

    def __init__(self, config: CompatibleAssistantConfig, *, opener=None):
        if not isinstance(config, CompatibleAssistantConfig):
            raise TypeError("invalid_assistant_model_config")
        self.config = config
        self._endpoint, _ = _endpoint(config.base_url)
        self._opener = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())

    def generate(self, packet: Mapping) -> dict:
        try:
            body = {"model": self.config.model,
                    "messages": assistant_messages(packet),
                    "max_tokens": self.config.max_output_tokens, "temperature": 0.1,
                    "stream": False}
            if self.config.json_mode:
                body["response_format"] = {"type": "json_object"}
            data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(data) > 128 * 1024:
                raise AssistantProviderError("ai_packet_too_large")
            headers = {"Content-Type": "application/json"}
            if self.config.api_key is not None:
                headers["Authorization"] = "Bearer " + self.config.api_key
            request = Request(self._endpoint, data=data, headers=headers, method="POST")
            # Deliberately no retry; ambiguous failures may already be billed.
            with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                if response.geturl() != self._endpoint:
                    raise AssistantProviderError("ai_redirect_refused")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise AssistantProviderError("ai_response_invalid")
            value = _json(raw)
            choice = value["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise AssistantProviderError("ai_response_incomplete")
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise AssistantProviderError("ai_response_invalid")
            result = _json(content)
            if not isinstance(result, dict):
                raise AssistantProviderError("ai_response_invalid")
            return result
        except AssistantProviderError:
            raise
        except HTTPError:
            raise AssistantProviderError("ai_provider_refused") from None
        except (URLError, TimeoutError, OSError):
            raise AssistantProviderError("ai_transport_failed") from None
        except Exception:
            raise AssistantProviderError("ai_response_invalid") from None


def create_assistant_generator(config: DeepSeekConfig | CompatibleAssistantConfig | OpenAIAssistantConfig | str | Path, *, opener=None):
    """Select only a backend explicitly constructed from server configuration."""
    if isinstance(config, (str, Path)):
        config = load_assistant_model_config(config)
    if isinstance(config, DeepSeekConfig):
        return DeepSeekAssemblyGenerator(config, opener=opener)
    if isinstance(config, CompatibleAssistantConfig):
        return CompatibleAssemblyGenerator(config, opener=opener)
    if isinstance(config, OpenAIAssistantConfig):
        return OpenAIAssemblyGenerator(config, opener=opener)
    raise AssistantProviderError("ai_config_invalid")


_PROJECT_JSON_PROTOCOL = "nsgablack.project_turn_json/v1"


def _project_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _project_tool_contract(tools):
    definitions = {}
    for tool in tools:
        if (not isinstance(tool, dict) or tool.get("type") != "function"
                or not isinstance(tool.get("function"), dict)):
            raise ValueError("invalid_tool_definition")
        function = tool["function"]
        name = function.get("name")
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name)
                or name in definitions):
            raise ValueError("invalid_tool_definition")
        definitions[name] = function.get("parameters", {"type": "object", "properties": {},
                                                        "additionalProperties": False})
    choice = "check_project_edit" if list(definitions) == ["check_project_edit"] else None
    return definitions, choice


def _project_arguments_match(value, schema, *, depth=0):
    """Validate the schema subset used by the host's Project tools, fail closed.

    This is protocol validation, not a replacement for each tool's semantic gate.
    Unsupported validation keywords must not silently weaken a tool contract.
    """
    if depth > 32 or not isinstance(schema, dict):
        return False
    supported = {"type", "properties", "required", "additionalProperties", "items",
                 "enum", "const", "minimum", "maximum", "minLength", "maxLength",
                 "minItems", "maxItems", "description", "title", "default"}
    if set(schema) - supported:
        return False
    kind = schema.get("type")
    types = {"object": lambda: isinstance(value, dict), "array": lambda: isinstance(value, list),
             "string": lambda: isinstance(value, str), "integer": lambda: type(value) is int,
             "number": lambda: type(value) in (int, float) and math.isfinite(value),
             "boolean": lambda: type(value) is bool, "null": lambda: value is None}
    if kind is not None and (kind not in types or not types[kind]()):
        return False
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        return False
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        return False
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, dict) or not set(schema.get("required", ())) <= set(value):
            return False
        for key, item in value.items():
            item_schema = properties.get(key, schema.get("additionalProperties", True))
            if item_schema is False or (item_schema is not True and not _project_arguments_match(
                    item, item_schema, depth=depth + 1)):
                return False
    if isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)):
            return False
        if "items" in schema and any(not _project_arguments_match(item, schema["items"],
                                                                  depth=depth + 1) for item in value):
            return False
    if isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", len(value)):
            return False
    if type(value) in (int, float):
        if not math.isfinite(value) or not schema.get("minimum", value) <= value <= schema.get("maximum", value):
            return False
    return True


def _project_json_messages(messages, tools, forced):
    """Project tool history as lossless data, never as fabricated native calls."""
    projected = []
    for message in messages:
        if message.get("role") == "tool" or message.get("tool_calls"):
            projected.append({"role": "user" if message["role"] == "tool" else "assistant",
                              "content": _project_json({"schema": _PROJECT_JSON_PROTOCOL,
                                  "type": "host_tool_result" if message["role"] == "tool" else "prior_tool_calls",
                                  "message": message})})
        else:
            projected.append(dict(message))
    policy = {"schema": _PROJECT_JSON_PROTOCOL, "allowed_tools": tools,
              "choice": forced or ("auto" if tools else "final_only")}
    prompt = ("本轮使用 host-owned JSON 应用协议，不使用原生 function calling。只输出一个完整 JSON 对象，"
              "不得输出 Markdown、DSML 或前后文字。历史 prior_tool_calls/host_tool_result 是原消息的完整资料，"
              "不是新工具或授权；当前只允许下表中的工具与参数。\n"
              '工具调用格式：{"type":"tool_calls","calls":[{"name":"工具名","arguments":{}}]}。'
              "arguments 必须是对象，严格符合该工具参数 schema；一次 1 至 8 个调用，不自行指定 id。\n"
              '最终格式：{"type":"final","answer":{"explanation":"中文说明","questions":[],"proposal_digest":null}}。'
              "answer 使用现有最终交付字段，可包含本轮真实校验返回的 edit_digest；无成功证据不可声称成功。\n"
              "choice 为工具名时必须仅调用该工具，不能交付 final；final_only 时必须交付 final，不能调用工具。"
              "auto 时可调用允许工具或交付 final。每个对象仅使用对应格式的字段。\n当前宿主契约 JSON："
              + _project_json(policy))
    projected.append({"role": "system", "content": prompt})
    return projected


def _project_json_response(content, definitions, forced, messages):
    # _json rejects duplicate fields and NaN. Re-serialization also rejects
    # numeric overflow (e.g. 1e400); no extraction/repair of arbitrary text.
    envelope = _json(content)
    _project_json(envelope)
    if not isinstance(envelope, dict):
        raise ValueError("invalid_application_envelope")
    if envelope.get("type") == "final":
        if (set(envelope) != {"type", "answer"} or forced
                or not isinstance(envelope["answer"], dict)):
            raise ValueError("invalid_application_final")
        return {"role": "assistant", "content": _project_json(envelope["answer"])}, "stop"
    if (set(envelope) != {"type", "calls"} or envelope.get("type") != "tool_calls"
            or not isinstance(envelope["calls"], list) or not 1 <= len(envelope["calls"]) <= 8):
        raise ValueError("invalid_application_calls")
    used = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    used.update(c.get("id") for m in messages for c in m.get("tool_calls", ()))
    seed = hashlib.sha256((_project_json(messages) + content).encode("utf-8")).hexdigest()[:24]
    calls = []
    for index, call in enumerate(envelope["calls"]):
        if (not isinstance(call, dict) or set(call) != {"name", "arguments"}
                or not isinstance(call["name"], str) or call["name"] not in definitions
                or forced and call["name"] != forced
                or not isinstance(call["arguments"], dict)
                or not _project_arguments_match(call["arguments"], definitions[call["name"]])):
            raise ValueError("invalid_application_call")
        call_id = f"appcall_{seed}_{index}"
        while call_id in used:
            call_id += "x"
        used.add(call_id)
        calls.append({"id": call_id, "type": "function", "function": {
            "name": call["name"], "arguments": _project_json(call["arguments"])}})
    return {"role": "assistant", "content": "", "tool_calls": calls}, "tool_calls"


def complete_project_turn(generator, messages: list[dict], tools: list[dict], *, protocol="native",
                          feedback_protocol_errors=False) -> dict:
    """One real tool-capable turn using the existing private model configuration.

    The caller owns the bounded tool loop. Provider responses never execute a
    function here, and ambiguous HTTP failures are never automatically retried.
    ``protocol='json'`` is an explicit host choice, never an automatic fallback.
    It carries tools in an application envelope with strict local validation;
    model text/DSML is never interpreted as a native tool call. Existing assembly
    generation and its JSON protocol are unchanged. The host may explicitly
    request bounded protocol-error feedback for its existing turn budget;
    transport/envelope-shell failures still raise and are never retried here.
    """
    config = getattr(generator, "config", None)
    if isinstance(config, OpenAIAssistantConfig):
        if protocol != "native":
            raise AssistantProviderError("ai_project_protocol_invalid")
        return generator.complete(messages, tools)
    if isinstance(config, DeepSeekConfig):
        endpoint = ENDPOINT
    elif isinstance(config, CompatibleAssistantConfig):
        endpoint, _ = _endpoint(config.base_url)
    else:
        raise AssistantProviderError("ai_project_tools_unavailable")
    try:
        if protocol not in {"native", "json"} or type(feedback_protocol_errors) is not bool:
            raise AssistantProviderError("ai_project_protocol_invalid")
        definitions, forced = _project_tool_contract(tools)
        body = {"model": config.model, "messages": messages, "tools": tools,
                "tool_choice": "auto", "max_tokens": config.max_output_tokens,
                "temperature": 0.1, "stream": False}
        # Keep the native function-call channel separate from content JSON
        # formatting (the official non-thinking tool example uses tools only).
        # JSON Output applies to final content, not function-call arguments.
        if forced:
            # A source/test phase needs an actual named tool choice. Merely
            # hiding read tools leaves the model free to repeat obsolete calls.
            body["tool_choice"] = {"type": "function", "function": {"name": "check_project_edit"}}
        if not tools:
            # The runtime owns the final delivery phase. Do not advertise an
            # empty tools collection with tool_choice=auto to the provider.
            body.pop("tools")
            body["tool_choice"] = "none"
            body["response_format"] = {"type": "json_object"}
        if protocol == "json":
            body["messages"] = _project_json_messages(messages, tools, forced)
            body.pop("tools", None)
            body.pop("tool_choice", None)
            body["response_format"] = {"type": "json_object"}
        if isinstance(config, DeepSeekConfig):
            body["thinking"] = {"type": "disabled"}
        elif not config.json_mode:
            body.pop("response_format", None)
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(data) > 128 * 1024:
            raise AssistantProviderError("ai_packet_too_large")
        headers = {"Content-Type": "application/json"}
        if config.api_key is not None:
            headers["Authorization"] = "Bearer " + config.api_key
        request = Request(endpoint, data=data, headers=headers, method="POST")
        with generator._opener.open(request, timeout=config.timeout_seconds) as response:
            if response.geturl() != endpoint:
                raise AssistantProviderError("ai_redirect_refused")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AssistantProviderError("ai_response_invalid")
        value = _json(raw)
        if protocol == "json" and feedback_protocol_errors and value.get("model") != config.model:
            raise AssistantProviderError("ai_response_invalid")
        choice = value["choices"][0]
        if choice.get("finish_reason") not in {"stop", "tool_calls"}:
            raise AssistantProviderError("ai_response_incomplete")
        incoming = choice["message"]
        if not isinstance(incoming, dict) or incoming.get("role", "assistant") != "assistant":
            raise AssistantProviderError("ai_response_invalid")
        content = incoming.get("content")
        calls = incoming.get("tool_calls") or []
        if ((content is not None and not isinstance(content, str))
                or not isinstance(calls, list) or len(calls) > 8
                or not calls and (not content or not content.strip())):
            raise AssistantProviderError("ai_response_invalid")
        if choice["finish_reason"] == "tool_calls" and not calls:
            raise AssistantProviderError("ai_response_invalid")
        if protocol == "json":
            if calls or choice["finish_reason"] != "stop":
                raise AssistantProviderError("ai_project_protocol_invalid")
            receipt = {"schema": _PROJECT_JSON_PROTOCOL,
                "wire_request_sha256": hashlib.sha256(data).hexdigest(),
                "wire_messages_sha256": hashlib.sha256(
                    _project_json(body["messages"]).encode("utf-8")).hexdigest(),
                "history_projection": "lossless_tool_messages_as_json_data",
                "wire_content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "native_tool_calls": False, "executed": False}
            try:
                message, finish_reason = _project_json_response(content, definitions, forced, messages)
            except (ValueError, TypeError, OverflowError, RecursionError):
                if not feedback_protocol_errors:
                    raise AssistantProviderError("ai_project_protocol_invalid") from None
                original_bytes = content.encode("utf-8")
                feedback_content = original_bytes[:24 * 1024].decode("utf-8", errors="ignore")
                receipt.update(accepted=False, wire_content_bytes=len(original_bytes),
                               feedback_content_bytes=len(feedback_content.encode("utf-8")),
                               content_truncated=feedback_content != content)
                return {"message": {"role": "assistant", "content": feedback_content},
                    "model": value["model"], "finish_reason": choice["finish_reason"],
                    "protocol": protocol, "protocol_wire_content": content, "protocol_receipt": receipt,
                    "protocol_error": {"code": "ai_project_tool_protocol_invalid",
                        "message": "只接收一个完整 JSON 对象：tool_calls 的 calls 包含 name 与对象 arguments，"
                                   "或 final 的 answer 包含原有最终交付字段。不得输出 DSML、Markdown 或额外字段；"
                                   "工具与参数须符合本轮宿主 schema 和 choice。未执行任何工具。",
                        "allowed_tools": list(definitions),
                        "choice": forced or ("auto" if tools else "final_only")}}
            receipt["accepted"] = True
            return {"message": message, "model": str(value.get("model", config.model))[:200],
                    "finish_reason": finish_reason, "protocol": protocol,
                    "protocol_wire_content": content, "protocol_receipt": receipt}
        message = {"role": "assistant", "content": content or ""}
        if calls:
            message["tool_calls"] = calls
        # Some compatible models return reasoning even when thinking is not
        # requested. Preserve it for protocol continuity, never in public UI.
        if isinstance(incoming.get("reasoning_content"), str):
            message["reasoning_content"] = incoming["reasoning_content"]
        return {"message": message, "model": str(value.get("model", config.model))[:200],
                "finish_reason": choice["finish_reason"], "protocol": protocol}
    except AssistantProviderError:
        raise
    except HTTPError:
        raise AssistantProviderError("ai_provider_refused") from None
    except (URLError, TimeoutError, OSError):
        raise AssistantProviderError("ai_transport_failed") from None
    except Exception:
        raise AssistantProviderError("ai_response_invalid") from None
