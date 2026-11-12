from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from blackbase.catalog import CatalogEntry
from nsgablack.catalog import curation


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def packet(root, import_path, *, key="tool.test", owner="demo", kind="tool"):
    entry = CatalogEntry(key=key, title="Test", kind=kind, import_path=import_path,
                         metadata={"catalog_framework": owner})
    return curation.prepare_packet(entry, [entry], {owner: root})


def evidence(packet):
    return "\n".join(item["text"] for item in packet["evidence"])


def assert_real(packet, roots):
    assert len(curation._json(packet)) <= curation.MAX_PACKET_CHARS
    for item in packet["evidence"]:
        owner, relative = item["path"].split("/", 1)
        data = (roots[owner] / relative).read_bytes()
        lines = data.decode("utf-8-sig").splitlines(keepends=True)
        assert item["file_sha256"] == hashlib.sha256(data).hexdigest()
        assert item["text"] == "".join(lines[item["start_line"] - 1:item["end_line"]])


def test_example_module_uses_only_its_explicit_owner_root(tmp_path):
    source = write(tmp_path, "examples/cases/sample/cases/search/build_solver.py",
                   "raise RuntimeError('must not execute')\ndef build_solver(resource_context=None):\n    return resource_context\n")
    result = packet(tmp_path, "examples.cases.sample.cases.search.build_solver:build_solver")
    assert "def build_solver(resource_context=None)" in evidence(result)
    assert not any("未定位到该导入" in gap for gap in result["gaps"])
    assert_real(result, {"demo": tmp_path})
    source.write_text(source.read_text(encoding="utf-8") + "\n# complete file change\n", encoding="utf-8")
    assert packet(tmp_path, "examples.cases.sample.cases.search.build_solver:build_solver")["source_digest"] != result["source_digest"]
    wrong = packet(tmp_path, "other.cases.sample:build_solver")
    assert not wrong["evidence"]


def test_try_reexport_captures_real_declaration_and_optional_import_proof(tmp_path):
    write(tmp_path, "__init__.py", "try:\n    from .impl import Actual as Public\nexcept ImportError:\n    Public = None\n")
    write(tmp_path, "impl.py", "raise RuntimeError('never import')\nclass Actual:\n    def compute(self, x):\n        return x + 1\n")
    result = packet(tmp_path, "demo:Public")
    assert "class Actual:" in evidence(result)
    assert "except ImportError:" in evidence(result)
    assert not any("符号未能" in gap for gap in result["gaps"])
    assert_real(result, {"demo": tmp_path})


def test_ambiguous_try_reexports_remain_unresolved(tmp_path):
    write(tmp_path, "__init__.py", "try:\n    from .a import Actual as Public\nexcept ImportError:\n    from .b import Actual as Public\n")
    for path in ("a.py", "b.py"):
        write(tmp_path, path, "raise RuntimeError('never import')\nclass Actual:\n    def compute(self, x):\n        return x\n")
    result = packet(tmp_path, "demo:Public")
    assert any("符号未能" in gap for gap in result["gaps"])
    assert not any(item["path"].endswith(("/a.py", "/b.py")) for item in result["evidence"])


def test_explicit_singleton_namespace_is_not_constructed(tmp_path):
    write(tmp_path, "__init__.py", "raise RuntimeError('never execute')\nclass _Selectors:\n    def __init__(self):\n        raise RuntimeError('never construct')\n    def all(self, owner):\n        return owner\nsubpools = _Selectors()\n")
    result = packet(tmp_path, "demo:subpools")
    assert "class _Selectors:" in evidence(result) and "def all(" in evidence(result)
    assert any(item["text"].strip() == "subpools = _Selectors()" for item in result["evidence"])
    assert not any("符号未能" in gap for gap in result["gaps"])
    assert_real(result, {"demo": tmp_path})


@pytest.mark.parametrize("assignment", ["subpools = factory()", "subpools = _Selectors(guess())",
                                          "subpools = _Selectors()\nsubpools = factory()"])
