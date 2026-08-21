from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from blackbase.project import build_case, case_import_context


_REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeSolver:
    def __init__(self) -> None:
        self.adapter = None
        self.resource_context = {}

    def set_adapter(self, adapter) -> None:
        self.adapter = adapter

    def set_resource_context(self, context) -> None:
        self.resource_context = dict(context or {})


@pytest.mark.parametrize(
    ("case_name", "inner_builder"),
    (
        ("supply_adjustment_nested", "_build_solver"),
        ("production_scheduling", "_build_solver_from_args"),
    ),
)
def test_standard_case_consumes_component_overrides(
    monkeypatch,
    case_name: str,
    inner_builder: str,
) -> None:
    project_root = _REPO_ROOT / "examples" / "cases" / case_name
    override_adapter = object()
    fake_solver = _FakeSolver()

    with case_import_context(project_root, case_name):
        module = importlib.import_module(f"cases.{case_name}.build_solver")

        if case_name == "supply_adjustment_nested":
            monkeypatch.setattr(
                module,
                inner_builder,
                lambda argv, *, resource_context=None: fake_solver,
            )
        else:
            monkeypatch.setattr(module, inner_builder, lambda args, **kwargs: fake_solver)

        case = build_case(
            module.build_solver,
            resource_context={"threads": 1, "namespace": f"test.{case_name}"},
            component_overrides={"adapter": override_adapter},
        )

    assert case.adapter is override_adapter
    assert case.component_override_audit["current"] is True
    assert case.component_override_audit["applied"] == ["adapter"]
    assert case.resource_binding_audit["current"] is True
