"""透明性测量器：只调用 pymoo 官方指标与非支配筛选，不实现 HV/IGD。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

REFERENCE_ROOT = Path(__file__).resolve().parent / "reference_sets"
PYMOO_VERSION = "0.6.2"


def load_reference(problem, *, root=REFERENCE_ROOT):
    import pymoo

    manifest = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    if pymoo.__version__ != manifest["pymoo_version"]:
        raise ValueError("reference set and installed pymoo versions differ")
    entry = manifest["sets"][problem]
    path = Path(root) / entry["file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError(f"official reference set checksum mismatch: {problem}")
    values = np.loadtxt(path, ndmin=2)
    if list(values.shape) != entry["shape"] or not np.isfinite(values).all():
        raise ValueError(f"invalid official reference set: {problem}")
    return values, {**entry, "pymoo_version": pymoo.__version__, "path": str(path)}


def measure(problem, objectives, violations, *, root=REFERENCE_ROOT):
    # These are the ONLY implementations of the metrics used by this suite.
    from pymoo.indicators.hv import HV
    from pymoo.indicators.igd import IGD
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

    reference, source = load_reference(problem, root=root)
    f = np.asarray(objectives, dtype=float)
    v = np.asarray(violations, dtype=float).reshape(-1)
    if f.ndim != 2 or f.shape[1] != reference.shape[1] or len(v) != len(f):
        raise ValueError("metric inputs must be aligned final member objectives/violations")
    if not np.isfinite(f).all() or not np.isfinite(v).all():
        raise ValueError("non-finite final member feedback cannot be measured")
    feasible = f[v <= 1e-10]
    if not len(feasible):
        return {"hv": 0.0, "igd": None, "igd_status": "undefined_no_feasible_members",
                "feasible_members": 0, "front_members": 0, "reference": source}
    front = feasible[NonDominatedSorting().do(feasible, only_non_dominated_front=True)]
    return {"hv": float(HV(ref_point=np.asarray(source["hv_reference_point"])).do(front)),
            "igd": float(IGD(reference).do(front)), "igd_status": "measured",
            "feasible_members": len(feasible), "front_members": len(front), "reference": source}


def quality(spec, reference_result, framework_state, reference_calls, framework_calls):
    from benchmarks.transparency_core import compare

    raw_error = compare([r["f"] for r in reference_calls], [r["f"] for r in framework_calls])
    result = {"status": "failed" if raw_error else "passed",
              "raw_objectives_equal": raw_error is None,
              "metric_problem": spec.metric_problem}
    if raw_error:
        result["raw_objectives_mismatch"] = raw_error
    if spec.metric_problem is None:
        result.update(measurement="algorithm-specific state and evaluated raw objectives",
                      multiobjective_metrics="not_applicable_to_this_fixture")
        return result
    bare_state = reference_result["state"]
    left = measure(spec.metric_problem, bare_state["objectives"], bare_state["violations"])
    right = measure(spec.metric_problem, framework_state["objectives"], framework_state["violations"])
    deltas = {key: (None if left[key] is None or right[key] is None else right[key] - left[key])
              for key in ("hv", "igd")}
    disagreement = compare({k: left[k] for k in ("hv", "igd")}, {k: right[k] for k in ("hv", "igd")})
    result.update(measurement="pymoo.indicators.HV / IGD on feasible nondominated final members",
                  reference=left, framework=right, deltas=deltas,
                  equal_population_size=len(bare_state["objectives"]) == len(framework_state["objectives"]),
                  reference_population_size=len(bare_state["objectives"]),
                  framework_population_size=len(framework_state["objectives"]))
    if disagreement or not result["equal_population_size"]:
        result["status"] = "failed"
        result["metric_mismatch"] = disagreement
    return result
