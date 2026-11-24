"""透明性标准 Case 的共享工厂；编排、授权和发布沿用 BlackBase。"""
from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import json
import os
import tempfile
import threading
import time

from blackbase.project import CaseRunRequest
from blackbase.resources import ResourceContext

from benchmarks.transparency_core import ProblemMeter, compare, json_value, run_pair


DEFAULT_NAMES = ("nsga2_zdt1", "sa", "cmaes", "bayesian_optimization", "map_elites")


@contextmanager
def _artifact_temp():
    # Diagnostic runs keep serializer scratch inside their writable Project.
    # The host sandbox TEMP can be a read-only Windows app-container path.
    directory = Path(__file__).resolve().parents[1] / "examples" / "cases" / "algorithm_transparency" / ".blackbase" / "tmp"
    directory.mkdir(parents=True, exist_ok=True)
    previous = tempfile.tempdir
    tempfile.tempdir = str(directory)
    try:
        yield
    finally:
        tempfile.tempdir = previous


def _registry(*, population_size=10, steps=6):
    from benchmarks.transparency_registry import specs
    return {spec.name: spec for spec in specs(population_size=int(population_size), steps=int(steps))}


def bare_report(spec, seed):
    meter = ProblemMeter(spec.make_problem())
    result = spec.reference(int(seed), int(spec.steps), meter.evaluate)
    return json_value({"name": spec.name, "seed": int(seed), "steps": spec.steps,
        "state": result["state"], "trace": [{"state": row["state"]} for row in result["trace"]],
        "calls": meter.records, "evaluations": len(meter.records)})


