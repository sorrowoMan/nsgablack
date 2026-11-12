"""Case form contracts preserve explicit overrides and the runner's ownership."""
from copy import deepcopy

import pytest

from nsgablack.catalog.lab_workspace_parameters import (
    parameter_form_plan, parse_parameter_json, validate_parameter_overrides,
)


@pytest.fixture
def schema():
    return {"parameter_mode": "declared", "properties": {
        "size": {"type": "int", "default": 20, "minimum": 0, "maximum": 128,
                 "bounds_source": "trial_resource_policy", "description": "种群大小", "option": "--size"},
        "strength": {"type": "float", "default": None, "minimum": 0., "maximum": 10.},
        "enabled": {"type": "bool", "default": False},
        "method": {"type": "str", "default": "native", "choices": ["native", "local"]},
        "name": {"type": "str"},
    }}


def test_plan_preserves_declared_fields_and_trial_bound_origin(schema):
    before = deepcopy(schema)
    plan = parameter_form_plan(schema)
    assert [field["kind"] for field in plan["fields"]] == ["number", "number", "checkbox", "choice", "text"]
    assert plan["fields"][0]["label"] == "size"
    assert plan["fields"][0]["bounds_source"] == "trial_resource_policy"
    assert plan["fields"][1]["has_default"] and plan["fields"][1]["default"] is None
    assert not plan["fields"][1]["default_valid"]
    assert not plan["fields"][-1]["has_default"]
    plan["fields"][3]["choices"].append("changed")
    assert schema == before


def test_absent_and_false_are_distinct_from_explicit_null(schema):
    assert validate_parameter_overrides(schema, {}) == {}
    assert validate_parameter_overrides(schema, {"enabled": False}) == {"enabled": False}
    assert validate_parameter_overrides(schema, {"strength": 0}) == {"strength": 0.}
    with pytest.raises(ValueError, match="空值"):
        validate_parameter_overrides(schema, {"strength": None})


def test_required_trial_override_is_not_seeded_or_clamped(schema):
    schema["properties"]["size"].update(default=300, requires_override=True)
    field = parameter_form_plan(schema)["fields"][0]
    assert field["default"] == 300 and field["requires_override"]
    assert not field["default_valid"]
    with pytest.raises(ValueError, match="显式设置：size"):
        validate_parameter_overrides(schema, {})
    assert validate_parameter_overrides(schema, {"size": 30}) == {"size": 30}


@pytest.mark.parametrize("values", [{"size": True}, {"size": 1.5}, {"strength": True},
    {"strength": float("nan")}, {"strength": float("inf")}, {"strength": 10 ** 1000},
    {"enabled": 1}, {"method": "missing"}, {"name": ["a"]}, {"size": -1},
    {"size": 129}, {"runtime_threads": 4}])
def test_invalid_values_cannot_cross_form_validation(schema, values):
    with pytest.raises(ValueError):
        validate_parameter_overrides(schema, values)


def test_compound_or_unknown_schema_stays_visible_for_advanced_json(schema):
    schema["properties"].update(items={"type": "array", "default": []},
                                custom={"type": "provider_choice"})
    plan = parameter_form_plan(schema)
    assert {row["name"] for row in plan["unsupported"]} == {"items", "custom"}
    with pytest.raises(ValueError, match="高级 JSON"):
        validate_parameter_overrides(schema, {"items": []})
    assert parse_parameter_json('{"items": [1, "a"], "custom": null}') == {"items": [1, "a"], "custom": None}


@pytest.mark.parametrize("rule", [{"type": "int", "minimum": 10, "maximum": 2},
    {"type": "int", "choices": [True]}, {"type": "bool", "choices": []},
    {"type": "float", "maximum": float("inf")}, {"type": "str", "choices": "x"},
    {"type": ["str", "null"]}])
def test_invalid_schema_does_not_offer_an_invented_control(rule):
    plan = parameter_form_plan({"properties": {"value": rule}})
    assert not plan["fields"] and plan["unsupported"][0]["name"] == "value"


@pytest.mark.parametrize("text", ['[]', 'null', '{"x":1,"x":2}', '{"x":{"k":1,"k":2}}',
    '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{"x":[0,-Infinity]}'])
def test_invalid_advanced_json_never_gets_silently_normalized(text):
    with pytest.raises(ValueError):
        parse_parameter_json(text)


def test_no_parameters_is_a_real_empty_contract():
    assert parameter_form_plan({"properties": {}, "parameter_mode": "none"}) == {
        "fields": [], "unsupported": [], "empty": True, "parameter_mode": "none"}
    assert validate_parameter_overrides({"properties": {}}, {}) == {}
