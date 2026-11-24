"""OpenAI Responses transport for the existing assistant loop and MCP tools.

This module owns one HTTP request, never a second agent or a retry loop.
Credentials come from trusted host configuration, not model/browser arguments.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from .lab_assistant import (
    AssistantProviderError, MAX_RESPONSE_BYTES, _NoRedirect, _json, assistant_messages,
)

ENDPOINT = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class OpenAIAssistantConfig:
    api_key: str = field(repr=False)
    model: str = "gpt-6.2-sol"
    max_output_tokens: int = 4096
    timeout_seconds: int = 60
    reasoning_effort: str = "low"

    def __post_init__(self):
        if (not isinstance(self.api_key, str) or not 1 <= len(self.api_key) <= 4096
                or any(ord(c) < 33 or ord(c) > 126 for c in self.api_key)):
            raise ValueError("invalid_assistant_credential")
        if (not isinstance(self.model, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", self.model)
                or ".." in self.model):
            raise ValueError("invalid_assistant_model")
        if type(self.max_output_tokens) is not int or not 256 <= self.max_output_tokens <= 16384:
            raise ValueError("invalid_assistant_token_limit")
        if type(self.timeout_seconds) is not int or not 5 <= self.timeout_seconds <= 60:
            raise ValueError("invalid_assistant_timeout")
        if self.reasoning_effort not in {"none", "minimal", "low", "medium", "high"}:
            raise ValueError("invalid_assistant_reasoning_effort")


def _input(messages):
    """Project Chat-shaped history onto Responses without losing tool pairing."""
    result = []
    for message in messages:
        role = message["role"]
        if role == "tool":
            result.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                           "output": message["content"]})
            continue
        if role not in {"system", "user", "assistant"}:
            raise ValueError("invalid_message_role")
        # Opaque reasoning is carried only in the private in-flight dialogue.
        # It never becomes prose, a source receipt, or another model's input.
        result.extend(deepcopy(message.get("_openai_reasoning", [])))
        if message.get("content"):
            result.append({"role": role, "content": message["content"]})
        for call in message.get("tool_calls") or ():
            result.append({"type": "function_call", "call_id": call["id"],
                "name": call["function"]["name"], "arguments": call["function"]["arguments"]})
    return result


def _provider_error(error):
    # Only fixed codes cross the boundary; never return arbitrary provider text.
    try:
        value = _json(error.read(8192)).get("error", {})
        code = value.get("code")
    except Exception:
        code = None
    if code == "unsupported_country_region_territory":
        return "ai_region_unsupported"
    if error.code == 401:
        return "ai_credential_rejected"
    if code in {"insufficient_quota", "billing_hard_limit_reached"}:
        return "ai_quota_exhausted"
    return "ai_rate_limited" if error.code == 429 else "ai_provider_refused"


class OpenAIAssemblyGenerator:
    """One stateless Responses call; host retains budgets and validation."""

    def __init__(self, config: OpenAIAssistantConfig, *, opener=None):
        if not isinstance(config, OpenAIAssistantConfig):
            raise TypeError("invalid_assistant_model_config")
        self.config = config
        self._opener = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())

    def generate(self, packet):
        result = self.complete(assistant_messages(packet), [])
        try:
            value = _json(result["message"]["content"])
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, TypeError, KeyError):
            raise AssistantProviderError("ai_response_invalid") from None

    def complete(self, messages, tools):
        from .lab_model_provider import _project_tool_contract
        try:
            definitions, forced = _project_tool_contract(tools)
            body = {"model": self.config.model, "input": _input(messages),
                "store": False, "include": ["reasoning.encrypted_content"],
                "max_output_tokens": self.config.max_output_tokens,
                "reasoning": {"effort": self.config.reasoning_effort},
                "parallel_tool_calls": False,
                "tool_choice": {"type": "function", "name": forced} if forced else "auto"}
            if tools:
                # Preserve existing optional arguments. Host validates the actual
                # schema; do not silently make optional parameters mandatory.
                body["tools"] = [{"type": "function", "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "parameters": deepcopy(t["function"]["parameters"]), "strict": False} for t in tools]
            else:
                body["tool_choice"] = "none"
                body["text"] = {"format": {"type": "json_object"}}
            data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(data) > 128 * 1024:
                raise AssistantProviderError("ai_packet_too_large")
            request = Request(ENDPOINT, data=data, headers={"Content-Type": "application/json",
                "Authorization": "Bearer " + self.config.api_key}, method="POST")
            # No SDK/global defaults, redirects, proxy fallback, or automatic retry.
            with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                if response.geturl() != ENDPOINT:
                    raise AssistantProviderError("ai_redirect_refused")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise AssistantProviderError("ai_response_invalid")
            value = _json(raw)
            if value.get("status") != "completed":
                raise AssistantProviderError("ai_response_incomplete")
            model = value.get("model")
            if not isinstance(model, str) or not 1 <= len(model) <= 200:
                raise ValueError()
            calls, contents, reasoning = [], [], []
            ids = set()
            for item in value["output"]:
                if item["type"] == "function_call":
                    name, call_id, arguments = item["name"], item["call_id"], item["arguments"]
                    if (name not in definitions or forced and name != forced
                            or not isinstance(call_id, str) or not 1 <= len(call_id) <= 160
                            or call_id in ids or not isinstance(arguments, str)):
                        raise ValueError()
                    ids.add(call_id)
                    calls.append({"id": call_id, "type": "function", "function": {
                        "name": name, "arguments": arguments}})
                elif item["type"] == "message":
                    if item.get("role") != "assistant":
                        raise ValueError()
                    for content in item["content"]:
                        if content["type"] != "output_text" or not isinstance(content["text"], str):
                            raise ValueError()
                        contents.append(content["text"])
                elif item["type"] == "reasoning":
                    if not isinstance(item.get("encrypted_content"), str) or not item["encrypted_content"]:
                        raise ValueError()
                    reasoning.append({"type": "reasoning", "id": item["id"], "summary": [],
                                      "encrypted_content": item["encrypted_content"]})
                else:
                    raise ValueError()
            content = "".join(contents)
            if len(calls) > 8 or not calls and not content.strip():
                raise ValueError()
            message = {"role": "assistant", "content": content}
            if calls:
                message["tool_calls"] = calls
            if reasoning:
                message["_openai_reasoning"] = reasoning
            return {"message": message, "model": model,
                    "finish_reason": "tool_calls" if calls else "stop", "protocol": "native"}
        except AssistantProviderError:
            raise
        except HTTPError as error:
            raise AssistantProviderError(_provider_error(error)) from None
        except (URLError, TimeoutError, OSError):
            raise AssistantProviderError("ai_transport_failed") from None
        except Exception:
            raise AssistantProviderError("ai_response_invalid") from None
