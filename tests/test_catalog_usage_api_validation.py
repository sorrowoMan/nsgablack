"""Static API checks use source text, including deliberately unimportable modules."""
from pathlib import Path
import pytest

from nsgablack.catalog.usage_api_validation import UsageApiValidator, inspect_usage_api


@pytest.fixture
def roots(tmp_path):
    package = tmp_path / "mlblack"
    core = package / "core"
    core.mkdir(parents=True)
    (package / "__init__.py").write_text("raise RuntimeError('must never execute')\nfrom .core import ArtifactBundle\n", encoding="utf-8")
    (core / "__init__.py").write_text("from .artifacts import ArtifactBundle, TrainerStateArtifact, ModelArtifact, NeuralGraphArtifact\n", encoding="utf-8")
    (core / "artifacts.py").write_text('''from dataclasses import dataclass, field
from typing import ClassVar
raise RuntimeError("source only; importing this module is forbidden")

@dataclass(frozen=True)
class TrainerStateArtifact:
    payload: dict
    signature: str = ""

@dataclass(frozen=True)
class ModelArtifact:
    name: str
    model: object
    def describe(self, *, include_model=False):
        return {}

@dataclass(frozen=True)
class NeuralGraphArtifact(ModelArtifact):
    graph_spec: dict = field(default_factory=dict)

@dataclass(frozen=True)
class ArtifactBundle:
    model_artifact: ModelArtifact | None = None
    trainer_state: TrainerStateArtifact | None = None
    cache: ClassVar[dict] = {}
    internal: dict = field(init=False, default_factory=dict)
    def describe(self):
        return {}
    def save(self, path):
        return path
    @classmethod
    def empty(cls) -> "ArtifactBundle":
        return cls()

class OpenClass:
    def __init__(self, value, **kwargs):
        self.callback = kwargs.get("callback")
    def __getattr__(self, name):
        return lambda **kwargs: None

class PlainBase:
    runtime_attribute: object

@dataclass
class ChildData(PlainBase):
    value: int

class Explicit:
    def __init__(self, value, *, key):
        self.value = value
    def describe(self, *, detail=False):
        return {}
''', encoding="utf-8")
    return {"mlblack": package}


def codes(report):
    return [item["code"] for item in report["issues"]]


def test_actual_trainer_state_wrong_keywords_are_proven_without_importing(roots):
    result = inspect_usage_api('''from mlblack.core import TrainerStateArtifact
def build(state):
    return TrainerStateArtifact(name="run", model=state)
''', source_roots=roots)
    assert not result["ok"]
    assert codes(result).count("usage-api-unknown-keyword") == 2
    assert "usage-api-missing-required" in codes(result)
    assert all(item["source_path"] == "mlblack/core/artifacts.py" for item in result["issues"])


def test_bundle_describe_rejects_model_artifact_keyword_on_wrong_owner(roots):
    result = inspect_usage_api('''from mlblack.core.artifacts import ArtifactBundle, ModelArtifact
model = ModelArtifact(name="run", model=None)
model.describe(include_model=True)
bundle = ArtifactBundle(model_artifact=model)
bundle.describe(include_model=True)
''', source_roots=roots)
    assert codes(result) == ["usage-api-unknown-keyword"]
    assert result["issues"][0]["target"].endswith("ArtifactBundle.describe")


def test_reexport_alias_inherited_dataclass_fields_and_methods_are_bound(roots):
    result = inspect_usage_api('''from mlblack.core import NeuralGraphArtifact as Graph
def package(model):
    item = Graph(name="test", model=model, graph_spec={})
    return item.describe(include_model=False)
''', source_roots=roots)
    assert result["ok"]
    assert len(result["checked_calls"]) == 2
    assert not result["unknown_calls"]


def test_module_style_import_resolves_symbols_from_trusted_source(roots):
    result = inspect_usage_api('''import mlblack.core.artifacts as artifacts
item = artifacts.TrainerStateArtifact({})
''', source_roots=roots)
    assert result["ok"] and len(result["checked_calls"]) == 1


def test_plain_dotted_import_resolves_submodule_members(roots):
    result = inspect_usage_api('''import mlblack.core.artifacts
item = mlblack.core.artifacts.ArtifactBundle()
item.describe(include_model=True)
''', source_roots=roots)
    assert "usage-api-unknown-keyword" in codes(result)


def test_missing_required_and_actual_nonexistent_method_block(roots):
    result = inspect_usage_api('''from mlblack.core import TrainerStateArtifact, ArtifactBundle
state = TrainerStateArtifact()
bundle = ArtifactBundle()
bundle.method_that_does_not_exist()
''', source_roots=roots)
    assert "usage-api-missing-required" in codes(result)
    assert "usage-api-method-missing" in codes(result)