def test_dynamic_or_multiple_singleton_assignments_are_not_guessed(tmp_path, assignment):
    write(tmp_path, "__init__.py", "class _Selectors:\n    def all(self, owner):\n        return owner\n" + assignment + "\n")
    result = packet(tmp_path, "demo:subpools")
    assert any("符号未能" in gap for gap in result["gaps"])


def test_loaded_child_module_namespace_has_source_and_loading_proof(tmp_path):
    write(tmp_path, "__init__.py", "from .context_keys import REGISTERED\n__all__ = ['context_keys']\n")
    write(tmp_path, "context_keys.py", "raise RuntimeError('never import namespace')\nREGISTERED = ('generation',)\ndef register(name):\n    return name\n")
    result = packet(tmp_path, "demo:context_keys")
    assert any(item["path"] == "demo/context_keys.py" for item in result["evidence"])
    assert "REGISTERED = ('generation',)" in evidence(result)
    assert "from .context_keys import REGISTERED" in evidence(result)
    assert not any("符号未能" in gap for gap in result["gaps"])
    assert_real(result, {"demo": tmp_path})
    write(tmp_path, "__init__.py", "__all__ = []\n")
    assert any("符号未能" in gap for gap in packet(tmp_path, "demo:context_keys")["gaps"])


def test_resolved_primary_packet_never_enters_fallback_and_docs_stay_unchanged(tmp_path, monkeypatch):
    write(tmp_path, "__init__.py", "class Toy:\n    def compute(self, x):\n        return x\ndoc_pointer = 'guide.md'\n")
    expected = packet(tmp_path, "demo:Toy")
    doc = packet(tmp_path, "demo:doc_pointer", kind="doc")
    def reject(*args, **kwargs):
        raise AssertionError("legacy successful/document primary must not change")
    monkeypatch.setattr(curation, "_fallback_declaration", reject)
    assert packet(tmp_path, "demo:Toy") == expected
    assert packet(tmp_path, "demo:doc_pointer", kind="doc") == doc


def softmax_sources(root):
    write(root, "representations/heads/probability.py", "from ...models.probability import SoftmaxProbabilityModel\nclass SoftmaxHead:\n    def decode(self, values):\n        return SoftmaxProbabilityModel(values)\n")
    write(root, "models/probability.py", "raise RuntimeError('never import model')\nfrom dataclasses import dataclass\n@dataclass(frozen=True)\nclass SoftmaxProbabilityModel:\n    def predict_proba(self, X):\n        return X\n    def predict(self, X):\n        return [self.classes_[i] for i in X]\n")
    return write(root, "problems/classification.py", "raise RuntimeError('never evaluate')\nclass SupervisedClassificationProblem:\n    def evaluate(self, model):\n        metrics = _classification_metrics(model)\n        return _build_objectives(metrics)\ndef _classification_metrics(model):\n    return {'train.f1_macro': _hidden(model)}\ndef _build_objectives(metrics):\n    return 1 - metrics['train.f1_macro']\ndef _hidden(model):\n    return 'not recursively expanded'\n")


def test_softmax_allowlist_adds_actual_consumer_helpers_and_model_without_global_expansion(tmp_path):
    source = softmax_sources(tmp_path)
    path = "mlblack.representations.heads.probability:SoftmaxHead"
    before = packet(tmp_path, path, key="mlblack.head.other", owner="mlblack")
    focused = packet(tmp_path, path, key="mlblack.head.softmax", owner="mlblack")
    text = evidence(focused)
    for token in ("def evaluate(", "def _classification_metrics(", "def _build_objectives(",
                  "class SoftmaxProbabilityModel:", "def predict("):
        assert token in text
    assert "def _hidden(" not in text
    assert "@dataclass(frozen=True)\nclass SoftmaxProbabilityModel:" in text.replace("\r\n", "\n")
    assert not any(item["path"].endswith("classification.py") for item in before["evidence"])
    assert_real(focused, {"mlblack": tmp_path})
    source.write_text(source.read_text(encoding="utf-8").replace("return 1 -", "return 2 -"), encoding="utf-8")
    assert packet(tmp_path, path, key="mlblack.head.other", owner="mlblack") == before
    assert packet(tmp_path, path, key="mlblack.head.softmax", owner="mlblack")["source_digest"] != focused["source_digest"]


