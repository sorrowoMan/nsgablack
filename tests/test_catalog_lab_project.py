"""Lab source/export contract and real formal Project acceptance."""
from __future__ import annotations

import ast
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import numpy as np
import pytest

from nsgablack.catalog import lab_project as lab


def test_recipe_metadata_is_detached_and_catalog_links_exist():
    from nsgablack.catalog.registry import get_source_catalog

    recipes = lab.list_recipes()
    assert {row["id"] for row in recipes} == {"ga", "vns", "moead", "ga_vns"}
    for profile in ("default", "framework-core"):
        catalog = get_source_catalog(profile=profile)
        for row in recipes:
            assert all(catalog.get(key) is not None for key in row["components"])
            assert set(row["defaults"]) == set(row["parameters"])
            assert lab.normalize_spec({"recipe": row["id"]}) == {
                "schema": lab.SPEC_SCHEMA, "recipe": row["id"], **row["defaults"]}
    recipes[0]["defaults"]["max_steps"] = -1
    assert lab.list_recipes()[0]["defaults"]["max_steps"] > 0


@pytest.mark.parametrize("spec", [None, [], "ga"])
def test_spec_rejects_non_mapping(spec):
    with pytest.raises(TypeError):
        lab.normalize_spec(spec)


@pytest.mark.parametrize("spec", [
    {"schema": "unknown"}, {"recipe": "../../evil"}, {"recipe": "bo"},
    {"seed": True}, {"seed": -1}, {"dimension": 8.0}, {"dimension": 9},
    {"initial_count": 0}, {"max_steps": 51}, {"max_steps": "3"},
    {"population_size": 25}, {"population_size": 6, "initial_count": 5},
    {"recipe": "vns", "population_size": 6}, {"ga_steps": 1},
    {"recipe": "ga_vns", "local_steps": 5}, {"recipe": "ga_vns", "ga_steps": 9},
    {"code": "import os"}, {"path": "secret"}, {"import_path": "os:system"},
    {1: "not a field"},
])
def test_spec_rejects_unsafe_unknown_or_out_of_bound_values(spec):
    with pytest.raises(ValueError):
        lab.normalize_spec(spec)


def test_preview_zip_and_export_are_the_same_source_without_unit_construction(tmp_path, monkeypatch):
    from nsgablack.adapters import NSGA2Adapter, VNSAdapter, MOEADAdapter

    def forbidden(*args, **kwargs):
        raise AssertionError("preview must not instantiate an algorithm")

    for adapter in (NSGA2Adapter, VNSAdapter, MOEADAdapter):
        monkeypatch.setattr(adapter, "__init__", forbidden)
    spec = lab.normalize_spec({"recipe": "ga_vns", "seed": 313})
    files = lab.preview_files(spec)
    assert "313" in files["cases/search/config.py"]
    assert json.loads(files["lab_spec.json"]) == spec
    for name, source in files.items():
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        if name.endswith(".py"):
            ast.parse(source, filename=name)
    root = lab.export_project(spec, tmp_path / "different_project_name")
    assert root.is_absolute()
    actual = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
              for p in root.rglob("*") if p.is_file()}
    assert actual == files
    zipped = lab.project_archive(spec)
    assert zipped == lab.project_archive(spec)
    with ZipFile(BytesIO(zipped)) as archive:
        assert {name.removeprefix("algorithm_lab/"): archive.read(name).decode("utf-8")
                for name in archive.namelist()} == files
    assert {"project_config.py", "run_project.py", "cases/__init__.py", "cases/search/.case",
            "cases/search/build_solver.py", "cases/search/run_solver.py",
            "cases/search/build_trainer.py", "cases/search/run_trainer.py"} <= files.keys()
    assert "from .build_solver import build_solver as build_trainer" in files["cases/search/build_trainer.py"]
    with pytest.raises(FileExistsError):
        lab.export_project(spec, root)
    assert actual == {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
                      for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("recipe, settings", [
    ("moead", {"max_steps": 3, "population_size": 4, "initial_count": 8, "dimension": 3}),
    ("ga_vns", {"max_steps": 11, "population_size": 4, "initial_count": 8,
                "ga_steps": 1, "local_steps": 2}),
])
def test_real_project_preserves_raw_objectives_and_publishes_report_receipt(tmp_path, recipe, settings):
    spec = lab.normalize_spec({"recipe": recipe, **settings})
    root = lab.export_project(spec, tmp_path / "project")
    repo = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(repo), str(repo.parent), env.get("PYTHONPATH", "")])
    completed = subprocess.run([sys.executable, "run_project.py", "--run-id", "lab-test"],
        cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-4000:]
    manifest = json.loads((root / ".blackbase/runs/lab-test/manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok" and manifest["exit_code"] == 0
    case = manifest["cases"][0]["result"]
    report = json.loads((root / "results/lab_report.json").read_text(encoding="utf-8"))
    assert report["schema"] == lab.REPORT_SCHEMA and report["spec"] == spec
    assert report["project_identity"] == case["identity"]
    assert report["steps"] == case["output"]["report"]["steps"]
    assert report["evaluations"] == case["output"]["report"]["evaluation_count"] > 0
    assert report["resource_binding_audit"]["current"] is True
    assert report["resource_binding_audit"]["effective"]["grant"]["threads"] == 1
    ref = case["artifact_refs"]["lab_report"]
    publication = case["artifact_publications"]["lab_report"]
    assert publication["ref"] == ref and publication["case_run_id"] == case["identity"]["case_run_id"]
    assert publication["receipt_digest"].startswith("sha256:")
    artifact = Path(ref["uri"]).read_bytes()
    assert "sha256:" + hashlib.sha256(artifact).hexdigest() == ref["checksum"]
    assert json.loads(artifact) == report
    result = report["result"]
    values = np.asarray(result["candidates"])
    assert values.shape == (len(result["refs"]), spec["dimension"])
    assert len(result["refs"]) == len(result["raw_objectives"]) == len(result["raw_violations"])
    assert np.isfinite(values).all() and np.all(values >= -2) and np.all(values <= 2)
    left, right = np.zeros(spec["dimension"]), np.zeros(spec["dimension"])
    left[0], right[0] = -1, 1
    expected = np.column_stack((np.sum((values - left) ** 2, axis=1), np.sum((values - right) ** 2, axis=1)))
    np.testing.assert_allclose(result["raw_objectives"], expected)
    assert np.asarray(result["raw_violations"]).max() == 0
    assert report["initial"]["units"] and not any(row["unit_exists"] for row in report["initial"]["units"])
    assert len(report["records"]) == report["steps"] <= spec["max_steps"]
    if recipe == "ga_vns":
        assert report["plan_completed"] is True
        assert [r["phases"] for r in report["records"]] == [["ga"]] + [["vns"]] * 8 + [["return"]]
        assert any(row["type"] == "NSGA2Adapter" and row["population_members"] == 4 for row in report["units"])
    else:
        directions = [view for view in report["pool"]["views"]
                      if view["metadata"]["kind"] == "objective_projection"]
        assert len(directions) == 4 and all(view["metadata"]["created_by"] for view in directions)
        assert all(view["members"] == 1 for view in directions)
