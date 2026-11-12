"""Verify the isolated trial worker and its real hosted Catalog workbench.

This deliberately runs bounded recipe and freely assembled Projects. It never calls AI or
adds execution authority to Catalog browsing. Use --worker-only inside the
credential-free worker image before connecting it to the Catalog reader.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import math
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch


def free_assembly_scenarios():
    """Concrete assembly documents, not additional named runtime recipes."""
    from nsgablack.catalog.lab_assembly import normalize_assembly

    ga_sa = dict(initial_count=8, max_steps=20,
        bias=dict(component="bias.l2_preference", parameters=dict(weight=.2)),
        plugins=[dict(component="plugin.pareto_archive")],
        pipeline=dict(repair=dict(component="repr.box_projection")),
        nodes=[dict(id="ga", component="adapter.nsga2", parameters=dict(population_size=4,
                    offspring_size=4), return_from="sa"),
               dict(id="sa", component="adapter.sa", input=dict(mode="refine",
                    source=dict(adapter="ga", views="all"), count="all", steps=2))],
        plan=dict(kind="serial", children=[dict(kind="stage", node="ga", steps=2),
            dict(kind="stage", node="sa"), dict(kind="stage", node="ga", action="compete")]))
    moead_vns = dict(initial_count=8, max_steps=20, nodes=[
        dict(id="directions", component="adapter.moead", parameters=dict(population_size=4,
            neighborhood_size=4, batch_size=2), change="moead_blend", return_from="local"),
        dict(id="local", component="adapter.vns", change="gaussian", input=dict(mode="refine",
            source=dict(adapter="directions", views="random", view_count=2), count=1, steps=2))],
        plan=dict(kind="serial", children=[dict(kind="stage", node="directions", steps=1),
            dict(kind="stage", node="local"), dict(kind="stage", node="directions", action="compete")]))
    parallel = dict(initial_count=8, max_steps=20, problem=dict(component="problem.sphere"), nodes=[
        dict(id="ga", component="adapter.nsga2", parameters=dict(population_size=4, offspring_size=4)),
        dict(id="de", component="adapter.de", parameters=dict(population_size=4, batch_size=2)),
        dict(id="local", component="adapter.pattern_search", input=dict(mode="refine",
            source="main", count=2, steps=2))], plan=dict(kind="serial", children=[
                dict(kind="multi", children=[dict(kind="stage", node="ga", steps=2),
                                              dict(kind="stage", node="de", steps=2)]),
                dict(kind="stage", node="local")]))
    # A child view of a directional refinement is consumed by a different leaf;
    # the original direction owner receives the final descendant's candidates.
    nested = json.loads(json.dumps(moead_vns))
    nested["nodes"][0]["return_from"] = "polish"
    nested["nodes"].append(dict(id="polish", component="adapter.pattern_search", input=dict(mode="refine",
        source=dict(adapter="local", views="all"), count=1, steps=2)))
    nested["plan"]["children"].insert(2, dict(kind="stage", node="polish"))
    # Deliberately infeasible: a successful Project must still retain positive
    # hard violations, and a max objective must remain a negated raw score.
    custom = dict(seed=17, initial_count=8, max_steps=3,
        problem=dict(component="problem.expression", parameters=dict(
            variables=[dict(name="quantity", low=0., high=10., type="continuous"),
                       dict(name="price", low=100., high=105., type="continuous")],
            objectives=[dict(name="利润", expression="quantity*price-quantity**2", direction="max"),
                        dict(name="成本", expression="price+quantity", direction="min")],
            constraints=[dict(name="资源上限", expression="price", relation="<=", rhs=90., tolerance=.5)])),
        pipeline=dict(initializer=dict(component="repr.problem_uniform", parameters={}),
                      repair=dict(component="repr.box_projection")),
        nodes=[dict(id="ga", component="adapter.nsga2", change="ga_mask",
                    parameters=dict(population_size=4, offspring_size=4))],
        plan=dict(kind="stage", node="ga", steps=3))
    return {
        "ga_sa_return": (normalize_assembly(ga_sa), {"NSGA2Adapter", "SimulatedAnnealingAdapter"}),
        "moead_direction_refinement": (normalize_assembly(moead_vns), {"MOEADAdapter", "VNSAdapter"}),
        "parallel_then_refine": (normalize_assembly(parallel), {
            "NSGA2Adapter", "DifferentialEvolutionAdapter", "PatternSearchAdapter"}),
        "nested_direction_views": (normalize_assembly(nested), {
            "MOEADAdapter", "VNSAdapter", "PatternSearchAdapter"}),
        "custom_problem_max_constraints": (normalize_assembly(custom), {"NSGA2Adapter"}),
    }


def _verify_custom_problem(result):
    """Independent oracle for the concrete formula above, beyond shape checks."""
    rows = result["results"]
    assert rows["variable_names"] == ["quantity", "price"]
    assert rows["objective_names"] == ["利润", "成本"]
    assert rows["objective_directions"] == ["max", "min"]
    assert rows["candidates"] and len(rows["display_objectives"]) == len(rows["candidates"])
    for candidate, raw, shown, violation in zip(rows["candidates"], rows["raw_objectives"],
                                                rows["display_objectives"], rows["raw_violations"]):
        quantity, price = candidate
        assert 0 <= quantity <= 10 and 100 <= price <= 105
        profit, cost = quantity * price - quantity**2, price + quantity
        assert len(raw) == len(shown) == 2
        for actual, expected in zip(raw, [-profit, cost]):
            assert math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-12)
        for actual, expected in zip(shown, [profit, cost]):
            assert math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-12)
        assert math.isclose(violation, price - 90. - .5, rel_tol=1e-11, abs_tol=1e-12)
        assert violation > 0, "A successful trial must not erase an infeasible Problem's raw violation"
    return {"checked_rows": len(rows["candidates"]), "max_direction_preserved": True,
            "hard_violations_preserved": True, "per_variable_bounds_preserved": True}


def _verify_timeout_cleanup():
    """Fixed process-tree probe; it is not an executable browser input surface."""
    import psutil
    from nsgablack.catalog.lab_runner import _execute, _trial_environment
    with tempfile.TemporaryDirectory(prefix="lab-cleanup-check-") as scratch:
        root = Path(scratch)
        (root / "run_project.py").write_text(
            "import subprocess,sys,time,pathlib\n"
            "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
            "pathlib.Path('child.pid').write_text(str(p.pid))\n"
            "time.sleep(60)\n", encoding="utf-8")
        _, _, timed_out = _execute(root, "cleanup-probe", _trial_environment(root), 2)
        assert timed_out and (root / "child.pid").is_file()
        child_pid = int((root / "child.pid").read_text())
        deadline = time.monotonic() + 3
        while psutil.pid_exists(child_pid) and time.monotonic() < deadline:
            try:
                if psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
                    return True
            except psutil.NoSuchProcess:
                return True
            time.sleep(.05)
        assert not psutil.pid_exists(child_pid), "Trial timeout left a live descendant"
        return True


def verify(*, worker_only=False):
    from nsgablack.catalog import lab_client, lab_project
    from nsgablack.catalog.lab_assembly import assembly_catalog
    from nsgablack.catalog.lab_runner import run_trial
    from nsgablack.catalog.lab_jobs import spec_digest
    from nsgablack.catalog.lab_guide import read_guide

    if not worker_only:
        from runtime import configure_reader
        assert configure_reader(os.environ) == "only"
        caps = lab_client.get_capabilities()
        assert caps["enabled"] and caps["mode"] == "remote", "Hosted worker is unavailable"
        assert caps["assembly_catalog"] == assembly_catalog(), "Runner assembly schema differs"
        ai_caps = lab_client.assistant_capabilities()
        assert ai_caps["enabled"] and ai_caps["mode"] == "remote", "Private AI draft service is unavailable"
        assert ai_caps["assembly_catalog"] == assembly_catalog() and ai_caps["drafts_only"]
        assert ai_caps["guide"] == read_guide()["metadata"], "AI service is using a different guidance Skill"
        assert ai_caps["limits"]["requests_per_utc_day"] is None
        assert ai_caps["quota"]["remaining"] is None and ai_caps["quota"]["resets_at"] is None
        quota_before = dict(ai_caps["quota"])
    results, last_job = {}, None
    scenarios = {recipe: (lab_project.normalize_spec({"recipe": recipe}), set())
                 for recipe in ("ga", "vns", "moead", "ga_vns")}
    scenarios.update(free_assembly_scenarios())
    for scenario, (spec, expected_types) in scenarios.items():
        if worker_only:
            result = run_trial(spec)
        else:
            job = lab_client.submit(spec)
            deadline = time.monotonic() + 75
            while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
                time.sleep(.25)
                job = lab_client.poll(job["job_id"])
            assert job["spec_digest"] == spec_digest(spec)
            assert job["status"] == "succeeded", "Trial job did not succeed: " + scenario
            last_job = job
            result = job["result"]
        assert result["status"] == "succeeded", "Formal Project failed: " + scenario + ": " + str(result.get("error"))
        assert result["resource_binding"]["current"] is True
        assert result["steps"] > 0 and result["evaluations"] > 0
        assert result["project_result"]["report_publication"]["checksum"].startswith("sha256:")
        if expected_types or scenario == "ga_vns":
            assert result["plan_completed"] is True, "Assembly plan did not complete: " + scenario
        instances = result["unit"].get("instances", [])
        actual_types = {unit["type"] for unit in instances}
        assert expected_types <= actual_types, "A declared algorithm was not actually assembled"
        for expected in expected_types:
            assert sum(unit["type"] == expected for unit in instances) == 1, "A mutable leaf was recreated"
        if "direction" in scenario:
            projections = [view for view in result["pool"]["views"]
                           if view["metadata"].get("kind") == "objective_projection"]
            assert len(projections) >= 4 and all(view["metadata"].get("created_by") for view in projections)
        results[scenario] = {"steps": result["steps"], "evaluations": result["evaluations"],
                           "pool": result["pool"], "plan_completed": result.get("plan_completed"),
                           "algorithm_types": sorted(actual_types), "resource_current": True}
        if scenario == "custom_problem_max_constraints":
            results[scenario]["problem_evidence"] = _verify_custom_problem(result)

    app_runs = 0
    if not worker_only:
        from nsgablack.catalog import dashboard
        from nsgablack.catalog.curation_provider import DeepSeekGenerator
        from nsgablack.catalog.lab_assistant import DeepSeekAssemblyGenerator
        from nsgablack.units import UnitBinding
        from streamlit.testing.v1 import AppTest

        def forbidden(*args, **kwargs):
            raise AssertionError("Preview attempted to build a Unit, call AI or submit a trial")

        with patch.object(DeepSeekGenerator, "generate", forbidden), \
                patch.object(DeepSeekAssemblyGenerator, "generate", forbidden), \
                patch.object(UnitBinding, "build", forbidden), patch.object(lab_client, "submit", forbidden), \
                patch.object(lab_client, "assistant_submit", forbidden), \
                patch.object(lab_client, "assistant_poll", forbidden):
            for profile in ("default", "framework-core"):
                app = AppTest.from_file(dashboard.__file__, default_timeout=90)
                app.query_params.update({"view": "lab", "profile": profile})
                app.run()
                assert not app.exception, "Workbench preview failed"
                assert next(w for w in app.radio if w.label == "工作区").value == "装配实验台"
                chooser = next(w for w in app.selectbox if w.label == "载入一个配方作为起点")
                chooser.set_value("ga_vns").run()
                assert app.session_state["catalog_lab::draft"]["nodes"][0]["id"] == "ga"
                next(w for w in app.button if w.label == "载入配方").click().run()
                assert not app.exception and len(app.get("download_button")) >= 2
                assert len(app.session_state["catalog_lab::draft"]["nodes"]) == 2
                # Seed a real freely assembled document; rendering it must not
                # reinterpret it as one of the four recipe IDs or request AI.
                free_spec = scenarios["nested_direction_views"][0]
                app.session_state["catalog_lab::draft"] = free_spec
                app.session_state["catalog_lab::draft_revision"] += 1
                app.run()
                assert not app.exception and app.session_state["catalog_lab::draft"] == free_spec
                expected_tabs = ["1 · 定义问题", "2 · 装配算法", "3 · 运行结果"]
                assert [tab.label for tab in app.tabs if tab.label in expected_tabs] == expected_tabs
                assert {widget.label for widget in app.text_area} >= {
                    "描述要解决的问题", "描述想怎么调整算法", "针对运行结果，你想了解什么"}
                assert {widget.label for widget in app.button} >= {
                    "生成可编辑草案", "请 AI 调整装配", "请 AI 解读结果", "应用问题定义"}
                # Render the real custom Problem result with its own current
                # document; objective labels/directions must survive the UI.
                custom_spec = scenarios["custom_problem_max_constraints"][0]
                app.session_state["catalog_lab::draft"] = custom_spec
                app.session_state["catalog_lab::draft_revision"] += 1
                app.session_state["catalog_lab::job"] = last_job
                app.run()
                assert not app.exception and app.success
                assert app.dataframe and app.metric
                assert app.session_state["catalog_lab::draft"] == custom_spec
                app_runs += 1
        quota_after = lab_client.assistant_capabilities()["quota"]
        assert quota_before == quota_after, "Read-only acceptance changed AI reservation state"
    cleanup = _verify_timeout_cleanup() if worker_only else None
    return {"ok": True, "worker_only": worker_only, "recipes": results,
            "assembly_bindings": len(assembly_catalog()["components"]["adapters"]),
            "guide": read_guide()["metadata"],
            "timeout_tree_cleanup": cleanup,
            "workbench_profile_runs": app_runs, "model_calls": 0}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-only", action="store_true")
    args = parser.parse_args(argv)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        result = verify(worker_only=args.worker_only)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
