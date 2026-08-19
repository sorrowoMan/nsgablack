from __future__ import annotations

from types import SimpleNamespace

import pytest

from nsgablack.project import apply_solver_component_overrides


class _Case:
    def __init__(self) -> None:
        self.adapter = None
        self.representation_pipeline = None
        self.bias_module = None

    def set_adapter(self, value) -> None:
        self.adapter = value

    def set_representation_pipeline(self, value) -> None:
        self.representation_pipeline = value

    def set_bias_module(self, value) -> None:
        self.bias_module = value


def test_safe_component_overrides_are_applied_and_audited() -> None:
    case = _Case()
    adapter = SimpleNamespace(name="adapter")
    pipeline = SimpleNamespace(name="pipeline")
    bias = SimpleNamespace(name="bias")

    apply_solver_component_overrides(
        case,
        {"adapter": adapter, "pipeline": pipeline, "bias_module": bias},
    )

    assert case.adapter is adapter
    assert case.representation_pipeline is pipeline
    assert case.bias_module is bias
    assert case.component_override_audit["current"] is True
    assert case.component_override_audit["applied"] == ["adapter", "bias_module", "pipeline"]


def test_unknown_component_override_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported post-construction"):
        apply_solver_component_overrides(_Case(), {"problem": object()})


def test_pipeline_aliases_cannot_be_ambiguous() -> None:
    with pytest.raises(ValueError, match="cannot provide both"):
        apply_solver_component_overrides(
            _Case(),
            {"pipeline": object(), "representation_pipeline": object()},
        )
