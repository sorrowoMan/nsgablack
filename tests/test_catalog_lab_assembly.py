"""Free assembly must execute real formal algorithms, not a new recipe switch."""
from __future__ import annotations

import ast
from dataclasses import fields
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import numpy as np
import pytest

from nsgablack.catalog.lab_assembly import (
    ASSEMBLY_SCHEMA, assembly_catalog, assembly_from_recipe, normalize_assembly)
from nsgablack.catalog.lab_project import export_project, normalize_spec, preview_files, project_archive


def test_catalog_metadata_matches_actual_component_contracts_both_profiles():
    from nsgablack import adapters
    from nsgablack.catalog.registry import get_source_catalog

    metadata = assembly_catalog()
    assert json.loads(json.dumps(metadata)) == metadata
    assert metadata["unsupported"]
    for profile in ("default", "framework-core"):
        catalog = get_source_catalog(profile=profile)
        for records in metadata["components"].values():
            for entry in records:
                if entry["catalog_key"]:
                    assert catalog.get(entry["catalog_key"]) is not None
    for entry in metadata["components"]["adapters"]:
        cls, cfg = getattr(adapters, entry["constructor"]), getattr(adapters, entry["config"])
        assert set(entry["parameters"]) <= {f.name for f in fields(cfg)}
        assert entry["operations"] == cls.operation_methods
        modes = set(cls.pool_input_modes)
        if cls.supports_pool_restart:
            modes.add("refine")
        assert set(entry["pool_modes"]) == modes
    metadata["components"]["adapters"].clear()
    assert len(assembly_catalog()["components"]["adapters"]) == 6


def test_recipe_documents_are_editable_and_preview_zip_export_have_one_source(tmp_path, monkeypatch):
    from nsgablack.adapters import NSGA2Adapter, VNSAdapter

    def forbidden(*args, **kwargs):
        raise AssertionError("preview must not construct Adapter / Unit")

    monkeypatch.setattr(NSGA2Adapter, "__init__", forbidden)
    monkeypatch.setattr(VNSAdapter, "__init__", forbidden)
    for recipe in ("ga", "vns", "moead", "ga_vns"):
        spec = assembly_from_recipe(recipe)
        assert normalize_spec(spec) == spec == normalize_assembly(spec)
        assert spec["schema"] == ASSEMBLY_SCHEMA and spec["recipe"] == "assembly"
    spec = assembly_from_recipe("ga_vns")
    spec["nodes"][1].update(component="adapter.sa", parameters={}, change="native")
    files = preview_files(spec)
    assert "A.SimulatedAnnealingAdapter" in files["cases/search/adapter/__init__.py"]
    assert "A.VNSAdapter" not in files["cases/search/adapter/__init__.py"]
    for name, source in files.items():
        if name.endswith(".py"):
            ast.parse(source, filename=name)
    root = export_project(spec, tmp_path / "project")
    assert {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
            for p in root.rglob("*") if p.is_file()} == files
    archive = project_archive(spec)
    assert archive == project_archive(spec)
    with ZipFile(BytesIO(archive)) as zipped:
        assert {n.removeprefix("algorithm_lab/"): zipped.read(n).decode("utf-8")
                for n in zipped.namelist()} == files


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(code="import os"),
    lambda s: s["nodes"][0].update(component="os.system"),
    lambda s: s["nodes"][0].update(id="../../pwn"),
    lambda s: s["nodes"][0]["parameters"].update(population_size=True),
    lambda s: s["nodes"][0]["parameters"].update(population_size=25),
    lambda s: s["nodes"][0].update(change="gaussian"),
    lambda s: s.update(seed=float("nan")),
    lambda s: s.update(initial_count=2),
    lambda s: s["nodes"][0]["input"].update(count=3),
    lambda s: s["nodes"][0]["input"].update(mode="refine"),
    lambda s: s["plan"].update(action="compete", steps=None),
    lambda s: s.update(plan={"kind": "shell", "node": "ga"}),
    lambda s: s["nodes"].append(s["nodes"][0].copy()),
    lambda s: s.update(bias={"component": "bias.bayesian"}),
    lambda s: s.update(plugins=[{"component": "plugin.os"}]),
    lambda s: s.update(pipeline={"mutator": None}),
    lambda s: s["pipeline"]["initializer"]["parameters"].update(low=2, high=-2),
    lambda s: s.update(nodes=[{"id": "m", "component": "adapter.moead"}],
                       problem={"component": "problem.sphere"}, plan={"kind": "stage", "node": "m"}),
    lambda s: s.update(plan={"kind": "multi", "children": [
        {"kind": "stage", "node": "ga"}, {"kind": "stage", "node": "ga"}]}),
    lambda s: s.update(plan={"kind": "repeat", "times": 11, "body": {"kind": "stage", "node": "ga"}}),
])
def test_static_validation_rejects_incompatible_or_unbounded_documents(mutation):
    spec = assembly_from_recipe("ga")
    mutation(spec)
    with pytest.raises((ValueError, TypeError)):
        normalize_assembly(spec)


