"""Static preparation advice respects Python scopes and never imports examples."""
import builtins
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import pytest

from nsgablack.catalog.usage_learning import assembly_location, external_names, external_preparation


def test_learning_fields_preserve_powers_keyword_unpacking_and_body_formatting():
    from nsgablack.catalog.usage_learning import documentation_fields

    fields = documentation_fields(({"path": "guide.md", "text": (
        "**先准备什么：** 目标为 `x**2`，工厂为 `build(**kwargs)`，保留 **实际布局**。\n\n"
        "**放在哪**：Case 工厂。\n"
    )},))
    assert fields["先准备什么"] == ("目标为 `x**2`，工厂为 `build(**kwargs)`，保留 **实际布局**。",)
    assert fields["放在哪"] == ("Case 工厂。",)


def test_page_and_acceptance_choose_the_same_richer_documentation_guide_independent_of_receipt_order():
    from nsgablack.catalog.usage_learning import select_documentation_guide

    text = ("**先准备什么：** 宿主提供输入。\n\n**放在哪：** Case工厂。\n\n"
            "**接入步骤：** 挂载组件。\n\n```python\nvalue = 'baseline'\n```\n\n"
            "**怎样判断接对：** 读取正式结果。\n")
    basic = {"id": "basic", "binding": "focused", "kind": "documentation", "verification": {"status": "executed"},
             "snippets": [{"path": "usage.md", "text": text}]}
    richer = {**basic, "id": "richer", "verification": {"status": "source_checked"},
              "snippets": [{"path": "usage.md", "text": text + "\n### 变体一\n改变消费位置。\n```python\nvalue = 'variant'\n```\n"}]}
    declared = {**richer, "id": "declared", "binding": "declared"}
    assert select_documentation_guide([basic, richer, declared])["id"] == "richer"
    assert select_documentation_guide([declared, richer, basic])["id"] == "richer"


def test_repository_links_become_findable_paths_without_changing_external_links_or_code():
    from nsgablack.catalog.usage_learning import source_link_text

    source = "nsgablack/docs/catalog_usage/usage.md"
    prose = "[实际工厂](../../examples/cases/demo/build_solver.py) 与 [ML](../../../mlblack/examples/demo.py#build)"
    rendered = source_link_text(prose, source)
    assert rendered == "实际工厂（`nsgablack/examples/cases/demo/build_solver.py`） 与 ML（`mlblack/examples/demo.py#build`）"
    external = "[官方说明](https://example.com/docs) `[literal](../code.py)`\n```python\nvalue = '[code](../source.py)'\n```\n"
    assert source_link_text(external, source) == external


@pytest.mark.parametrize("source,expected", [
    ("import numpy as np\nresult = np.array([1, 2])\nprint(result)", ()),
    ("def change(request, *, rng):\n    local = rng.random()\n    return request.parents[0] + local", ()),
    ("def outer(data):\n    scale = 2\n    def inner(value):\n        return value + scale + data\n    return inner", ()),
    ("def outer():\n    local = 0\n    def inner():\n        nonlocal local\n        local += 1\n        return local\n    return inner", ()),
    ("values = [row * scale for row in rows]\nresult = {key: value for key, value in pairs}", ("pairs", "rows", "scale")),
    ("class Rule:\n    factor = scale\n    def apply(self, candidate):\n        return candidate * factor", ("factor", "scale")),
    ("def use():\n    return solver.evaluate_individual(candidate, context)", ("candidate", "context", "solver")),
    ("def build(solver):\n    return solver.set_adapter(adapter)\nresult = build(control)", ("adapter", "control")),
    ("# solver is only a comment\ntext = 'problem and candidate'\nprint(__name__, __file__, text)", ()),
    ("def build(:", ()),
])
def test_external_names_distinguish_globals_from_locals_closures_and_builtins(source, expected):
    assert external_names(source) == expected


def test_analyzing_imports_and_calls_does_not_execute_them(monkeypatch, tmp_path):
    original = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "catalog_source_must_not_import":
            raise AssertionError("Component import is forbidden for advice")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    marker = tmp_path / "never-written.txt"
    source = ("from catalog_source_must_not_import import Component\n"
              f"open({str(marker)!r}, 'w').write('unsafe')\n"
              "solver.set_adapter(Component(problem))")
    assert external_names(source) == ("problem", "solver")
    preparation = "\n".join(external_preparation(source))
    assert "build_problem()" in preparation and "build_solver()" in preparation
    assert not marker.exists()


def test_preparation_explains_known_hosts_and_groups_unknown_inputs_without_inventing_values():
    source = "solver.set_adapter(adapter)\nproblem.evaluate(candidate, context)\nresult = custom_b + custom_a"
    preparation = external_preparation(source)
    text = "\n".join(preparation)
    assert "build_solver()" in text and "build_problem()" in text
    assert "当前调用传入的单个候选" in text and "回调时传入" in text
    assert "`custom_a`、`custom_b`" in preparation[-1]
    assert external_preparation("def use(solver, problem):\n    return solver, problem") == ()


@pytest.mark.parametrize("entry,expected", [
    ({"kind": "adapter"}, "adapter/"),
    ({"kind": "bias"}, "bias/"),
    ({"kind": "plugin"}, "plugins/"),
    ({"kind": "capability"}, "plugins/"),
    ({"kind": "codec"}, "pipeline/"),
    ({"kind": "data_view"}, "pipeline/"),
    ({"kind": "problem"}, "problem/"),
    ({"kind": "trainer"}, "build_trainer.py"),
    ({"kind": "tool", "role": "unit_builder"}, "UnitBinding"),
    ({"kind": "representation", "contract": {"catalog": {"role": "unit_feature"}}}, "unit.feature(spec)"),
    ({"kind": "tool", "contract": {"catalog": {"role": "orchestration"}}}, "adapter/"),
    ({"kind": "tool"}, ""),
])
def test_assembly_location_follows_declared_owner_and_role(entry, expected):
    location = assembly_location(entry)
    assert expected in location if expected else location == ""


def test_actual_unit_feature_declaration_fallback_points_to_feature_consumer():
    path = Path(__file__).resolve().parents[1] / "catalog/entries/unit_features.toml"
    entries = tomllib.loads(path.read_text(encoding="utf-8-sig"))["entry"]
    entry = next(item for item in entries if item["key"] == "tool.unit_feature")
    location = assembly_location(entry)
    assert "所属 Unit" in location and "算子/回调" in location
    assert "unit.feature(spec)" in location and "FeatureUnit.feature" in location
    assert "UnitBinding" not in location