def test_patchtst_allowlist_adds_only_real_case_pipeline_and_group(tmp_path):
    write(tmp_path, "__init__.py", "def preset(data):\n    return data\n")
    base = "examples/cases/temporal_neural_compare/"
    write(tmp_path, base + "cases/temporal_patchtst/build_solver.py",
          "def build_solver(config=None, *, resource_context=None, component_overrides=None):\n    return resource_context\n")
    write(tmp_path, base + "cases/temporal_patchtst/pipeline/__init__.py", "from .main import build_pipeline\n")
    write(tmp_path, base + "cases/temporal_patchtst/pipeline/main.py", "def build_pipeline(config=None):\n    return config\n")
    write(tmp_path, base + "project_config.py", "GROUPS = {'default': {'stages': ['models']}}\n")
    focused = packet(tmp_path, "mlblack:preset", owner="mlblack", key="mlblack.preset.temporal_patchtst_forecast")
    unrelated = packet(tmp_path, "mlblack:preset", owner="mlblack", key="mlblack.preset.other")
    assert "component_overrides=None" in evidence(focused)
    assert "def build_pipeline(" in evidence(focused)
    assert "from .main import build_pipeline" in evidence(focused)
    assert "GROUPS =" in evidence(focused)
    assert not any("/examples/" in item["path"] for item in unrelated["evidence"])
    assert_real(focused, {"mlblack": tmp_path})


@pytest.mark.parametrize("import_path,owner", [("nsgablack.bias:BiasModule", "nsgablack"),
                                               ("nsgablack.adapters:subpools", "nsgablack"),
                                               ("blackbase.context:context_keys", "blackbase")])
def test_live_framework_known_names_are_static_and_have_no_missing_primary(import_path, owner):
    workspace = Path(__file__).resolve().parents[1]
    root = workspace if owner == "nsgablack" else workspace.parent / owner
    if not root.is_dir():
        pytest.skip("sibling framework source is unavailable")
    result = packet(root, import_path, owner=owner)
    assert not any("符号未能" in gap or "未定位到该导入" in gap for gap in result["gaps"])
    assert_real(result, {owner: root})


@pytest.mark.parametrize("key", sorted(curation._CASE_SIGNATURE_EVIDENCE_KEYS))
def test_exact_case_signature_allowlist_adds_injection_check_without_certifying_tutorial(tmp_path, key):
    blackbase = tmp_path / "blackbase"
    demo = tmp_path / "demo"
    write(demo, "__init__.py", "class Leaf:\n    def read(self):\n        return 1\n")
    source = write(blackbase, "src/blackbase/project/runtime.py",
                   "raise RuntimeError('never import runtime')\n"
                   "def build_case(builder, *, resource_context=None, component_overrides=None):\n"
                   "    required = ('resource_context', 'component_overrides')\n"
                   "    if not all(name in builder.parameters for name in required):\n"
                   "        raise TypeError('canonical Case builder must accept keyword parameters')\n"
                   "    return builder(resource_context=resource_context, component_overrides=component_overrides)\n")
    roots = {"demo": demo, "blackbase": blackbase}
    entry = CatalogEntry(key=key, title="Test", kind="doc" if key.startswith("doc.") else "tool",
                         import_path="demo:Leaf")
    first = curation.prepare_packet(entry, [entry], roots)
    assert "canonical Case builder must accept keyword parameters" in evidence(first)
    assert "return builder(resource_context=resource_context, component_overrides=component_overrides)" in evidence(first)
    assert not first["gaps"]
    assert_real(first, roots)
    source.write_text(source.read_text(encoding="utf-8") + "\n# full runtime source revision\n", encoding="utf-8")
    assert curation.prepare_packet(entry, [entry], roots)["source_digest"] != first["source_digest"]
    unrelated = CatalogEntry(key="mlblack.preset.unlisted", title="Other", kind="tool", import_path="demo:Leaf")
    baseline = curation.prepare_packet(unrelated, [unrelated], roots)
    assert not any(item["path"].startswith("blackbase/") for item in baseline["evidence"])