def test_view_publication_requires_causal_stage_barriers():
    spec = assembly_from_recipe("ga_vns")
    spec["nodes"][0]["return_from"] = None
    a, b, _ = spec["plan"]["children"]
    spec["plan"] = dict(kind="multi", children=[a, b])
    with pytest.raises(ValueError, match="视图尚未发布"):
        normalize_assembly(spec)
    spec["plan"] = dict(kind="serial", children=[b, a])
    with pytest.raises(ValueError, match="视图尚未发布"):
        normalize_assembly(spec)


def test_repeat_and_new_population_search_cannot_return_stale_refinement_requests():
    spec = _small(assembly_from_recipe("ga_vns"))
    first, refine, compete = spec["plan"]["children"]
    # The first loop has a real result, the second must not re-use it.
    spec["plan"] = dict(kind="serial", children=[first, refine,
        dict(kind="repeat", times=2, body=compete)])
    with pytest.raises(ValueError, match="旧请求"):
        normalize_assembly(spec)
    # A new population search also invalidates previous dependent refinements.
    extra = {**first, "label": "new_search"}
    spec["plan"] = dict(kind="serial", children=[first, refine, extra, compete])
    with pytest.raises(ValueError, match="新精修"):
        normalize_assembly(spec)


def _small(spec):
    spec["initial_count"] = 8
    for n in spec["nodes"]:
        if "population_size" in n["parameters"]:
            n["parameters"]["population_size"] = 4
            n["input"]["count"] = 4
            if "offspring_size" in n["parameters"]:
                n["parameters"]["offspring_size"] = 4
    return spec


def _sa_return():
    s = _small(assembly_from_recipe("ga_vns"))
    s["nodes"][1].update(component="adapter.sa", parameters={}, change="native")
    s["bias"] = dict(component="bias.l2_preference", parameters=dict(weight=.2))
    s["plugins"] = [dict(component="plugin.pareto_archive")]
    s["pipeline"]["repair"]["component"] = "repr.box_projection"
    return s


def _moead_directions():
    s = _small(assembly_from_recipe("ga_vns"))
    s["nodes"][0].update(component="adapter.moead", parameters=dict(population_size=4,
        neighborhood_size=4, batch_size=2), change="moead_blend")
    s["nodes"][1]["input"].update(source=dict(adapter="ga", views="random", view_count=2), count=1)
    s["plan"]["children"][0]["steps"] = 1
    return s


def _parallel_local():
    return dict(initial_count=8, max_steps=20, problem=dict(component="problem.sphere"), nodes=[
        dict(id="ga", component="adapter.nsga2", parameters=dict(population_size=4, offspring_size=4)),
        dict(id="de", component="adapter.de", parameters=dict(population_size=4, batch_size=2)),
        dict(id="local", component="adapter.pattern_search", input=dict(mode="refine", source="main", count=2, steps=2))],
        plan=dict(kind="serial", children=[dict(kind="multi", children=[
            dict(kind="stage", node="ga", steps=2), dict(kind="stage", node="de", steps=2)]),
            dict(kind="stage", node="local")]))