def test_local_classes_callbacks_numpy_and_unknown_kwargs_are_not_false_errors(roots):
    result = inspect_usage_api('''import numpy as np
from mlblack.core import TrainerStateArtifact
class MyObject:
    def describe(self, **kwargs):
        return kwargs
def apply(callback, values):
    return callback(values, custom=True)
local = MyObject()
local.describe(anything=True)
array = np.asarray([1, 2])
state = TrainerStateArtifact(**payload)
''', source_roots=roots)
    assert result["ok"] and not result["complete"]
    assert result["unknown_calls"]
    assert any(item["reason"] == "dynamic_argument_binding" for item in result["unknown_calls"])


def test_local_factory_keeps_known_return_type(roots):
    result = inspect_usage_api('''from mlblack.core import ArtifactBundle
def build():
    return ArtifactBundle()
item = build()
item.describe(include_model=True)
''', source_roots=roots)
    assert "usage-api-unknown-keyword" in codes(result)
    assert result["unknown_calls"][0]["reason"] == "local_callable"


def test_classmethod_return_type_and_bound_self_are_inferred(roots):
    result = inspect_usage_api('''from mlblack.core import ArtifactBundle
item = ArtifactBundle.empty()
item.describe(include_model=True)
''', source_roots=roots)
    assert codes(result) == ["usage-api-unknown-keyword"]


def test_dynamic_receiver_does_not_produce_missing_method_false_positive(roots):
    result = inspect_usage_api('''from mlblack.core.artifacts import OpenClass
item = OpenClass(1, callback=None, custom=True)
item.dynamically_provided_method(option=1)
''', source_roots=roots)
    assert result["ok"] and result["unknown_calls"]


def test_dataclass_non_init_and_class_variables_are_not_constructor_keywords(roots):
    result = inspect_usage_api('''from mlblack.core import ArtifactBundle
ArtifactBundle(internal={}, cache={})
''', source_roots=roots)
    assert codes(result).count("usage-api-unknown-keyword") == 2


def test_conditional_and_comprehension_shadowing_stays_unknown(roots):
    result = inspect_usage_api('''from mlblack.core import ArtifactBundle
item = ArtifactBundle()
if choose_other:
    item = custom_factory()
item.describe(include_model=True)
items = [item.describe(include_model=True) for item in unknown_values]
''', source_roots=roots)
    assert result["ok"] and result["unknown_calls"]


def test_case_gate_only_applies_to_claimed_module_level_case_entry(roots):
    code = "def build_solver(**kwargs):\n    return object()\n"
    leaf = inspect_usage_api(code, source_roots=roots, placement="独立组件调用函数")
    assert leaf["ok"]
    case = inspect_usage_api(code, source_roots=roots, placement="正式 Case 的 cases/search/build_solver.py")
    assert {"case-build-missing-resource-context", "case-build-missing-component-overrides"} <= set(codes(case))
    nested = inspect_usage_api("def wrapper():\n    def build_solver():\n        pass\n", source_roots=roots, placement="build_solver.py")
    assert nested["ok"]


def test_case_gate_accepts_explicit_keyword_parameters(roots):
    result = inspect_usage_api("def build_solver(config=None, *, resource_context=None, component_overrides=None):\n    return object()\n",
        source_roots=roots, placement="build_solver.py")
    assert result["ok"]


def test_reusable_validator_has_independent_snippet_state(roots):
    validator = UsageApiValidator(roots)
    first = validator.inspect("from mlblack.core import ArtifactBundle\nitem=ArtifactBundle()\n")
    second = validator.inspect("item.describe(include_model=True)\n")
    assert first["ok"] and second["ok"]
    assert not second["checked_calls"] and second["unknown_calls"]


def test_non_dataclass_parent_annotations_are_not_constructor_fields(roots):
    result = inspect_usage_api("from mlblack.core.artifacts import ChildData\nitem=ChildData(value=1)\n", source_roots=roots)
    assert result["ok"]


def test_explicit_init_and_keyword_only_method_binding(roots):
    result = inspect_usage_api('''from mlblack.core.artifacts import Explicit
item=Explicit(value=1, key="id")
item.describe(detail=True)
item.describe(invented=True)
''', source_roots=roots)
    assert codes(result) == ["usage-api-unknown-keyword"]


def test_shared_source_cache_is_safe_for_concurrent_batch_checks(roots):
    from concurrent.futures import ThreadPoolExecutor
    validator = UsageApiValidator(roots)
    code = "from mlblack.core import ArtifactBundle\nitem=ArtifactBundle()\nitem.describe(include_model=True)\n"
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(validator.inspect, [code] * 12))
    assert all(codes(result) == ["usage-api-unknown-keyword"] for result in results)


def test_real_stack_artifact_error_is_detected_from_actual_source_only():
    root = Path(__file__).resolve().parents[1]
    source_roots = {name: root.parent / name for name in ("nsgablack", "blackbase", "mlblack")}
    if not (source_roots["mlblack"] / "core/artifacts.py").exists():
        pytest.skip("sibling ML source checkout is unavailable")
    result = inspect_usage_api('''from mlblack.core.artifacts import TrainerStateArtifact, ArtifactBundle
TrainerStateArtifact(name="bad", model=None)
bundle = ArtifactBundle()
bundle.describe(include_model=True)
''', source_roots=source_roots)
    assert codes(result).count("usage-api-unknown-keyword") == 3
