"""Server-owned model backends for the existing assembly assistant protocol.

This is an inference bridge, not model training or an additional agent loop.
Every backend returns a draft to AssistantManager's existing validation gate.
Neither a browser request nor a generated draft may configure its endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import json
from pathlib import Path
import re
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import ProxyHandler, Request, build_opener

from .curation_provider import DeepSeekConfig
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


def load_assistant_model_config(path: str | Path) -> DeepSeekConfig | CompatibleAssistantConfig:
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


def create_assistant_generator(config: DeepSeekConfig | CompatibleAssistantConfig | str | Path, *, opener=None):
    """Select only a backend explicitly constructed from server configuration."""
    if isinstance(config, (str, Path)):
        config = load_assistant_model_config(config)
    if isinstance(config, DeepSeekConfig):
        return DeepSeekAssemblyGenerator(config, opener=opener)
    if isinstance(config, CompatibleAssistantConfig):
        return CompatibleAssemblyGenerator(config, opener=opener)
    raise AssistantProviderError("ai_config_invalid")


def complete_project_turn(generator, messages: list[dict], tools: list[dict]) -> dict:
    """One real tool-capable turn using the existing private model configuration.

    The caller owns the bounded tool loop. Provider responses never execute a
    function here, and ambiguous HTTP failures are never automatically retried.
    Existing assembly generation and its JSON protocol are unchanged.
    """
    config = getattr(generator, "config", None)
    if isinstance(config, DeepSeekConfig):
        endpoint = ENDPOINT
    elif isinstance(config, CompatibleAssistantConfig):
        endpoint, _ = _endpoint(config.base_url)
    else:
        raise AssistantProviderError("ai_project_tools_unavailable")
    try:
        body = {"model": config.model, "messages": messages, "tools": tools,
                "tool_choice": "auto", "max_tokens": config.max_output_tokens,
                "temperature": 0.1, "stream": False,
                "response_format": {"type": "json_object"}}
        if isinstance(config, DeepSeekConfig):
            body["thinking"] = {"type": "disabled"}
        elif not config.json_mode:
            body.pop("response_format")
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
        message = {"role": "assistant", "content": content or ""}
        if calls:
            message["tool_calls"] = calls
        # Some compatible models return reasoning even when thinking is not
        # requested. Preserve it for protocol continuity, never in public UI.
        if isinstance(incoming.get("reasoning_content"), str):
            message["reasoning_content"] = incoming["reasoning_content"]
        return {"message": message, "model": str(value.get("model", config.model))[:200],
                "finish_reason": choice["finish_reason"]}
    except AssistantProviderError:
        raise
    except HTTPError:
        raise AssistantProviderError("ai_provider_refused") from None
    except (URLError, TimeoutError, OSError):
        raise AssistantProviderError("ai_transport_failed") from None
    except Exception:
        raise AssistantProviderError("ai_response_invalid") from None
