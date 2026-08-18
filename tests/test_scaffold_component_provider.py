from __future__ import annotations

from nsgablack.project.scaffold.component_templates import render_component_template
from nsgablack.project.scaffold import add_case, add_component, create_project


def test_nsgablack_component_provider_owns_semantic_imports() -> None:
    plugin_source = render_component_template("trace", "plugin")
    problem_source = render_component_template("objective", "problem")

    assert "from nsgablack.plugins.base import Plugin" in plugin_source
    assert "from nsgablack.core.base import BlackBoxProblem" in problem_source
    assert "mlblack" not in plugin_source + problem_source


def test_cross_framework_case_uses_its_own_component_provider(tmp_path) -> None:
    project_root = create_project(tmp_path / "cross-framework")
    add_case("trainer", "trainer", framework="mlblack", project_root=project_root)

    component = add_component(
        "loss_problem",
        "problem",
        case_name="trainer",
        project_root=project_root,
    )

    assert component is not None
    source = component.read_text(encoding="utf-8")
    assert "mlblack.core.problem" in source
    assert "nsgablack.core.base" not in source
