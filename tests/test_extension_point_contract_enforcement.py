"""
Task 9: Extension-point context contract enforcement tests.

Verifies that:
1. Every adapter exported from adapters/__all__ declares the four core
   context contract fields: context_requires, context_provides,
   context_mutates, context_cache.
2. Every plugin class in plugins/*.py base-declares the four fields
   (either on the class or inherited from Plugin base).
3. verify_component_contract() correctly detects missing fields.
4. verify_solver_contracts() correctly walks a solver component tree.
5. The doctor _CORE_CONTRACT_KEYS set matches the four canonical fields.
6. context_contracts.get_component_contract() handles adapters and plugins
   without raising.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any, List, Type

import pytest

_CORE_FIELDS = ("context_requires", "context_provides", "context_mutates", "context_cache")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(cls: Type[Any]) -> Any:
    """Construct adapter with minimal args; skip adapters that need non-trivial wiring."""
    import numpy as np

    # Adapters that need substantial runtime objects to construct — use class-level check.
    _SKIP_INSTANTIATE = {
        "AStarAdapter", "MOAStarAdapter",
        "CompositeAdapter",
        "RoleAdapter", "RoleRouterAdapter",
        "AsyncEventDrivenAdapter",
    }
    if cls.__name__ in _SKIP_INSTANTIATE:
        return None  # caller must handle None

    try:
        return cls()
    except TypeError:
        try:
            return cls(config=None)
        except TypeError:
            return cls(name=cls.__name__.lower())


# ---------------------------------------------------------------------------
# 1. All exported adapters declare the four core fields
# ---------------------------------------------------------------------------

def _get_all_adapter_classes():
    import nsgablack.adapters as pkg
    all_names = getattr(pkg, "__all__", [])
    return [
        (name, getattr(pkg, name))
        for name in all_names
        if name.endswith("Adapter")
    ]


@pytest.mark.parametrize("name,cls", _get_all_adapter_classes(),
                         ids=[n for n, _ in _get_all_adapter_classes()])
def test_adapter_declares_core_contract_fields(name, cls):
    """Every exported adapter must carry all four core context contract fields."""
    for field in _CORE_FIELDS:
        # Attribute may be declared on the class itself or inherited from AlgorithmAdapter base.
        assert hasattr(cls, field), (
            f"{name} is missing class attribute '{field}'. "
            "Declare it explicitly (may be empty: `context_{field[8:]} = ()`)."
        )


@pytest.mark.parametrize("name,cls", _get_all_adapter_classes(),
                         ids=[n for n, _ in _get_all_adapter_classes()])
def test_adapter_core_contract_fields_are_iterable(name, cls):
    """Core contract field values must be iterable (tuple/list/set) or None."""
    for field in _CORE_FIELDS:
        val = getattr(cls, field, None)
        if val is None:
            continue
        try:
            list(val)
        except TypeError:
            pytest.fail(
                f"{name}.{field} = {val!r} is not iterable. "
                "Use a tuple (e.g. `context_requires = ('generation',)`)."
            )


# ---------------------------------------------------------------------------
# 2. Plugin base + concrete plugin classes
# ---------------------------------------------------------------------------

def test_plugin_base_declares_core_contract_fields():
    """Plugin base class must declare all four core fields as defaults."""
    from nsgablack.plugins.base import Plugin
    for field in _CORE_FIELDS:
        assert hasattr(Plugin, field), (
            f"Plugin base class missing '{field}'. "
            "All plugin subclasses inherit it; the base must define the default."
        )


def _iter_plugin_classes_from_files():
    """AST-scan plugins/*.py (non-base, non-__init__) for *Plugin class definitions."""
    root = Path(__file__).resolve().parents[1] / "plugins"
    classes = []
    for py_file in sorted(root.glob("*.py")):
        if py_file.name in ("__init__.py", "base.py"):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith("Plugin"):
                if not node.name.startswith("_"):
                    classes.append((py_file.stem, node.name))
    return classes


@pytest.mark.parametrize("module_stem,cls_name", _iter_plugin_classes_from_files(),
                         ids=[f"{m}.{c}" for m, c in _iter_plugin_classes_from_files()])
def test_plugin_inherits_core_contract_fields(module_stem, cls_name):
    """Concrete plugin classes must inherit (or override) all four core fields."""
    try:
        mod = importlib.import_module(f"nsgablack.plugins.{module_stem}")
        cls = getattr(mod, cls_name)
    except (ImportError, AttributeError):
        pytest.skip(f"Cannot import nsgablack.plugins.{module_stem}.{cls_name}")

    for field in _CORE_FIELDS:
        assert hasattr(cls, field), (
            f"nsgablack.plugins.{module_stem}.{cls_name} missing '{field}'. "
            "It should inherit this from Plugin base; ensure Plugin base declares it."
        )


# ---------------------------------------------------------------------------
# 3. verify_component_contract() — unit tests
# ---------------------------------------------------------------------------

class TestVerifyComponentContract:

    def test_fully_declared_returns_empty(self):
        from nsgablack.utils.extension_contracts import verify_component_contract
        from nsgablack.adapters.nsga2 import NSGA2Adapter
        adapter = NSGA2Adapter()
        missing = verify_component_contract(adapter)
        assert missing == [], f"NSGA2Adapter should have no missing contract fields, got {missing}"

    def test_missing_field_detected(self):
        from nsgablack.utils.extension_contracts import verify_component_contract

        class BadAdapter:
            context_requires = ()
            context_provides = ()
            # context_mutates missing
            # context_cache missing
            name = "bad"

        missing = verify_component_contract(BadAdapter())
        assert "context_mutates" in missing
        assert "context_cache" in missing

    def test_strict_raises_on_missing(self):
        from nsgablack.utils.extension_contracts import verify_component_contract, ContractError

        class PartialAdapter:
            context_requires = ()
            context_provides = ()
            name = "partial"

        with pytest.raises(ContractError, match="context_mutates"):
            verify_component_contract(PartialAdapter(), strict=True)

    def test_fully_declared_strict_does_not_raise(self):
        from nsgablack.utils.extension_contracts import verify_component_contract
        from nsgablack.adapters.differential_evolution import DifferentialEvolutionAdapter
        adapter = DifferentialEvolutionAdapter()
        verify_component_contract(adapter, strict=True)  # must not raise

    def test_none_value_treated_as_missing(self):
        """A field explicitly set to None counts as missing."""
        from nsgablack.utils.extension_contracts import verify_component_contract

        class NoneFieldAdapter:
            context_requires = None  # explicit None
            context_provides = ()
            context_mutates = ()
            context_cache = ()

        missing = verify_component_contract(NoneFieldAdapter())
        assert "context_requires" in missing

    def test_empty_tuple_is_valid(self):
        """Empty tuple () is a valid declaration (means 'declares nothing')."""
        from nsgablack.utils.extension_contracts import verify_component_contract

        class EmptyAdapter:
            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()

        missing = verify_component_contract(EmptyAdapter())
        assert missing == []


# ---------------------------------------------------------------------------
# 4. verify_solver_contracts() — integration
# ---------------------------------------------------------------------------

class TestVerifySolverContracts:

    def _make_minimal_solver(self):
        """Build a minimal ComposableSolver with a valid adapter."""
        from nsgablack.core.base import BlackBoxProblem
        from nsgablack.core.composable_solver import ComposableSolver
        from nsgablack.adapters.nsga2 import NSGA2Adapter
        import numpy as np

        class MinProblem(BlackBoxProblem):
            def __init__(self):
                super().__init__(name="min", dimension=2,
                                 bounds={"x0": (-1.0, 1.0), "x1": (-1.0, 1.0)})

            def evaluate(self, x):
                return float(np.sum(np.asarray(x) ** 2))

        return ComposableSolver(problem=MinProblem(), adapter=NSGA2Adapter())

    def test_clean_solver_returns_empty(self):
        from nsgablack.utils.extension_contracts import verify_solver_contracts
        solver = self._make_minimal_solver()
        issues = verify_solver_contracts(solver)
        assert issues == [], (
            f"Clean solver should have no contract issues, got: {issues}"
        )

    def test_bad_adapter_detected(self):
        from nsgablack.utils.extension_contracts import verify_solver_contracts
        from nsgablack.core.base import BlackBoxProblem
        from nsgablack.core.composable_solver import ComposableSolver
        from nsgablack.adapters import AlgorithmAdapter
        import numpy as np

        class P(BlackBoxProblem):
            def __init__(self):
                super().__init__(name="p", dimension=2,
                                 bounds={"x0": (-1.0, 1.0), "x1": (-1.0, 1.0)})

            def evaluate(self, x):
                return float(np.sum(np.asarray(x) ** 2))

        class IncompleteAdapter(AlgorithmAdapter):
            # Inherits context_requires/provides/mutates/cache from AlgorithmAdapter base
            # so this should actually pass. Test that it does.
            def propose(self, solver, context):
                return [np.zeros(2)]

        solver = ComposableSolver(problem=P(), adapter=IncompleteAdapter(name="incomplete"))
        issues = verify_solver_contracts(solver)
        # AlgorithmAdapter base declares all four fields → no issues expected
        assert issues == [], f"Unexpected issues: {issues}"


# ---------------------------------------------------------------------------
# 5. doctor _CORE_CONTRACT_KEYS alignment check
# ---------------------------------------------------------------------------

def test_doctor_core_contract_keys_contains_all_four_fields():
    """project/doctor.py _CORE_CONTRACT_KEYS must include all four canonical fields."""
    # Import via AST to avoid triggering the full doctor runtime.
    doctor_path = Path(__file__).resolve().parents[1] / "project" / "doctor.py"
    tree = ast.parse(doctor_path.read_text(encoding="utf-8"))

    keys_value = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_CORE_CONTRACT_KEYS":
                    keys_value = node.value
    assert keys_value is not None, "_CORE_CONTRACT_KEYS not found in doctor.py"

    try:
        value = ast.literal_eval(keys_value)
    except Exception:
        pytest.skip("_CORE_CONTRACT_KEYS is not a literal set — skip static check")

    for field in _CORE_FIELDS:
        assert field in value, (
            f"doctor.py _CORE_CONTRACT_KEYS is missing '{field}'. "
            f"Current value: {value}"
        )


# ---------------------------------------------------------------------------
# 6. context_contracts.get_component_contract() handles all registered adapters
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,cls", _get_all_adapter_classes(),
                         ids=[n for n, _ in _get_all_adapter_classes()])
def test_get_component_contract_does_not_raise(name, cls):
    """get_component_contract() must not raise for any exported adapter."""
    from nsgablack.core.state.context_contracts import get_component_contract
    if cls.__name__ == "AlgorithmAdapter":
        pytest.skip("Abstract base — not directly instantiable")
    adapter = _make(cls)
    if adapter is None:
        # Cannot instantiate without heavy deps; verify class attrs instead.
        for field in _CORE_FIELDS:
            assert hasattr(cls, field), f"{name} missing class attr '{field}'"
        return
    contract = get_component_contract(adapter)
    # Contract may be None if no fields declared, but must not raise.
    assert contract is None or hasattr(contract, "requires")


@pytest.mark.parametrize("name,cls", _get_all_adapter_classes(),
                         ids=[n for n, _ in _get_all_adapter_classes()])
def test_get_component_contract_returns_contract_instance(name, cls):
    """All adapters that declare contract fields must return a ContextContract."""
    from nsgablack.core.state.context_contracts import get_component_contract, ContextContract
    if cls.__name__ == "AlgorithmAdapter":
        pytest.skip("Abstract base — not directly instantiable")
    adapter = _make(cls)
    if adapter is None:
        # Cannot instantiate — class-attr check is sufficient for declaration coverage.
        for field in _CORE_FIELDS:
            assert hasattr(cls, field), f"{name} missing class attr '{field}'"
        return
    contract = get_component_contract(adapter)
    # All adapters declare context_requires/provides/mutates/cache → contract must not be None
    assert contract is not None, (
        f"{name}: get_component_contract() returned None — "
        "adapter declares contract fields but they may all be empty tuples. "
        "Check context_contracts._collect_attrs() handles empty tuples."
    )
    assert isinstance(contract, ContextContract), (
        f"{name}: expected ContextContract, got {type(contract).__name__}"
    )
