"""成本阶梯及原排程模型：同算法配对，分离验收 trace 与运行成本。

只有现有标准 Project 调用 run_cost_matrix，无私有 Solver CLI。
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import partial
from hashlib import sha256
from pathlib import Path
import statistics
import time
import json

import numpy as np

from benchmarks.transparency_core import (PairSpec, ProblemMeter, _timed, build_pair_solver,
    compare, json_value, run_pair)
from benchmarks.transparency_population import (FixedPopulationInitializer, PopulationReferenceKernel,
    project_population, specs as population_specs)
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import GaussianMutation, RepresentationPipeline

ROOT = Path(__file__).resolve().parents[1]


class TimedRepair:
    stateless = True

    def __init__(self, repair):
        self.operation = repair
        self.wall_s = self.cpu_s = 0.

    def repair(self, candidate, context=None):
        wall, cpu = time.perf_counter(), time.process_time()
        try:
            return self.operation(candidate)
        finally:
            self.wall_s += time.perf_counter() - wall
            self.cpu_s += time.process_time() - cpu


def _cpu_work(iterations):
    value = np.linspace(.1, .9, 256)
    for _ in range(iterations):
        value = np.sin(value) + .1
    return float(value[0])


def calibrate_cpu(target_ms):
    if target_ms <= 0:
        return 0
    _cpu_work(100)
    # Windows process CPU counters may tick at ~15 ms. A tiny calibration can
    # read zero and inflate the entire experiment by orders of magnitude.
    count = 2048
    while True:
        start = time.process_time()
        _cpu_work(count)
        elapsed = time.process_time() - start
        if elapsed >= .125:
            break
        count *= 2
    return max(1, round(target_ms / 1000 * count / elapsed))


def cost_problem(factory, *, iterations=0, wait_ms=0):
    problem = factory()
    original = problem.evaluate

    def evaluate(candidate):
        if iterations:
            _cpu_work(iterations)
        if wait_ms:
            time.sleep(wait_ms / 1000)
        return original(candidate)

    problem.evaluate = evaluate
    return problem


def numeric_reference(seed, steps, evaluate, *, initial, repair, sigma=.08,
                      record_trace=True):
    kernel = PopulationReferenceKernel("nsga2", seed, len(initial(seed)),
        initial_values=initial(seed), mutation_sigma=sigma)
    history, timings = [], []
    repair_meter = TimedRepair(repair)
    for _ in range(steps):
        wall, cpu = time.perf_counter(), time.process_time()
        meter = getattr(evaluate, "__self__", None)
        problem_before = (getattr(meter, "wall_s", 0.), getattr(meter, "cpu_s", 0.))
        old_repair = (repair_meter.wall_s, repair_meter.cpu_s)
        candidates = np.asarray([repair_meter.repair(x.copy()) for x in kernel.ask()])
        feedback = [evaluate(x.copy()) for x in candidates]
        kernel.tell(candidates, np.asarray([x[0] for x in feedback]), np.asarray([x[1] for x in feedback]))
        if record_trace:
            history.append({"state": kernel.project()})
        timings.append({"wall_s": time.perf_counter() - wall, "cpu_s": time.process_time() - cpu,
                        "problem_wall_s": getattr(meter, "wall_s", 0.) - problem_before[0],
                        "problem_cpu_s": getattr(meter, "cpu_s", 0.) - problem_before[1],
                        "repair_wall_s": repair_meter.wall_s - old_repair[0],
                        "repair_cpu_s": repair_meter.cpu_s - old_repair[1]})
    return {"state": kernel.project(), "trace": history, "iteration_timings": timings}


def numeric_adapter(seed, *, initial, sigma=.08):
    values = initial(seed)
    return NSGA2Adapter(population_size=len(values), offspring_size=len(values), crossover_rate=.9,
        initializer=FixedPopulationInitializer(values), mutator=GaussianMutation(sigma=sigma))


def numeric_pipeline(seed, *, repair):
    return RepresentationPipeline(repair=TimedRepair(repair))


def _initial_uniform(seed, *, size, dimension=8, high=1.):
    return np.random.default_rng(np.random.SeedSequence([seed, 7919])).uniform(0., high, (size, dimension))


def cost_spec(target_ms, *, size=8, steps=8, wait=False):
    if not np.isfinite(target_ms) or target_ms < 0:
        raise ValueError("evaluation cost must be finite and nonnegative")
    base = population_specs(population_size=size, steps=steps)[0]
    iterations = 0 if wait else calibrate_cpu(target_ms)
    initial = partial(_initial_uniform, size=size)
    repair = partial(np.clip, a_min=0., a_max=1.)
    return replace(base, name=f"{'wait' if wait else 'cpu'}_{target_ms:g}ms",
        make_problem=partial(cost_problem, base.make_problem, iterations=iterations,
                             wait_ms=target_ms if wait else 0),
        make_adapter=partial(numeric_adapter, initial=initial),
        make_pipeline=partial(numeric_pipeline, repair=repair),
        reference=partial(numeric_reference, initial=initial, repair=repair),
        metadata={**base.metadata, "cost_kind": "simulated_io_wait" if wait else "calibrated_fixed_numpy_cpu_work",
                  "target_ms": target_ms, "work_iterations": iterations,
                  "cost_injection": "no change to official objective output; actual cost measured, not assumed"})


def production_spec(resource_context, *, size=8, steps=8):
    # Reuse the original standard Case factory, rather than import its private
    # absolute-import modules or reimplement the domain model.
    from blackbase.project.runtime import build_case, load_case_builder
    project = ROOT / "examples/cases/production_scheduling"
    case = project / "cases/production_scheduling"
    bom, supply = case / "machine_material_mapping.csv", case / "SUPPLY.xlsx"
    if not bom.is_file() or not supply.is_file():
        raise FileNotFoundError("real production BOM/SUPPLY required; synthetic fallback forbidden")
    builder = load_case_builder(project, "production_scheduling", case_kind="solver")
    original = build_case(builder, resource_context=resource_context, component_overrides={"argv": [
        "--check", "--no-run-logs", "--no-bias", "--no-profile", "--no-decision-trace",
        "--machines", "22", "--materials", "157", "--days", "31", "--bom", str(bom),
        "--supply", str(supply), "--max-prod", "3000"]})
    problem = original.problem
    if Path(problem.data.bom_path).resolve() != bom.resolve() or Path(problem.data.supply_path).resolve() != supply.resolve():
        raise ValueError("production factory did not load the requested real files")
    repair = original.representation_pipeline.problem_repair.repair
    initial = partial(_initial_uniform, size=size, dimension=problem.dimension, high=3000.)
    hashes = {p.name: sha256(p.read_bytes()).hexdigest() for p in
              (bom, supply, case / "problem/production_problem.py", case / "pipeline/schedule_pipeline.py")}
    return PairSpec(name="production_nsga2", make_problem=partial(deepcopy, problem),
        make_adapter=partial(numeric_adapter, initial=initial, sigma=50.),
        make_pipeline=partial(numeric_pipeline, repair=repair),
        reference=partial(numeric_reference, initial=initial, repair=repair, sigma=50.),
        project=project_population, population_size=size, steps=steps,
        metadata={"family": "real_production_cost", "model": type(problem).__name__,
            "dimension": problem.dimension, "machines": problem.machines, "days": problem.days,
            "materials": problem.materials, "source_sha256": hashes, "synthetic_fallback": False,
            "supply": "original immutable arrivals; no date shifts or day0 inventory edits",
            "scope": "original domain model and supply repair; matched NSGA-II benchmark, not a replacement for full multi-agent/nested supply search"})


def measure(spec, seed, mode, *, context, checkpoint):
    step_trace, call_trace = mode == "full", mode != "lean"
    bare_meter = ProblemMeter(spec.make_problem(), record_calls=call_trace)
    bare, bare_time = _timed(lambda: spec.reference(seed, spec.steps, bare_meter.evaluate, record_trace=step_trace))
    solver, meter, trace, _ = build_pair_solver(spec, seed, resource_context=context,
        runtime_checkpoint=checkpoint, capture_trace=step_trace, record_calls=call_trace)
    trace.repair_meter = solver.representation_pipeline.problem_repair
    _, framework_time = _timed(lambda: solver.run(max_steps=spec.steps))
    state = json_value(spec.project(solver))
    checks = {"final_state": compare(json_value(bare["state"]), state),
              "actual_evaluations": compare(bare_meter.call_count, meter.call_count),
              "solver_evaluations": compare(meter.call_count, solver.evaluation_count),
              "commits": compare(spec.steps, trace.commits)}
    if call_trace:
        checks["evaluation_sequence"] = compare(bare_meter.records, meter.records)
    if step_trace:
        checks["commit_trace"] = compare(json_value(bare["trace"]), trace.trace)
    f_normal = [x for x in trace.attempt_timings if x["status"] == "committed"][1:]
    b_normal = bare["iteration_timings"][1:]
    normal = {"commits": len(f_normal), "evaluations": sum(x["evaluation_calls"] for x in f_normal)}
    for clock in ("wall_s", "cpu_s"):
        f = sum(x[clock] for x in f_normal)
        b = sum(x[clock] for x in b_normal)
        problem = sum(x[f"problem_{clock}"] for x in f_normal)
        repair_time = sum(x[f"repair_{clock}"] for x in f_normal)
        bare_problem = sum(x[f"problem_{clock}"] for x in b_normal)
        bare_repair = sum(x[f"repair_{clock}"] for x in b_normal)
        normal[clock] = {"framework": f, "reference": b, "difference": f-b,
            "difference_ms_per_evaluation": 1000*(f-b)/normal["evaluations"],
            "ratio": f/b if b else None, "framework_problem": problem,
            "framework_repair": repair_time, "reference_repair": bare_repair,
            "reference_problem": bare_problem, "framework_remainder": f-problem-repair_time,
            "reference_remainder": b-bare_problem-bare_repair,
            "extra_nonproblem_nonrepair": (f-problem-repair_time)-(b-bare_problem-bare_repair)}
    return {"status": "failed" if any(checks.values()) else "passed", "seed": seed, "mode": mode,
        "checks": checks, "evaluations": meter.call_count, "normal": normal,
        "framework": framework_time, "reference": bare_time,
        "state": state, "observer_self_time": {"wall_s": trace.observation_wall_s, "cpu_s": trace.observation_cpu_s},
        "scope": "remaining minimal timers/counters retained; no evidence, transaction or control disabled"}


def run_cost_matrix(options, *, context, checkpoint, work_dir):
    size, steps = int(options.get("population_size", 8)), int(options.get("steps", 8))
    seeds = list(options.get("seeds", [11, 29]))
    if size < 5 or steps < 3 or not seeds:
        raise ValueError("cost benchmark needs size>=5, steps>=3 and nonempty seeds")
    selected = [cost_spec(float(ms), size=size, steps=steps) for ms in options.get("cpu_ms", [0, 1, 10, 50])]
    selected += [cost_spec(float(ms), size=size, steps=steps, wait=True) for ms in options.get("wait_ms", [10])]
    if options.get("production", True):
        selected.append(production_spec(context, size=size, steps=steps))
    if not selected or len({spec.name for spec in selected}) != len(selected):
        raise ValueError("cost matrix needs nonempty unique fixtures")
    reports = []
    for spec in selected:
        qualification = run_pair(spec, seeds[0], recovery=True, resource_context=context,
                                 runtime_checkpoint=checkpoint, work_dir=work_dir)
        Path(work_dir).mkdir(parents=True, exist_ok=True)
        (Path(work_dir) / f"{spec.name}_qualification.json").write_text(
            json.dumps(qualification, ensure_ascii=False, indent=2), encoding="utf-8")
        if any(qualification[key]["status"] != "passed" for key in ("semantics", "quality", "recovery")):
            raise RuntimeError(f"cost fixture qualification failed: {spec.name}: {qualification}")
        measurements = []
        # Rotate mode order to avoid always charging first-run effects to full.
        modes = ("full", "no_step_trace", "lean")
        for index, seed in enumerate(seeds):
            for mode in (*modes[index % 3:], *modes[:index % 3]):
                checkpoint()
                measurements.append(measure(spec, seed, mode, context=context, checkpoint=checkpoint))
        paired = []
        for seed in seeds:
            rows = {r["mode"]: r for r in measurements if r["seed"] == seed}
            for mode in modes:
                if compare(rows["full"]["state"], rows[mode]["state"]):
                    raise ValueError("trace mode changed algorithm outcome")
            paired.append({"seed": seed, **{clock: {
                "step_trace_delta_s": rows["full"]["normal"][clock]["framework"] - rows["no_step_trace"]["normal"][clock]["framework"],
                "call_trace_delta_s": rows["no_step_trace"]["normal"][clock]["framework"] - rows["lean"]["normal"][clock]["framework"],
                "all_trace_delta_s": rows["full"]["normal"][clock]["framework"] - rows["lean"]["normal"][clock]["framework"]}
                for clock in ("wall_s", "cpu_s")}})
        reports.append({"name": spec.name, "metadata": json_value(spec.metadata), "qualification": qualification,
            "measurements": measurements, "paired_trace_effects": paired,
            "lean_normal_extra_ms_per_evaluation_median": statistics.median(
                r["normal"]["wall_s"]["difference_ms_per_evaluation"] for r in measurements if r["mode"] == "lean")})
        (Path(work_dir) / "cost_progress.json").write_text(json.dumps(
            {"complete": len(reports) == len(selected), "expected": [s.name for s in selected], "fixtures": reports},
            ensure_ascii=False, indent=2), encoding="utf-8")
    return {"mode": "costs", "fixtures": reports,
        "validation": {"status": "failed" if any(m["status"] != "passed" for r in reports for m in r["measurements"]) else "passed"},
        "method": "normal commits exclude bootstrap; signed paired deltas, never clipped to zero; tiny counter/timer overhead remains; CPU load and simulated I/O wait are separate; qualification and checkpoint excluded from timing"}
