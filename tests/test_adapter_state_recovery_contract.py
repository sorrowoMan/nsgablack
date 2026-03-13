from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pytest


_ALLOWED_LEVELS = {"L0", "L1", "L2"}

# Minimal synthetic population used for L2 roundtrip tests.
_POP = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=float)
_OBJ = np.array([[0.1, 0.9], [0.5, 0.5], [0.9, 0.1]], dtype=float)
_VIO = np.array([0.0, 0.0, 0.0], dtype=float)


# ---------------------------------------------------------------------------
# AST helpers (static analysis)
# ---------------------------------------------------------------------------

def _iter_adapter_classes() -> list[tuple[Path, ast.ClassDef]]:
    out: list[tuple[Path, ast.ClassDef]] = []
    root = Path(__file__).resolve().parents[1] / "adapters"
    for py_file in sorted(root.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith("Adapter"):
                out.append((py_file, node))
    return out


def _class_attrs(node: ast.ClassDef) -> dict[str, ast.expr]:
    attrs: dict[str, ast.expr] = {}
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    attrs[target.id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            attrs[stmt.target.id] = stmt.value
    return attrs


def _literal_str(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return str(expr.value)
    return None


def _class_methods(node: ast.ClassDef) -> set[str]:
    return {
        stmt.name
        for stmt in node.body
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


# ---------------------------------------------------------------------------
# Static (AST) contract tests
# ---------------------------------------------------------------------------

def test_stateful_adapters_declare_recovery_level_and_roundtrip_methods():
    """Any adapter that defines get_state/set_state must declare state_recovery_level."""
    for path, class_node in _iter_adapter_classes():
        methods = _class_methods(class_node)
        has_get = "get_state" in methods
        has_set = "set_state" in methods
        if not (has_get or has_set):
            continue
        assert has_get and has_set, f"{path}:{class_node.name} must define both get_state/set_state"

        attrs = _class_attrs(class_node)
        assert "state_recovery_level" in attrs, f"{path}:{class_node.name} missing state_recovery_level"
        level = _literal_str(attrs["state_recovery_level"])
        assert level is not None, f"{path}:{class_node.name} state_recovery_level must be a string literal"
        assert level in _ALLOWED_LEVELS, f"{path}:{class_node.name} invalid state_recovery_level={level!r}"


def test_non_l0_stateful_adapters_declare_recovery_notes():
    """Non-L0 adapters must include state_recovery_notes documentation."""
    for path, class_node in _iter_adapter_classes():
        attrs = _class_attrs(class_node)
        level_expr = attrs.get("state_recovery_level")
        if level_expr is None:
            continue
        level = _literal_str(level_expr)
        if level is None or level == "L0":
            continue
        notes_expr = attrs.get("state_recovery_notes")
        notes = _literal_str(notes_expr) if notes_expr is not None else None
        assert notes, f"{path}:{class_node.name} with {level} should declare non-empty state_recovery_notes"


def test_l2_adapters_define_population_methods():
    """L2 adapters must define both get_population and set_population (own or inherited).

    This static check covers only *own* method definitions. If a class inherits these
    methods from a parent (e.g. NSGA3Adapter from NSGA2Adapter), it is still valid.
    The runtime test below covers the full MRO.
    """
    for path, class_node in _iter_adapter_classes():
        attrs = _class_attrs(class_node)
        level_expr = attrs.get("state_recovery_level")
        if level_expr is None:
            continue
        level = _literal_str(level_expr)
        if level != "L2":
            continue
        methods = _class_methods(class_node)
        # Classes that inherit population methods from L2 parent are fine.
        # We flag only if the class re-declares state_recovery_level="L2" without
        # providing any population-management methods AND has no L2 parent.
        has_own_pop = "get_population" in methods or "set_population" in methods
        # If the class declares its own get_state (i.e. is a root L2), it MUST also
        # declare population methods in-tree. Subclasses that inherit are checked at runtime.
        has_own_state = "get_state" in methods
        if has_own_state and not has_own_pop:
            assert False, (
                f"{path}:{class_node.name} declares state_recovery_level='L2' and owns "
                f"get_state() but does not define get_population() / set_population(). "
                "A root L2 adapter must provide both pairs."
            )


def test_adapters_level_values_are_valid():
    """All declared state_recovery_level values must be in the allowed set."""
    for path, class_node in _iter_adapter_classes():
        attrs = _class_attrs(class_node)
        level_expr = attrs.get("state_recovery_level")
        if level_expr is None:
            continue
        level = _literal_str(level_expr)
        if level is None:
            continue  # non-string literal, caught by other tests
        assert level in _ALLOWED_LEVELS, (
            f"{path}:{class_node.name} state_recovery_level={level!r} not in {_ALLOWED_LEVELS}"
        )


# ---------------------------------------------------------------------------
# Runtime (import + instantiate) contract tests
# ---------------------------------------------------------------------------

def _make_adapter(cls):
    """Construct adapter with minimal / no args."""
    try:
        return cls()
    except TypeError:
        try:
            return cls(config=None)
        except TypeError:
            return cls(name=cls.__name__.lower())


_L2_ADAPTERS = [
    ("nsgablack.adapters.nsga2", "NSGA2Adapter"),
    ("nsgablack.adapters.nsga3", "NSGA3Adapter"),
    ("nsgablack.adapters.spea2", "SPEA2Adapter"),
    ("nsgablack.adapters.differential_evolution", "DifferentialEvolutionAdapter"),
    ("nsgablack.adapters.moead", "MOEADAdapter"),
]


@pytest.mark.parametrize("module,cls_name", _L2_ADAPTERS, ids=[c for _, c in _L2_ADAPTERS])
def test_l2_get_population_returns_triple_before_init(module, cls_name):
    """Before any population is loaded, get_population() returns (ndarray, ndarray, ndarray)."""
    import importlib
    cls = getattr(importlib.import_module(module), cls_name)
    adapter = _make_adapter(cls)
    result = adapter.get_population()
    assert isinstance(result, tuple) and len(result) == 3
    for i, arr in enumerate(result):
        assert isinstance(arr, np.ndarray), (
            f"{cls_name}.get_population()[{i}] must be ndarray, got {type(arr).__name__}"
        )


@pytest.mark.parametrize("module,cls_name", _L2_ADAPTERS, ids=[c for _, c in _L2_ADAPTERS])
def test_l2_set_population_returns_true_on_valid_input(module, cls_name):
    """set_population() with valid (N,D) pop + (N,M) obj + (N,) vio must return True."""
    import importlib
    cls = getattr(importlib.import_module(module), cls_name)
    adapter = _make_adapter(cls)
    ok = adapter.set_population(_POP.copy(), _OBJ.copy(), _VIO.copy())
    assert ok is True, f"{cls_name}.set_population() returned {ok!r} (expected True)"


@pytest.mark.parametrize("module,cls_name", _L2_ADAPTERS, ids=[c for _, c in _L2_ADAPTERS])
def test_l2_population_roundtrip_shape_and_values(module, cls_name):
    """After set_population(), get_population() must return matching shapes and values."""
    import importlib
    cls = getattr(importlib.import_module(module), cls_name)
    adapter = _make_adapter(cls)
    adapter.set_population(_POP.copy(), _OBJ.copy(), _VIO.copy())
    pop, obj, vio = adapter.get_population()
    assert pop.shape == _POP.shape, f"{cls_name}: pop shape {pop.shape} != expected {_POP.shape}"
    assert obj.shape == _OBJ.shape, f"{cls_name}: obj shape {obj.shape} != expected {_OBJ.shape}"
    assert vio.shape == _VIO.shape, f"{cls_name}: vio shape {vio.shape} != expected {_VIO.shape}"
    np.testing.assert_allclose(pop, _POP, rtol=1e-5, atol=1e-7,
                               err_msg=f"{cls_name}: pop values changed in roundtrip")
    np.testing.assert_allclose(obj, _OBJ, rtol=1e-5, atol=1e-7,
                               err_msg=f"{cls_name}: obj values changed in roundtrip")
    np.testing.assert_allclose(vio, _VIO, rtol=1e-5, atol=1e-7,
                               err_msg=f"{cls_name}: vio values changed in roundtrip")


@pytest.mark.parametrize("module,cls_name", _L2_ADAPTERS, ids=[c for _, c in _L2_ADAPTERS])
def test_l2_get_state_set_state_roundtrip(module, cls_name):
    """get_state() must return a dict; set_state(get_state()) must not raise."""
    import importlib
    cls = getattr(importlib.import_module(module), cls_name)
    adapter = _make_adapter(cls)
    state = adapter.get_state()
    assert isinstance(state, dict), f"{cls_name}.get_state() must return dict"
    adapter.set_state(state)  # must not raise
    state2 = adapter.get_state()
    assert set(state.keys()) == set(state2.keys()), (
        f"{cls_name}: get_state() key set changed after roundtrip: "
        f"{set(state.keys())} -> {set(state2.keys())}"
    )


# ---------------------------------------------------------------------------
# Specific regression: MOEAD now declares L2 and has get_state/set_state
# ---------------------------------------------------------------------------

def test_moead_declares_l2():
    from nsgablack.adapters.moead import MOEADAdapter
    assert MOEADAdapter.state_recovery_level == "L2", (
        "MOEADAdapter must declare state_recovery_level='L2' (has get/set_population)."
    )


def test_moead_has_get_state_and_set_state():
    from nsgablack.adapters.moead import MOEADAdapter
    adapter = MOEADAdapter()
    assert callable(getattr(adapter, "get_state", None)), "MOEADAdapter must have get_state()"
    assert callable(getattr(adapter, "set_state", None)), "MOEADAdapter must have set_state()"


def test_moead_get_state_schema():
    from nsgablack.adapters.moead import MOEADAdapter
    adapter = MOEADAdapter()
    state = adapter.get_state()
    assert isinstance(state, dict)
    # Expect scalar fields to be present
    for key in ("_m", "_n"):
        assert key in state, f"MOEADAdapter.get_state() missing key '{key}'"


def test_moead_set_state_roundtrip():
    from nsgablack.adapters.moead import MOEADAdapter
    adapter = MOEADAdapter()
    state = adapter.get_state()
    adapter.set_state(state)
    state2 = adapter.get_state()
    assert set(state.keys()) == set(state2.keys())


# ---------------------------------------------------------------------------
# Specific regression: NSGA3Adapter explicitly declares L2
# ---------------------------------------------------------------------------

def test_nsga3_explicitly_declares_l2():
    from nsgablack.adapters.nsga3 import NSGA3Adapter
    # Verify it's declared on the class itself, not just inherited.
    assert "state_recovery_level" in NSGA3Adapter.__dict__, (
        "NSGA3Adapter must explicitly declare state_recovery_level in its class body "
        "(not just rely on NSGA2Adapter inheritance)."
    )
    assert NSGA3Adapter.state_recovery_level == "L2"


def test_nsga3_inherits_population_methods():
    from nsgablack.adapters.nsga3 import NSGA3Adapter
    adapter = NSGA3Adapter()
    assert callable(getattr(adapter, "get_population", None))
    assert callable(getattr(adapter, "set_population", None))
    ok = adapter.set_population(_POP.copy(), _OBJ.copy(), _VIO.copy())
    assert ok is True
    pop, obj, vio = adapter.get_population()
    assert pop.shape == _POP.shape
