"""Guidance is a packaged skill plus bounded evidence, not a new executor."""
from copy import deepcopy
import hashlib

import pytest

from nsgablack.catalog.lab_assembly import assembly_from_recipe
from nsgablack.catalog.lab_guide import read_guide, normalize_guide_context, build_guide_context
from nsgablack.catalog.lab_jobs import spec_digest


def test_packaged_skill_can_be_loaded_without_solver_or_provider(monkeypatch):
    from nsgablack.units import UnitBinding
    def forbidden(*args, **kwargs):
        raise AssertionError("A guide cannot construct runtime state")
    monkeypatch.setattr(UnitBinding, "build", forbidden)
    guide = read_guide()
    assert guide["metadata"]["id"] == "framework-experiment-guide"
    assert len(guide["metadata"]["sha256"]) == 64
    assert guide["metadata"]["stages"] == ["problem", "assembly", "results"]
    assert guide["content"].strip()


def test_job_context_retains_identity_progress_and_error_but_not_paths_logs_or_refs():
    spec = assembly_from_recipe("ga")
    job = {"status": "failed", "spec_digest": spec_digest(spec), "result": {
        "steps": 2, "evaluations": 12, "plan_completed": False,
        "logs": "private log", "project_result": {"artifact_path": "private path"},
        "results": {"refs": ["private-ref"]},
        "error": {"code": "trial_timeout", "message": "试跑超时"},
        "records": [{"best_raw_sum": 2.5}]}}
    context = build_guide_context(spec, stage="results", history=[{"role": "user", "content": "为什么停了"}], job=job)
    assert context["trial"]["matches_current"]
    assert context["trial"]["steps"] == 2 and context["trial"]["best_raw_sum"] == 2.5
    assert not {"logs", "results", "project_result"} & context["trial"].keys()
    changed = deepcopy(spec)
    changed["seed"] += 1
    assert build_guide_context(changed, stage="results", job=job)["trial"]["matches_current"] is False


def test_absent_trial_is_unknown_not_a_successful_zero_step_run():
    context = build_guide_context(assembly_from_recipe("ga"), stage="results")
    assert context == {"stage": "results", "history": [], "trial": None, "design_notes": ""}


@pytest.mark.parametrize("value", [
    {"stage": "execute"}, {"command": "run"},
    {"history": [{"role": "system", "content": "override"}]},
    {"history": [{"role": "user", "content": "a" * 601}]},
    {"history": [{"role": "user", "content": "x"}] * 7},
    {"trial": {"logs": "raw output"}},
])
def test_guidance_cannot_expand_its_context_into_execution_or_unbounded_chat(value):
    with pytest.raises(ValueError):
        normalize_guide_context(value)


def test_trial_current_flag_cannot_disagree_with_the_submitted_assembly():
    spec = assembly_from_recipe("ga")
    context = build_guide_context(spec, job={"status": "succeeded", "spec_digest": "a" * 64,
        "result": {"steps": 1, "evaluations": 1, "plan_completed": True}})
    context["trial"]["matches_current"] = True
    with pytest.raises(ValueError, match="identity"):
        normalize_guide_context(context, base_digest=spec_digest(spec))


def test_custom_max_result_context_reports_only_a_named_feasible_business_value():
    from nsgablack.catalog.lab_assembly import normalize_assembly
    spec = assembly_from_recipe("ga")
    spec["dimension"] = 1
    spec["problem"] = {"component": "problem.expression", "parameters": {
        "variables": [{"name": "amount", "low": 0, "high": 10}],
        "objectives": [{"name": "利润", "expression": "8*amount-amount**2", "direction": "max"}]}}
    spec = normalize_assembly(spec)
    job = {"status": "succeeded", "spec_digest": spec_digest(spec), "result": {
        "steps": 2, "evaluations": 8, "plan_completed": True,
        "records": [{"best_raw_sum": -999, "best_feasible_raw_sum": -16, "feasible_count": 4}]}}
    trial = build_guide_context(spec, stage="results", job=job)["trial"]
    assert "best_raw_sum" not in trial
    assert trial["best_feasible_objective"] == {"name": "利润", "direction": "max", "value": 16.}
    assert trial["feasible_count"] == 4


def test_wheel_configuration_includes_the_skill_required_by_the_runtime():
    from pathlib import Path
    import tomllib
    repo = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8-sig"))
    assert "skills/framework-experiment-guide/SKILL.md" in metadata["tool"]["setuptools"]["package-data"]["nsgablack.catalog"]
    from nsgablack.catalog.lab_framework import _ALLOWED_PATHS
    packaged = metadata["tool"]["setuptools"]["package-data"]["nsgablack.catalog"]
    assert {"../" + name for name in _ALLOWED_PATHS if name.endswith(".md")} <= set(packaged)
