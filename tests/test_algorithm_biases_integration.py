import ast
from pathlib import Path

from nsgablack.catalog.registry import get_catalog
from nsgablack.project.doctor import run_project_doctor


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = REPO_ROOT / "core" / "adapters"


def test_catalog_uses_adapter_entries_for_process_algorithms():
    catalog = get_catalog(refresh=True)
    keys = {entry.key for entry in catalog._entries}

    # Canonical process algorithm entries must exist in adapter layer.
    required_adapter_keys = {
        "adapter.de",
        "adapter.gradient_descent",
        "adapter.pattern_search",
        "adapter.nsga2",
        "adapter.nsga3",
        "adapter.spea2",
    }
    assert required_adapter_keys.issubset(keys)

    # Process-like bias entries must be removed.
    removed_bias_keys = {
        "bias.sa",
        "bias.de",
        "bias.gradient_descent",
        "bias.pattern_search",
        "bias.nsga2_core",
        "bias.nsga3_core",
        "bias.spea2_core",
        "bias.moead_decomposition",
    }
    assert keys.isdisjoint(removed_bias_keys)


def test_adapter_layer_contains_no_bias_style_classes_or_compute_api():
    for py_file in ADAPTER_DIR.glob("*.py"):
        if py_file.name.startswith("__"):
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            assert not node.name.endswith("Bias"), f"{py_file}: forbidden class name {node.name}"
            method_names = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            assert "compute" not in method_names, f"{py_file}: forbidden bias-style compute() in {node.name}"


def test_algorithm_adapter_subclasses_have_propose_and_update():
    for py_file in ADAPTER_DIR.glob("*.py"):
        if py_file.name.startswith("__"):
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)
            if "AlgorithmAdapter" not in base_names:
                continue
            method_names = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            assert "propose" in method_names, f"{py_file}: {node.name} missing propose()"
            assert "update" in method_names, f"{py_file}: {node.name} missing update()"


def test_doctor_strict_has_no_adapter_layer_purity_error():
    report = run_project_doctor(path=REPO_ROOT, instantiate_solver=False, strict=True)
    errors = [d for d in report.diagnostics if d.level == "error" and d.code == "adapter-layer-purity"]
    assert not errors

