"""Read descriptive usage guidance from the shared CatalogEntry contract.

This is an index over declared roles and operations, not a runtime capability
grant. Reading it must never import a component or construct its Unit.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


GUIDANCE_FIELDS = ("role", "concepts", "operations", "boundaries")
WIRING_STATUS_NOTE = "配方状态仅说明片段的语法与构造签名，不代表运行或算法语义已经验收。"


def wiring_status_label(status: str) -> str:
    return {
        "guidance": "使用说明",
        "template": "需填写依赖",
        "signature-checked": "仅签名检查",
        "unverified": "尚未验证",
        "invalid": "签名不匹配",
    }.get(str(status), "尚未验证（未知状态）")


@dataclass(frozen=True)
class CatalogGuidance:
    role: str
    concepts: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()


def guidance_for(entry: object) -> CatalogGuidance:
    """Read ``contract.catalog`` without guessing behavior from class names."""
    key = str(getattr(entry, "key", "<unknown>"))
    contract = getattr(entry, "contract", {})
    if not isinstance(contract, Mapping):
        raise TypeError(f"{key}: catalog contract must be a mapping")
    declared = contract.get("catalog", {})
    if not isinstance(declared, Mapping):
        raise TypeError(f"{key}: contract.catalog must be a mapping")
    role = declared.get("role", getattr(entry, "kind", "component"))
    if not isinstance(role, str) or not role.strip():
        raise TypeError(f"{key}: contract.catalog.role must be a non-empty string")

    def strings(field: str) -> tuple[str, ...]:
        values = declared.get(field, ())
        if not isinstance(values, (tuple, list)) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise TypeError(f"{key}: contract.catalog.{field} must be a list of non-empty strings")
        return tuple(dict.fromkeys(value.strip() for value in values))

    return CatalogGuidance(
        role=role.strip(),
        concepts=strings("concepts"),
        operations=strings("operations"),
        boundaries=strings("boundaries"),
    )


def guidance_payload(entry: object) -> dict[str, str | tuple[str, ...]]:
    guidance = guidance_for(entry)
    return {field: getattr(guidance, field) for field in GUIDANCE_FIELDS}


def guidance_text(entry: object) -> str:
    guidance = guidance_for(entry)
    return " ".join((guidance.role, *guidance.concepts, *guidance.operations, *guidance.boundaries))


__all__ = ["CatalogGuidance", "GUIDANCE_FIELDS", "guidance_for", "guidance_payload",
           "wiring_status_label", "WIRING_STATUS_NOTE"]
