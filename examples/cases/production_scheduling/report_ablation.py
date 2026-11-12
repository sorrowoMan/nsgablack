"""Read-only metrics over formally published raw observations; no solver loop."""
import io
import json
from pathlib import Path

import numpy as np

from blackbase.resources import ArtifactBinding, ArtifactPublisher


def read_observations(project, project_run_id, expected_budget):
    path = Path(project) / ".blackbase/runs" / project_run_id / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["status"] != "ok" or len(manifest["cases"]) != 1:
        raise ValueError("ablation requires a successful single-Case Project manifest")
    case = manifest["cases"][0]["result"]
    binding = ArtifactBinding.from_dict({"ref": case["artifact_refs"]["ablation_observations"],
                                        "publication": case["artifact_publications"]["ablation_observations"]})
    reader = ArtifactPublisher.from_resource_context(case["request"]["resource_context"],
        project_run_id=case["identity"]["project_run_id"], case_run_id=case["identity"]["case_run_id"])
    with np.load(io.BytesIO(reader.read_verified(binding)), allow_pickle=False) as data:
        arrays = {k: data[k].copy() for k in data.files}
    meta = dict(binding.ref.metadata)
    n = len(arrays["raw_violations"])
    if (n != expected_budget or case["output"]["report"]["evaluation_count"] != n
            or arrays["raw_objectives"].shape != (n, 4)
            or arrays["batch_counts"].sum() != n
            or arrays["cumulative_evaluations"][-1] != n
            or len(set(arrays["event_ids"].tolist())) != len(arrays["event_ids"])
            or not np.isfinite(arrays["raw_objectives"]).all()
            or not np.isfinite(arrays["raw_violations"]).all()):
        raise ValueError("ablation observation rows/budget/event identities do not reconcile")
    grant = case["resource_usage"]["binding"]["effective"]["resources"]
    if grant["threads"] != 1 or grant["gpus"] != 0:
        raise ValueError("ablation grant must remain single-CPU/no-GPU")
    return {"metadata": meta, "arrays": arrays, "elapsed_seconds": case["elapsed_seconds"],
        "termination_reason": case["output"]["termination_reason"], "binding": binding.as_dict(),
        "identity": case["identity"]}


def front(values):
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
    values = np.asarray(values, dtype=float)
    if not len(values):
        return values
    return values[NonDominatedSorting().do(values, only_non_dominated_front=True)]


def summarize(observations):
    from pymoo.indicators.hv import HV
    from pymoo.indicators.igd import IGD
    if not observations:
        raise ValueError("no successful observations")
    by_seed = {}
    for row in observations:
        by_seed.setdefault(row["metadata"]["seed"], []).append(row)
    for seed, rows in by_seed.items():
        arms = [r["metadata"]["arm"] for r in rows]
        if len(arms) != 3 or set(arms) != {"constructive", "moead", "directional"}:
            raise ValueError(f"comparison requires exactly three distinct arms for seed={seed}")
        if len({len(r["arrays"]["raw_violations"]) for r in rows}) != 1:
            raise ValueError(f"evaluation budgets differ across arms for seed={seed}")
        if len({r["metadata"]["initial_values_sha256"] for r in rows}) != 1:
            raise ValueError(f"initial candidate values differ across arms for seed={seed}")
        if {r["metadata"]["initial_count"] for r in rows} != {48}:
            raise ValueError("all arms must start with exactly 48 evaluated candidates")
        initial = rows[0]["arrays"]["raw_objectives"][:48]
        for r in rows:
            if not np.array_equal(initial, r["arrays"]["raw_objectives"][:48]):
                raise ValueError("initial raw feedback differs across arms")
            if not np.array_equal(rows[0]["arrays"]["raw_violations"][:48], r["arrays"]["raw_violations"][:48]):
                raise ValueError("initial raw violations differ across arms")
            if not np.any(r["arrays"]["raw_violations"][:48] <= 1e-9):
                raise ValueError("initial population has no feasible observation for comparison")
    # One disclosed common scale across ALL arms/seeds, never one scale per arm.
    feasible = [r["arrays"]["raw_objectives"][r["arrays"]["raw_violations"] <= 1e-9] for r in observations]
    union = np.vstack(feasible)
    low, high = union.min(axis=0), union.max(axis=0)
    scale = np.where(high > low, high - low, 1.0)
    reference = front(np.unique((union - low) / scale, axis=0))
    hv = HV(ref_point=np.full(4, 1.1))
    igd = IGD(reference)
    results = []
    for row in observations:
        arrays, meta = row["arrays"], row["metadata"]
        f, v = arrays["raw_objectives"], arrays["raw_violations"]
        good = f[v <= 1e-9]
        initial = f[:48][v[:48] <= 1e-9]
        initial_front = front((initial - low) / scale)
        observed_front = front((good - low) / scale)
        common_best = max(float(-r["arrays"]["raw_objectives"][r["arrays"]["raw_violations"] <= 1e-9, 0].min())
                          for r in by_seed[meta["seed"]])
        high_output = good[-good[:, 0] >= 0.9 * common_best]
        results.append({"arm": meta["arm"], "seed": meta["seed"], "evaluations": len(f),
            "initial_values_sha256": meta["initial_values_sha256"],
            "initial_best_output": float(-initial[:, 0].min()), "best_output": float(-good[:, 0].min()),
            "output_gain_after_initial": float(initial[:, 0].min() - good[:, 0].min()),
            "hard_feasible_fraction": float(np.mean(v <= 1e-9)),
            "unique_numeric_candidates": len(set(arrays["numeric_hashes"].tolist())),
            "initial_hv": float(hv.do(initial_front)), "observed_hv": float(hv.do(observed_front)),
            "hv_gain_after_initial": float(hv.do(observed_front) - hv.do(initial_front)),
            "empirical_igd": float(igd.do(observed_front)),
            "best_daily_cv_at_90pct_common_output": None if not len(high_output) else float(np.sqrt(high_output[:, 1].min())),
            "common_output_threshold": 0.9 * common_best,
            "case_elapsed_seconds": row["elapsed_seconds"],
            "observer_seconds": meta["observer_seconds"], "packing_seconds": meta["packing_seconds"],
            "termination_reason": row["termination_reason"], "artifact": row["binding"]})
    return {"schema": "production.ablation_comparison/v1", "results": results,
        "initial_candidates_equal_within_seed": True, "normalization_low": low.tolist(), "normalization_high": high.tolist(),
        "hv_reference_point": [1.1]*4, "empirical_reference_front": reference.tolist(),
        "measurement": "pymoo HV/IGD on all evaluated raw feasible vectors from committed batches",
        "reference_scope": "pooled empirical nondominated observations, not a true production Pareto reference set",
        "numeric_uniqueness_scope": "diagnostic only; equal values do not merge candidate identities or budgets",
        "stability_threshold_scope": "reported comparison policy, not a new Problem constraint",
        "limitations": "fixed budget and initial values; no literature/global-optimality or multi-seed claim without repeated seeds"}