def test_scaffold_config_has_required_numericizer_plan_dataclass_source_only_for_exact_key(tmp_path):
    write(tmp_path, "__init__.py", "class ScaffoldConfig:\n    def describe(self):\n        return {}\n")
    write(tmp_path, "pipeline/numericizer/default.py",
          "raise RuntimeError('never construct numericizer')\nfrom dataclasses import dataclass\n"
          "@dataclass\nclass DefaultNumericizer:\n    plan: NumericizationPlan\n"
          "    def transform(self, rows):\n        return self.plan\n")
    source = write(tmp_path, "pipeline/numericizer/plan.py",
                   "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass NumericizationPlan:\n"
                   "    schema: object\n    columns: tuple\n    target: object\n"
                   "    @classmethod\n    def from_schema(cls, schema):\n        return cls(schema, (), schema.target)\n")
    first = packet(tmp_path, "mlblack:ScaffoldConfig", owner="mlblack", key="mlblack.schema.scaffold_config")
    text = evidence(first).replace("\r\n", "\n")
    assert "@dataclass\nclass DefaultNumericizer:" in text
    assert "plan: NumericizationPlan" in text and "plan: NumericizationPlan =" not in text
    assert "def from_schema(" in text and "target: object" in text
    assert_real(first, {"mlblack": tmp_path})
    unrelated = packet(tmp_path, "mlblack:ScaffoldConfig", owner="mlblack", key="mlblack.schema.other")
    assert "DefaultNumericizer" not in evidence(unrelated)
    source.write_text(source.read_text(encoding="utf-8") + "\n# plan definition revision\n", encoding="utf-8")
    assert packet(tmp_path, "mlblack:ScaffoldConfig", owner="mlblack", key="mlblack.schema.scaffold_config")["source_digest"] != first["source_digest"]
    assert packet(tmp_path, "mlblack:ScaffoldConfig", owner="mlblack", key="mlblack.schema.other") == unrelated


@pytest.mark.parametrize("key", ["mlblack.problem.training_proxy", "mlblack.problem_bridge.ml_black_training"])
def test_training_proxy_explicit_execution_methods_are_not_hidden_by_class_preface(tmp_path, key):
    write(tmp_path, "problems/proxy.py", "raise RuntimeError('never import or train')\nclass MLBlackTrainingProxy:\n"
          + "    # declaration preface\n" * 120
          + "    def make_task(self, candidate, context):\n        return candidate\n"
            "    def run_task(self, task):\n        trainer = build_trainer(task)\n        return trainer.fit(max_steps=task.max_steps)\n"
            "    def evaluate_individual(self, candidate, context):\n        return self.run_task(self.make_task(candidate, context))\n"
            "    def evaluate_population(self, population, context):\n        return tuple(self.evaluate_individual(row, context) for row in population)\n")
    path = "mlblack.problems.proxy:MLBlackTrainingProxy"
    focused = packet(tmp_path, path, owner="mlblack", key=key)
    assert "def run_task(" in evidence(focused) and "trainer.fit(max_steps=task.max_steps)" in evidence(focused)
    assert "def evaluate_population(" in evidence(focused)
    assert "def run_task(" not in evidence(packet(tmp_path, path, owner="mlblack", key="mlblack.problem.other_proxy"))
    assert_real(focused, {"mlblack": tmp_path})


def test_interval_result_evidence_preserves_constraint_sign_and_violation_consumer(tmp_path):
    ml = tmp_path / "mlblack"
    nsga = tmp_path / "nsgablack"
    write(ml, "__init__.py", "class IntervalHead:\n    def decode(self, x):\n        return x\n")
    write(ml, "problems/supervised.py", "raise RuntimeError('never evaluate')\nclass SupervisedIntervalRegressionProblem:\n"
          "    def evaluate(self, model, state, context):\n        coverage = model.coverage\n"
          "        constraints = [self.target_coverage - coverage]\n        return constraints\n")
    write(nsga, "core/evaluation_feedback.py", "def feedback_constraint_violation(feedback):\n    return sum(max(0., g) for g in feedback.constraints)\n")
    entry = CatalogEntry(key="mlblack.head.interval", title="Interval", kind="head", import_path="mlblack:IntervalHead")
    result = curation.prepare_packet(entry, [entry], {"mlblack": ml, "nsgablack": nsga})
    assert "self.target_coverage - coverage" in evidence(result)
    assert "max(0., g)" in evidence(result)
    assert_real(result, {"mlblack": ml, "nsgablack": nsga})