def _nested_repeat():
    return dict(initial_count=8, max_steps=20, nodes=[
        dict(id="ga", component="adapter.nsga2", parameters=dict(population_size=4, offspring_size=4)),
        dict(id="sa", component="adapter.sa")],
        plan=dict(kind="repeat", times=2, body=dict(kind="serial", children=[
            dict(kind="stage", node="ga", steps=2), dict(kind="multi", children=[
                dict(kind="stage", node="sa", steps=2)])])))


def _nested_views():
    s = _moead_directions()
    s["nodes"][1]["return_from"] = None
    s["nodes"].append(dict(id="polish", component="adapter.pattern_search", input=dict(mode="refine",
        source=dict(adapter="vns", views="all"), count=1, steps=2)))
    s["nodes"][0]["return_from"] = "polish"
    s["plan"]["children"].insert(2, dict(kind="stage", node="polish"))
    return s


def _repeated_handoff():
    s = _small(assembly_from_recipe("ga_vns"))
    s["max_steps"] = 30
    s["plan"]["children"][0]["steps"] = 1
    s["plan"] = dict(kind="repeat", times=2, body=s["plan"])
    return s


@pytest.mark.parametrize("factory, types", [
    (_sa_return, {"NSGA2Adapter", "SimulatedAnnealingAdapter"}),
    (_moead_directions, {"MOEADAdapter", "VNSAdapter"}),
    (_parallel_local, {"NSGA2Adapter", "DifferentialEvolutionAdapter", "PatternSearchAdapter"}),
    (_nested_repeat, {"NSGA2Adapter", "SimulatedAnnealingAdapter"}),
    (_nested_views, {"MOEADAdapter", "VNSAdapter", "PatternSearchAdapter"}),
    (_repeated_handoff, {"NSGA2Adapter", "VNSAdapter"}),
])
def test_real_project_assembly_handoffs_keep_raw_evidence_and_l0(tmp_path, factory, types):
    spec = normalize_assembly(factory())
    project = export_project(spec, tmp_path / "project")
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(repo), str(repo.parent), os.environ.get("PYTHONPATH", "")])}
    completed = subprocess.run([sys.executable, "run_project.py", "--run-id", "assembly-test"],
        cwd=project, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    assert completed.returncode == 0, completed.stdout[-6000:] + completed.stderr[-6000:]
    report = json.loads((project / "results/lab_report.json").read_text(encoding="utf-8"))
    manifest = json.loads((project / ".blackbase/runs/assembly-test/manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert report["spec"] == spec and report["plan_completed"] is True
    assert report["resource_binding_audit"]["current"] is True
    assert report["resource_binding_audit"]["effective"]["grant"]["threads"] == 1
    publication = manifest["cases"][0]["result"]["artifact_publications"]["lab_report"]
    assert publication["receipt_digest"].startswith("sha256:")
    assert types <= {node["type"] for node in report["units"]}
    for typ in types:
        assert len([node for node in report["units"] if node["type"] == typ]) == 1
    result = report["result"]
    x = np.asarray(result["candidates"])
    assert len(x) > 0 and np.max(np.abs(x)) <= 2
    if spec["problem"]["component"] == "problem.sphere":
        expected = np.sum(x ** 2, axis=1).reshape(-1, 1)
    else:
        left, right = np.zeros(spec["dimension"]), np.zeros(spec["dimension"])
        left[0], right[0] = -1, 1
        expected = np.column_stack([np.sum((x - left) ** 2, axis=1), np.sum((x - right) ** 2, axis=1)])
    np.testing.assert_allclose(result["raw_objectives"], expected)
    assert np.max(result["raw_violations"]) == 0
    assert len(report["records"]) == report["steps"] <= spec["max_steps"]
    assert not any(node["unit_exists"] for node in report["initial"]["units"])
    if factory is _sa_return:
        assert "ParetoArchivePlugin" in report["assembly_components"]["plugins"]
    if factory in {_moead_directions, _nested_views}:
        direction_views = [v for v in report["pool"]["views"] if v["metadata"]["kind"] == "objective_projection"]
        assert len(direction_views) >= 4
        assert report["records"][-1]["phases"] == [spec["plan"]["children"][-1]["label"]]
