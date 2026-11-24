"""Presentation helpers for the Case's already published parameter contract.

These functions neither discover builder kwargs nor supply missing defaults.
The formal runner remains the execution authority and validates again on run.
Only explicit overrides are returned; an unchecked form field keeps the Case's
own default, including a declared ``None`` default.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
import math


_KINDS = {"int": "number", "float": "number", "bool": "checkbox", "str": "text"}


def _finite(value) -> bool:
    try:
        return type(value) in {int, float} and math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _matches(kind: str, value) -> bool:
    if kind == "float":
        return _finite(value)
    if kind == "int":
        return type(value) is int and _finite(value)
    if kind == "bool":
        return type(value) is bool
    if kind == "str":
        return type(value) is str
    return False


def _properties(schema: Mapping) -> Mapping:
    if not isinstance(schema, Mapping) or not isinstance(schema.get("properties"), Mapping):
        raise ValueError("没有有效的 Case 参数声明，不能生成参数表单。")
    return schema["properties"]


def parameter_form_plan(schema: Mapping) -> dict:
    """Describe literal controls without guessing values or changing the schema.

    ``bounds_source=trial_resource_policy`` is preserved so the UI can label
    those limits as trial limits rather than Problem constraints. Unsupported
    declarations remain visible for the advanced JSON/runner path.
    """
    fields, unsupported = [], []
    for name, rule in _properties(schema).items():
        reason = None
        if not isinstance(name, str) or not isinstance(rule, Mapping):
            reason = "参数声明格式不支持表单编辑。"
        else:
            kind = rule.get("type")
            if not isinstance(kind, str) or kind not in _KINDS:
                reason = "此参数类型需要使用高级 JSON，并由运行器核对支持范围。"
            choices = rule.get("choices")
            if "choices" in rule and (not isinstance(choices, (list, tuple)) or not choices
                    or any(not _matches(kind, choice) for choice in choices)):
                reason = "可选值声明无法安全转换为表单。"
            if kind in ("int", "float"):
                limits = [rule[key] for key in ("minimum", "maximum") if key in rule]
                if (any(not _matches(kind, value) for value in limits)
                        or (len(limits) == 2 and limits[0] > limits[1])):
                    reason = "数值范围声明无法安全转换为表单。"
        if reason:
            unsupported.append({"name": str(name), "reason": reason})
            continue
        has_default = "default" in rule
        default = deepcopy(rule.get("default"))
        default_valid = has_default and _matches(kind, default)
        if default_valid and kind in {"int", "float"}:
            default_valid = ("minimum" not in rule or default >= rule["minimum"]) and (
                "maximum" not in rule or default <= rule["maximum"])
        if default_valid and "choices" in rule:
            default_valid = any(type(default) is type(choice) and default == choice for choice in choices)
        field = {"name": name, "label": str(rule.get("title") or name), "type": kind,
                 "kind": "choice" if "choices" in rule else _KINDS[kind],
                 "description": str(rule.get("description") or ""),
                 "has_default": has_default, "default": default,
                 "default_valid": bool(default_valid),
                 "requires_override": bool(rule.get("requires_override", False)),
                 "bounds_source": rule.get("bounds_source"), "option": rule.get("option")}
        for key in ("minimum", "maximum", "choices"):
            if key in rule:
                field[key] = deepcopy(rule[key])
        fields.append(field)
    return {"fields": fields, "unsupported": unsupported, "empty": not _properties(schema),
            "parameter_mode": schema.get("parameter_mode")}


def validate_parameter_overrides(schema: Mapping, values: Mapping) -> dict:
    """Validate only user-enabled primitive overrides; never inject defaults.

    This is form feedback, not permission to execute. The runner rechecks the
    bound revision, all runtime limits, and the complete proposal on submit.
    """
    properties = _properties(schema)
    if not isinstance(values, Mapping):
        raise ValueError("参数覆盖必须是对象。")
    if any(not isinstance(name, str) or name not in properties for name in values):
        raise ValueError("参数含有 Case 未公开声明的名称。")
    required = [name for name, rule in properties.items()
                if isinstance(rule, Mapping) and rule.get("requires_override") and name not in values]
    if required:
        raise ValueError("默认规模超出本次试跑范围，请显式设置：" + "、".join(required))
    supported = {field["name"] for field in parameter_form_plan(schema)["fields"]}
    normalized = {}
    for name, value in values.items():
        if name not in supported:
            raise ValueError(f"{name} 的声明不能由当前表单校验，请使用高级 JSON 交由运行器核对。")
        rule = properties[name]
        kind = rule["type"]
        if not _matches(kind, value):
            raise ValueError(f"{name} 必须符合声明的 {kind} 类型；空值不能替代未覆盖。")
        if kind in {"int", "float"} and (("minimum" in rule and value < rule["minimum"])
                or ("maximum" in rule and value > rule["maximum"])):
            label = "本次试跑范围" if rule.get("bounds_source") == "trial_resource_policy" else "声明范围"
            raise ValueError(f"{name} 超出{label}。")
        if "choices" in rule and not any(type(value) is type(choice) and value == choice
                                         for choice in rule["choices"]):
            # A declared float also accepts int input, matching the runner's
            # numeric conversion, while bool is never treated as a number.
            if not (kind == "float" and value in rule["choices"]):
                raise ValueError(f"{name} 不在声明的可选值中。")
        normalized[name] = float(value) if kind == "float" else deepcopy(value)
    return normalized


def parse_parameter_json(text: str) -> dict:
    """Parse an advanced object, rejecting duplicate keys and nonfinite values.

    Arrays and null remain their explicit JSON values here; the Case runner
    decides whether their declarations support them. They are never flattened,
    coerced into strings, or silently replaced with defaults.
    """
    def object_pairs(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError(f"参数 JSON 包含重复名称：{name}")
            result[name] = value
        return result

    def reject_constant(_value):
        raise ValueError("参数 JSON 不能包含 NaN 或 Infinity。")

    try:
        value = json.loads(text, object_pairs_hook=object_pairs, parse_constant=reject_constant)
        if not isinstance(value, dict):
            raise ValueError("参数 JSON 必须是对象。")
        json.dumps(value, allow_nan=False)
    except (json.JSONDecodeError, TypeError, OverflowError) as exc:
        raise ValueError("参数 JSON 无效：" + str(exc)) from exc
    return value
