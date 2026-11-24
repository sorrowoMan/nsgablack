import json
import re
from pathlib import Path
import pytest
from blackbase.project import load_case_builder, build_case, run_case
from nsgablack.project.scaffold import create_project, add_case
from nsgablack.project.starter import build_starter_solver


def test_generated_starter_builds_runs_and_exports(tmp_path):
    root = create_project(tmp_path / "starter")
    add_case("search", "solver", project_root=root)
    solver = build_case(load_case_builder(root, "search"), resource_context={"threads": 1, "workers": 1})
    result = run_case(solver)
    assert solver.run_progress_steps == 2
    assert solver.evaluation_count > 0
    assert result is not None


@pytest.mark.parametrize("filename,class_name", [("09_custom_adapter.md", "MyAdapter"), ("11_custom_plugin_hooks.md", "TraceAuditPlugin")])
def test_documented_component_runs_verbatim(filename, class_name):
    root = Path(__file__).resolve().parents[1]
    content = (root / "docs/standard_scaffold_tutorial" / filename).read_text(encoding="utf-8")
    snippet = next(s for s in re.findall(r"```python\s*\n(.*?)```", content, re.S) if f"class {class_name}" in s)
    scope = {"__name__": "tutorial_probe"}
    exec(compile(snippet, filename, "exec"), scope)
    component = scope[class_name]()
    solver = build_starter_solver(max_steps=2)
    if class_name == "MyAdapter":
        solver.set_adapter(component)
        state = json.loads(json.dumps(component.get_state()))
        component.set_state(state)
    else:
        solver.add_plugin(component)
    solver.export_case_result(solver.run())
    assert solver.run_progress_steps == 2