class TransparencyCase:
    """A benchmark Case delegates Solver lifecycle to each registered PairSpec."""
    def __init__(self, case_name, options, resource_context):
        self.case_name, self.options = str(case_name), dict(options)
        self.resource_context = ResourceContext.from_mapping(resource_context or {})
        self.case_runtime = None
        self.component_override_audit = {"config": json_value(self.options)}

    def set_resource_context(self, context):
        self.resource_context = ResourceContext.from_mapping(context)
        return self

    def get_resource_context(self):
        return self.resource_context

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        return self

    def _matrix(self):
        registry = _registry(population_size=self.options.get("population_size", 10), steps=self.options.get("steps", 6))
        requested = self.options.get("names", DEFAULT_NAMES)
        names = list(registry) if requested == "all" else list(requested)
        seeds = list(self.options.get("seeds", [11]))
        if not names or not seeds:
            return {"mode": "matrix", "rows": [], "names": names, "seeds": seeds,
                "validation": {"status": "failed", "failures": [{"section": "request", "status": "failed",
                    "error": "transparency matrix requires nonempty names and seeds"}]}}
        unknown = [name for name in names if name not in registry]
        if unknown:
            raise ValueError(f"unknown transparency PairSpecs: {unknown}")
        identity = self.case_runtime.identity
        output_root = Path(self.options.get("output_dir") or Path(__file__).resolve().parents[1]
            / "examples" / "cases" / "algorithm_transparency" / "results")
        safe_id = identity.case_run_id.replace(":", "_")
        work_dir = output_root / safe_id
        rows = []
        for name in names:
            for seed in seeds:
                self.case_runtime.checkpoint()
                rows.append(run_pair(registry[name], seed=int(seed), recovery=bool(self.options.get("recovery", True)),
                    resource_context=self.resource_context, work_dir=work_dir,
                    runtime_checkpoint=self.case_runtime.checkpoint))
                self.case_runtime.checkpoint()
        required = set(self.options.get("required_sections", ("semantics", "quality")))
        if bool(self.options.get("recovery", True)):
            required.add("recovery")
        optional_unsupported = set(self.options.get("allow_unsupported", ()))
        failures = []
        for row in rows:
            for section in ("semantics", "quality", "overhead", "recovery"):
                status = row[section]["status"]
                if status == "failed" or (status == "unsupported" and section in required and section not in optional_unsupported):
                    failures.append({"name": row["name"], "seed": row["seed"], "section": section,
                                     "status": status, "detail": row[section]})
        return {"mode": "matrix", "rows": rows, "names": names,
                "population_profile": {"population_size": self.options.get("population_size", 10),
                                       "steps": self.options.get("steps", 6)},
                "passed_semantics": sum(row["semantics"]["status"] == "passed" for row in rows),
                "failed_semantics": sum(row["semantics"]["status"] == "failed" for row in rows),
                "validation": {"status": "failed" if failures else "passed", "failures": failures,
                    "required_sections": sorted(required), "allow_unsupported": sorted(optional_unsupported)}}

    def _bare(self):
        spec = _registry()[str(self.options.get("name", "cmaes"))]
        return {"mode": "bare", "semantic": bare_report(spec, int(self.options.get("seed", 11)))}

    def _nested(self):
        name, seed = str(self.options.get("name", "cmaes")), int(self.options.get("seed", 11))
        direct = bare_report(_registry()[name], seed)
        request = CaseRunRequest(project_name=self.case_runtime.request.project_name,
            stage_name="nested_transparency", case_name="bare_inner", case_kind="solver",
            resource_request={"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
            component_overrides={"config": {"mode": "matrix", "names": [name], "seeds": [seed], "recovery": False}},
            metadata={"purpose": "direct bare reference versus an actual Solver in a nested authorized Case"})
        child = self.case_runtime.invoke(request)
        child.raise_for_failure("nested bare benchmark Case failed")
        row = child.output["rows"][0]
        if any(row[section]["status"] != "passed" for section in ("semantics", "quality")):
            raise RuntimeError("nested Solver did not pass its semantics and quality checks")
        observed = row["semantics"]
        nested = json_value({"name": row["name"], "seed": row["seed"], "steps": row["steps"],
            "state": observed["framework_state"], "trace": observed["framework_trace"],
            "calls": observed["framework_calls"], "evaluations": observed["framework_evaluations"]})
        mismatch = compare(direct, nested)
        return {"mode": "nested", "semantic": nested, "direct": direct,
            "comparison": {"status": "failed" if mismatch else "passed", "mismatch": mismatch},
            "child_identity": child.identity.as_dict(), "child_resource_context": child.request.resource_context,
            "child_resource_binding": child.resource_usage.get("binding", {}),
            "child_artifact_refs": {key: ref.as_dict() for key, ref in child.artifact_refs.items()},
            "child_publications": {key: receipt.as_dict() for key, receipt in child.artifact_publications.items()}}

    def run(self):
        with _artifact_temp():
            return self._run()

    def _run(self):
        if self.case_runtime is None:
            raise RuntimeError("TransparencyCase requires the formal Project CaseRuntimeContext")
        started = time.time()
        mode = str(self.options.get("mode", "matrix"))
        if mode == "matrix":
            content = self._matrix()
        elif mode == "bare":
            content = self._bare()
        elif mode == "nested":
            content = self._nested()
        elif mode == "costs":
            from benchmarks.transparency_costs import run_cost_matrix
            directory = Path(__file__).resolve().parents[1] / "examples/cases/algorithm_transparency/results" / self.case_runtime.identity.case_run_id.replace(":", "_")
            directory.mkdir(parents=True, exist_ok=True)
            content = run_cost_matrix(self.options, context=self.resource_context,
                checkpoint=self.case_runtime.checkpoint, work_dir=directory)
        elif mode == "modification_tasks":
            from benchmarks.modification_tasks import run
            content = run(self.options, context=self.resource_context, checkpoint=self.case_runtime.checkpoint)
        elif mode == "classical_quality":
            from benchmarks.classical_quality import run
            directory = Path(__file__).resolve().parents[1] / "examples/cases/algorithm_transparency/results" / self.case_runtime.identity.case_run_id.replace(":", "_")
            content = run(self.options, context=self.resource_context,checkpoint=self.case_runtime.checkpoint,work_dir=directory)
        elif mode == "quality":
            from benchmarks.quality_suite import run as quality_run
            content = quality_run(self.options)
        elif mode == "fusion":
            from benchmarks.fusion_suite import run as fusion_run
            content = fusion_run(self.options)
        elif mode == "single_objective":
            from benchmarks.single_objective_suite import run as single_run
            content = single_run(self.options)
        else:
            raise ValueError(f"unknown transparency Case mode: {mode}")
        report = json_value({**content, "case": self.case_name, "started_at": started, "finished_at": time.time(),
            "pid": os.getpid(), "thread_id": threading.get_ident(),
            "identity": self.case_runtime.identity.as_dict(), "resource_context": self.resource_context.as_dict(),
            "runtime_control": "parent Case checkpoint is delegated to each internal Solver; shared Case control owner/cache",
            "solver_evidence_scope": "Solver-local stores; only aggregate report is published as a formal Case Artifact",
            "resource_binding": getattr(self, "resource_binding_audit", {})})
        validation = report.get("validation", report.get("comparison", {}))
        if validation.get("status") == "failed":
            output_root = Path(self.options.get("output_dir") or Path(__file__).resolve().parents[1]
                / "examples" / "cases" / "algorithm_transparency" / "results")
            directory = output_root / self.case_runtime.identity.case_run_id.replace(":", "_")
            directory.mkdir(parents=True, exist_ok=True)
            evidence = directory / "failed_report.json"
            evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            raise RuntimeError(f"transparency validation failed; local evidence: {evidence}")
        ref = self.case_runtime.publish_artifact("report", report, serializer="json",
            kind="algorithm-transparency-evidence", metadata={"semantic_owner": "nsgablack", "mode": mode})
        return {**report, "artifact_refs": {"report": ref.as_dict()}}


def make_benchmark_case(case_name, *, mode="matrix", defaults=None, config=None,
                        resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    options = {"mode": mode, **dict(defaults or {}), **dict(config or {}), **dict(overrides.pop("config", {}))}
    if overrides:
        raise ValueError(f"unsupported transparency component overrides: {sorted(overrides)}")
    return TransparencyCase(case_name, options, resource_context)


__all__ = ["TransparencyCase", "bare_report", "make_benchmark_case"]
