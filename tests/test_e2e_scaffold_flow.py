from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from nsgablack.catalog.quick_add import build_entry_payload, upsert_catalog_entry
from nsgablack.project import init_project, load_project_catalog


def test_e2e_scaffold_register_search_build_run_doctor(tmp_path):
    root = init_project(tmp_path / "e2e_project")

    # 1) write a minimal component
    (root / "bias" / "flow_bias.py").write_text(
        "class FlowBias:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = ('e2e flow bias',)\n"
        "    requires_metrics = ()\n"
        "    metrics_fallback = 'none'\n"
        "    missing_metrics_policy = 'warn'\n"
        "    def __init__(self, weight: float = 1.0):\n"
        "        self.weight = float(weight)\n"
        "    def compute(self, x, context):\n"
        "        return 0.0\n",
        encoding="utf-8",
    )

    # 2) register into project catalog
    payload = build_entry_payload(
        key="project.bias.flow_bias",
        title="FlowBias",
        kind="bias",
        import_path="bias.flow_bias:FlowBias",
        summary="E2E minimal bias for scaffold flow regression.",
        tags=("project", "bias", "e2e"),
        context_requires=(),
        context_provides=(),
        context_mutates=(),
        context_cache=(),
        context_notes=("e2e flow bias",),
    )
    upsert_catalog_entry(root / "catalog" / "entries.toml", payload, replace=True)

    # 3) catalog search (project scope)
    project_catalog = load_project_catalog(root, include_global=False)
    hits = project_catalog.search("project.bias.flow_bias", kinds=("bias",))
    assert any(h.key == "project.bias.flow_bias" for h in hits)

    # 4) build + run (isolated process to avoid package-name collisions with framework root)
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util, json;"
                "spec=importlib.util.spec_from_file_location('project_build_solver','build_solver.py');"
                "mod=importlib.util.module_from_spec(spec);"
                "spec.loader.exec_module(mod);"
                "solver=mod.build_solver(['--generations','2','--pop-size','12','--enable-bias']);"
                "result=solver.run(return_dict=True);"
                "print('ok' if isinstance(result, dict) else 'bad')"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert "ok" in run.stdout

    # 5) audit
    doctor = subprocess.run(
        [sys.executable, "-m", "nsgablack", "project", "doctor", "--path", ".", "--strict"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert doctor.returncode == 0, doctor.stdout + "\n" + doctor.stderr


def test_project_catalog_can_load_split_kind_toml(tmp_path):
    root = init_project(tmp_path / "split_project")
    payload = build_entry_payload(
        key="project.bias.split_bias",
        title="SplitBias",
        kind="bias",
        import_path="bias.example_bias:BiasTemplate",
        summary="Split catalog file regression.",
        tags=("project", "split"),
    )
    target = root / "catalog" / "entries" / "bias.toml"
    upsert_catalog_entry(target, payload, replace=True)

    project_catalog = load_project_catalog(root, include_global=False)
    hit = project_catalog.get("project.bias.split_bias")
    assert hit is not None
    assert hit.kind == "bias"
