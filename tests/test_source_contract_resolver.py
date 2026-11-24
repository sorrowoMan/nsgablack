import ast

from nsgablack.project.doctor_core.contract_resolver import SourceContractResolver


def resolve(path, class_name):
    resolver = SourceContractResolver()
    tree = resolver._tree(path)
    node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    return resolver.declarations(path, node, {"context_requires", "context_provides"})


def test_diamond_uses_python_mro_not_recursive_base_merging(tmp_path):
    path = tmp_path / "component.py"
    path.write_text(
        "class Root:\n    context_requires = ('generation',)\n"
        "class Left(Root):\n    pass\n"
        "class Right(Root):\n    context_requires = ('phase',)\n"
        "class Child(Left, Right):\n    pass\n", encoding="utf-8")
    declarations = resolve(path, "Child")
    assert ast.literal_eval(declarations["context_requires"].value) == ("phase",)


def test_alias_reexport_prefers_package_over_legacy_shim_without_import(tmp_path):
    package = tmp_path / "base"
    package.mkdir()
    (package / "__init__.py").write_text("from .exports import *\n", encoding="utf-8")
    (package / "exports.py").write_text("from .contract import Parent as Exported\n__all__ = ['Exported']\n", encoding="utf-8")
    (package / "contract.py").write_text(
        "raise RuntimeError('Doctor must not execute module')\n"
        "class Parent:\n    context_requires = ('generation',)\n", encoding="utf-8")
    (tmp_path / "base.py").write_text("class Exported: pass\n", encoding="utf-8")
    child = tmp_path / "child.py"
    child.write_text("from .base import Exported as Base\nclass Child(Base): pass\n", encoding="utf-8")
    assert ast.literal_eval(resolve(child, "Child")["context_requires"].value) == ("generation",)


def test_reassigned_base_does_not_inherit_stale_declaration(tmp_path):
    path = tmp_path / "ambiguous.py"
    path.write_text(
        "class Base:\n    context_requires = ('generation',)\n"
        "Base = dynamic_factory()\nclass Child(Base): pass\n", encoding="utf-8")
    assert resolve(path, "Child") == {}


def test_inheritance_cycle_retains_local_only(tmp_path):
    path = tmp_path / "cycle.py"
    path.write_text(
        "class A(B):\n    context_requires = ('phase',)\n"
        "class B(A):\n    context_provides = ('generation',)\n", encoding="utf-8")
    assert set(resolve(path, "A")) == {"context_requires"}


def test_inconsistent_c3_does_not_invent_contract(tmp_path):
    path = tmp_path / "mro.py"
    path.write_text(
        "class X:\n    context_requires = ('phase',)\nclass Y: pass\n"
        "class A(X, Y): pass\nclass B(Y, X): pass\nclass Child(A, B): pass\n", encoding="utf-8")
    assert resolve(path, "Child") == {}


def test_doctor_l2_accepts_inherited_partition_restore_and_rejects_shadowing(tmp_path):
    from nsgablack.project import run_project_doctor
    folder = tmp_path / "adapters"
    folder.mkdir()
    path = folder / "inherited.py"
    source = (
        "class ParentAdapter:\n"
        "    state_recovery_level = 'L2'\n"
        "    population_state_mode = 'partitioned'\n"
        "    context_requires = context_provides = context_mutates = context_cache = ()\n"
        "    context_notes = 'source-only inheritance test'\n"
        "    def get_state(self): return {}\n"
        "    def set_state(self, state): pass\n"
        "    def get_population_partitions(self): return ()\n"
        "    def set_population_partitions(self, values): return True\n"
        "class ChildAdapter(ParentAdapter):\n"
        "    def get_state(self): return super().get_state()\n"
    )
    path.write_text(source, encoding="utf-8")
    report = run_project_doctor(tmp_path, strict=True)
    assert not any(d.code.startswith("l2-population-authority") or d.code == "state-roundtrip-asymmetric"
                   for d in report.diagnostics)
    path.write_text(source + "    set_population_partitions = None\n", encoding="utf-8")
    report = run_project_doctor(tmp_path, strict=True)
    assert any(d.code == "l2-population-authority-incomplete" for d in report.diagnostics)
    without_context = source.replace(
        "    context_requires = context_provides = context_mutates = context_cache = ()\n", ""
    ).replace("    context_notes = 'source-only inheritance test'\n", "")
    path.write_text(without_context, encoding="utf-8")
    report = run_project_doctor(tmp_path, strict=True)
    assert any(d.code == "class-contract-missing" for d in report.diagnostics)
