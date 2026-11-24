"""Permit a declared Unit dataclass parent hook without opening reflection."""
import ast
import hashlib
from pathlib import Path
from types import FunctionType

import pytest

from nsgablack.catalog.assistant_edit_acceptance import review_execution_source


def unit_guard(source):
    guard = review_execution_source
    namespace = {**guard.__globals__, "EXECUTION_ALLOWED_NAMESPACES":
                 (*guard.__globals__["EXECUTION_ALLOWED_NAMESPACES"], "nsgablack.units")}
    return FunctionType(guard.__code__, namespace, guard.__name__)(source)


def declaration(body="super().__post_init__()", *, imports=None, decorator="dataclass", base="PopulationUnit", method="__post_init__"):
    imports = imports or "from dataclasses import dataclass\nfrom nsgablack.units import PopulationUnit"
    return f"{imports}\n@{decorator}\nclass Child({base}):\n    def {method}(self):\n        {body}\n"


@pytest.mark.parametrize("imports,decorator,base", [
    (None, "dataclass", "PopulationUnit"),
    ("from dataclasses import dataclass as dc\nfrom nsgablack.units import PopulationUnit as PU", "dc()", "PU"),
    ("import dataclasses as dc\nimport nsgablack.units as unit", "dc.dataclass(slots=True)", "unit.PopulationUnit"),
])
def test_unit_dataclass_can_invoke_declared_parent_initializer(imports, decorator, base):
    unit_guard(declaration(imports=imports, decorator=decorator, base=base))


@pytest.mark.parametrize("body", [
    "super().__dict__", "super().__class__", "super().__getattribute__('age')",
    "parent = super(); parent.__post_init__()", "hook = super().__post_init__",
    "other.__post_init__()", "super(Child, self).__post_init__()",
    "super().__post_init__(self)", "super().__post_init__(age=0)",
    "def nested():\n            super().__post_init__()",
])
def test_unit_parent_hook_permission_is_not_private_attribute_access(body):
    with pytest.raises(ValueError, match="dev_execution_attribute_review_failed"):
        unit_guard(declaration(body))


@pytest.mark.parametrize("source", [
    declaration(method="other"),
    declaration().replace("@dataclass\n", ""),
    declaration(base="object"),
    declaration(base="PopulationUnit, object"),
    declaration(imports="from dataclasses import dataclass\nfrom nsgablack.adapters import NSGA2Adapter", base="NSGA2Adapter"),
    declaration().replace("@dataclass", "def dataclass(cls): return cls\n@dataclass"),
    declaration().replace("@dataclass", "dataclass = lambda cls: cls\n@dataclass"),
    declaration().replace("@dataclass", "PopulationUnit = object\n@dataclass"),
    declaration().replace("@dataclass", "super = lambda: None\n@dataclass"),
    declaration().replace("@dataclass", "@wrapper\n@dataclass"),
    declaration().replace("def __post_init__(self):", "def __post_init__(self, super):"),
    declaration().replace("@dataclass", "from typing import Any as PopulationUnit\n@dataclass"),
    declaration().replace("class Child(PopulationUnit)", "class Parent(PopulationUnit):\n    pass\n\n@dataclass\nclass Child(Parent)"),
])
def test_unknown_or_shadowed_parent_declarations_remain_rejected(source):
    with pytest.raises(ValueError, match="dev_execution_attribute_review_failed"):
        unit_guard(source)


@pytest.mark.parametrize("body", [
    "try:\n            pass\n        except ValueError as super:\n            super().__post_init__()",
    "match value:\n            case super:\n                super().__post_init__()",
    "match value:\n            case [*super]:\n                super().__post_init__()",
    "match value:\n            case {**super}:\n                super().__post_init__()",
])
def test_parent_hook_rejects_exception_and_pattern_bound_super(body):
    with pytest.raises(ValueError, match="dev_execution_attribute_review_failed: __post_init__"):
        unit_guard(declaration(body))


@pytest.mark.parametrize("name", ["super", "dc", "PU"])
@pytest.mark.parametrize("binding", [
    "try:\n    pass\nexcept ValueError as {name}:\n    pass",
    "match value:\n    case {name}:\n        pass",
    "match value:\n    case [*{name}]:\n        pass",
    "match value:\n    case {{**{name}}}:\n        pass",
    pytest.param("class Other[{name}]:\n    pass", marks=pytest.mark.skipif(not hasattr(ast, "TypeVar"), reason="requires type-parameter AST")),
    pytest.param("class Other[*{name}]:\n    pass", marks=pytest.mark.skipif(not hasattr(ast, "TypeVarTuple"), reason="requires type-parameter AST")),
    pytest.param("class Other[**{name}]:\n    pass", marks=pytest.mark.skipif(not hasattr(ast, "ParamSpec"), reason="requires type-parameter AST")),
])
def test_string_binders_do_not_launder_unit_or_decorator_imports(name, binding):
    source = declaration(imports="from dataclasses import dataclass as dc\nfrom nsgablack.units import PopulationUnit as PU",
                         decorator="dc", base="PU")
    source = source.replace("@dc", binding.format(name=name) + "\n@dc")
    with pytest.raises(ValueError, match="dev_execution_attribute_review_failed: __post_init__"):
        unit_guard(source)


@pytest.mark.skipif(not hasattr(ast, "TypeVar"), reason="requires type-parameter AST")
@pytest.mark.parametrize("parameter", ["super", "*super", "**super"])
def test_method_type_parameters_cannot_shadow_builtin_super(parameter):
    source = declaration().replace("def __post_init__(self)", f"def __post_init__[{parameter}](self)")
    with pytest.raises(ValueError, match="dev_execution_attribute_review_failed: __post_init__"):
        unit_guard(source)


def test_original_model_bytes_only_change_the_review_outcome():
    root = Path(__file__).resolve().parents[1]
    evidence = root / "docs/user_guide/evidence"
    source = (evidence / "ai-novel-20261123.unit-continuation-v2.age_population_unit.check2.py").read_bytes()
    assert hashlib.sha256(source).hexdigest() == "94d4d68c6bf6871fc1cbb8e406a9d7161a17a4a5752b33a93f4bf239908281a7"
    before = evidence / "ai-novel-20261123.unit-continuation-v2.runtime/catalog/assistant_edit_acceptance.py"
    if not before.is_file():
        before = evidence / "ai-novel-20261123.unit-continuation-v1.runtime/catalog/assistant_edit_acceptance.py"
    old_tree = ast.parse(before.read_bytes())
    original = next(node for node in old_tree.body if isinstance(node, ast.FunctionDef) and node.name == "review_execution_source")
    namespace = {**review_execution_source.__globals__, "EXECUTION_ALLOWED_NAMESPACES":
                 (*review_execution_source.__globals__["EXECUTION_ALLOWED_NAMESPACES"], "nsgablack.units")}
    exec(compile(ast.Module(body=[original], type_ignores=[]), str(before), "exec"), namespace)
    with pytest.raises(ValueError, match="dev_execution_attribute_review_failed: __post_init__"):
        namespace["review_execution_source"](source.decode("utf-8"))
    unit_guard(source.decode("utf-8"))