def test_semantic_extension_has_registration_actual_constructor_and_formal_case_boundary(tmp_path):
    nsga, base = tmp_path / "nsgablack", tmp_path / "blackbase"
    write(nsga, "core/semantic_extension.py", "raise RuntimeError('never import extension')\n"
          "class SolverSemanticExtension:\n    name = 'semantic'\n"
          "    def project_context(self, solver, context):\n        return context\n")
    write(nsga, "core/composable_solver.py", "class ComposableSolver:\n"
          "    def __init__(self, problem, adapter=None, *, resource_context=None):\n"
          "        raise RuntimeError('never construct solver')\n")
    write(nsga, "core/blank_solver.py", "class SolverBase:\n"
          "    def register_semantic_extension(self, extension):\n"
          "        if self.running:\n            raise RuntimeError('cannot register during run')\n"
          "        self.semantic_extensions.append(extension)\n")
    write(base, "src/blackbase/project/runtime.py", "def build_case(builder, resource_context=None, component_overrides=None):\n"
          "    required = ('resource_context', 'component_overrides')\n"
          "    return builder(resource_context=resource_context, component_overrides=component_overrides)\n")
    roots = {"nsgablack": nsga, "blackbase": base}
    def prepare(key):
        entry = CatalogEntry(key=key, title="Extension", kind="tool",
                             import_path="nsgablack.core.semantic_extension:SolverSemanticExtension")
        return curation.prepare_packet(entry, [entry], roots)
    result, unrelated = prepare("tool.semantic_extension"), prepare("tool.other_extension")
    text = evidence(result)
    assert "def register_semantic_extension(" in text
    assert "def build_case(" in text and "required = ('resource_context', 'component_overrides')" in text
    constructor = next(item["text"] for item in result["evidence"] if item["path"].endswith("composable_solver.py"))
    assert "resource_context=None" in constructor and "semantic_extension" not in constructor
    assert "raise RuntimeError('never construct solver')" not in constructor
    assert "def register_semantic_extension(" not in evidence(unrelated)
    assert_real(result, roots)


def test_projection_adds_actual_violation_consumers_only_for_exact_key(tmp_path):
    write(tmp_path, "core/state/pool_views.py", "class ObjectiveProjection:\n"
          "    def apply(self, feedback):\n        return copy_feedback(objectives=[1.], violations=feedback.violations)\n")
    consumer = write(tmp_path, "core/evaluation_acceptance.py", "raise RuntimeError('never evaluate')\n"
          "class FeasibleEvaluationAcceptance:\n    def select(self, candidates, feedback, context):\n"
          "        return [i for i, v in enumerate(feedback.raw_violations) if v <= self.constraint_tolerance]\n")
    write(tmp_path, "utils/performance/fast_non_dominated_sort.py", "class FastNonDominatedSort:\n"
          "    @staticmethod\n    def sort(objectives, constraint_violations):\n"
          "        return constraint_violations <= FEASIBILITY_THRESHOLD\n")
    path = "nsgablack.core.state.pool_views:ObjectiveProjection"
    result = packet(tmp_path, path, owner="nsgablack", key="tool.objective_projection")
    unrelated = packet(tmp_path, path, owner="nsgablack", key="tool.other_projection")
    assert "violations=feedback.violations" in evidence(result)
    assert "feedback.raw_violations" in evidence(result)
    assert "@staticmethod\n    def sort(" in evidence(result).replace("\r\n", "\n")
    assert "constraint_violations <= FEASIBILITY_THRESHOLD" in evidence(result)
    assert "feedback.raw_violations" not in evidence(unrelated)
    assert_real(result, {"nsgablack": tmp_path})
    consumer.write_text(consumer.read_text(encoding="utf-8") + "\n# consumer revision\n", encoding="utf-8")
    assert packet(tmp_path, path, owner="nsgablack", key="tool.objective_projection")["source_digest"] != result["source_digest"]
    assert packet(tmp_path, path, owner="nsgablack", key="tool.other_projection") == unrelated


def test_model_representation_has_unknown_state_access_and_initializer_return_contract(tmp_path):
    ml, base = tmp_path / "mlblack", tmp_path / "blackbase"
    write(ml, "core/representation.py", "raise RuntimeError('never import model')\n"
          "class ModelRepresentation:\n    def init(self, context) -> UnknownState:\n        raise NotImplementedError\n"
          "    def decode(self, state: UnknownState):\n        raise NotImplementedError\n")
    source = write(base, "src/blackbase/types.py", "from dataclasses import dataclass\n"
          "@dataclass(frozen=True)\nclass UnknownState:\n    values: object\n    metadata: object\n"
          "    def as_array(self):\n        return self.values.copy()\n"
          "    def with_values(self, values, **metadata):\n        return UnknownState(values, {**self.metadata, **metadata})\n")
    write(ml, "integrations/nsgablack_control.py", "def _initialize_representation(representation, context):\n"
          "    state = representation.init(dict(context))\n    if not isinstance(state, UnknownState):\n"
          "        raise TypeError('ModelRepresentation.init must return UnknownState')\n    return state\n")
    roots = {"mlblack": ml, "blackbase": base}
    def prepare(key):
        entry = CatalogEntry(key=key, title="Model", kind="model",
                             import_path="mlblack.core.representation:ModelRepresentation")
        return curation.prepare_packet(entry, [entry], roots)
    result, unrelated = prepare("mlblack.core.model"), prepare("mlblack.core.other_model")
    text = evidence(result)
    for token in ("@dataclass(frozen=True)", "def as_array(", "def with_values(",
                  "if not isinstance(state, UnknownState)", "must return UnknownState"):
        assert token in text
    assert "def as_array(" not in evidence(unrelated)
    assert_real(result, roots)
    source.write_text(source.read_text(encoding="utf-8") + "\n# state contract revision\n", encoding="utf-8")
    assert prepare("mlblack.core.model")["source_digest"] != result["source_digest"]
    assert prepare("mlblack.core.other_model") == unrelated


def test_orthogonal_model_adds_exact_feature_map_methods_with_real_decorators_and_body(tmp_path):
    source = write(tmp_path, "models/linear.py", "raise RuntimeError('never import or fit model')\n"
                   "class OrthogonalFeatureMap:\n" + "    # long declaration preface\n" * 120
                   + "    @classmethod\n    def fit(cls, X, *, max_components=None):\n"
                     "        components = decompose(X)[:max_components]\n        return cls(components)\n"
                     "    @property\n    def output_dim(self):\n        return int(self.components.shape[0])\n"
                     "    def transform(self, X):\n        return (X - self.mean) @ self.components.T\n"
                     "    def unrelated(self):\n        return 'not selected'\n"
                     "class OrthogonalLinearPointModel:\n    def predict(self, X):\n"
                     "        return self.intercept + self.feature_map.transform(X) @ self.weights\n")
    path = "mlblack.models.linear:OrthogonalLinearPointModel"
    focused = packet(tmp_path, path, owner="mlblack", key="mlblack.model.orthogonal_linear_point")
    unrelated = packet(tmp_path, path, owner="mlblack", key="mlblack.model.other_linear_point")
    text = evidence(focused).replace("\r\n", "\n")
    assert "@classmethod\n    def fit(" in text
    assert "components = decompose(X)[:max_components]" in text
    assert "@property\n    def output_dim(" in text
    assert "return (X - self.mean) @ self.components.T" in text
    assert "def unrelated(" not in text and "def fit(" not in evidence(unrelated)
    assert_real(focused, {"mlblack": tmp_path})
    source.write_text(source.read_text(encoding="utf-8").replace("X - self.mean", "X - self.updated_mean"), encoding="utf-8")
    assert packet(tmp_path, path, owner="mlblack", key="mlblack.model.orthogonal_linear_point")["source_digest"] != focused["source_digest"]
