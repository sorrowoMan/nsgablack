"""Reconcile delivered archive candidates against existing raw evidence, without evaluation."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT.parents[2]) not in sys.path:
    sys.path.insert(0, str(ROOT.parents[2]))

import numpy as np
from blackbase.resources import ArtifactBinding, ArtifactPublisher
from blackbase.types import PopulationSnapshot
from examples.cases.production_scheduling.report_ablation import front, read_observations
from examples.cases.production_scheduling.run_quality_benchmark import _write


def numeric_digest(values):
    values = np.asarray(values, dtype="<f8", order="C")
    return hashlib.sha256(str(values.shape).encode("ascii") + b"\0" + values.tobytes()).hexdigest()


def delivered_raw(snapshot, observations):
    """Identity chooses the evidence row; numeric digest only verifies that identity."""
    a = observations["arrays"]
    values = []
    for token, candidate in zip(snapshot.candidate_tokens, snapshot.candidates):
        indices = np.flatnonzero(a["candidate_tokens"] == token)
        if not len(indices):
            raise ValueError("delivered candidate has no matching raw evaluation identity")
        digest = numeric_digest(candidate.as_array())
        if any(a["numeric_hashes"][i] != digest for i in indices):
            raise ValueError("delivered token numeric version does not match raw evidence")
        first = int(indices[0])
        for index in indices:
            if (not np.array_equal(a["raw_objectives"][index], a["raw_objectives"][first])
                    or a["raw_violations"][index] != a["raw_violations"][first]):
                raise ValueError("repeated identity has ambiguous raw feedback")
        if a["raw_violations"][first] <= 1e-9:
            values.append(a["raw_objectives"][first])
    if not values:
        raise ValueError("delivered archive has no raw hard-feasible candidate")
    return np.asarray(values)


def main(argv=None):
    import argparse
    from pymoo.indicators.hv import HV
    from pymoo.indicators.igd import IGD
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    folder = args.run_dir.resolve()
    comparison = json.loads((folder / "comparison.json").read_text(encoding="utf-8"))
    study = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    low, high = np.array(comparison["normalization_low"]), np.array(comparison["normalization_high"])
    scale = np.where(high > low, high-low, 1.)
    hv = HV(ref_point=np.array(comparison["hv_reference_point"]))
    igd = IGD(np.array(comparison["empirical_reference_front"]))
    rows = []
    for job in study["jobs"]:
        path = ROOT / ".blackbase/runs" / job["project_run_id"] / "manifest.json"
        case = json.loads(path.read_text())["cases"][0]["result"]
        binding = ArtifactBinding.from_dict({"ref": case["artifact_refs"]["pareto_front"],
            "publication": case["artifact_publications"]["pareto_front"]})
        reader = ArtifactPublisher.from_resource_context(case["request"]["resource_context"],
            project_run_id=case["identity"]["project_run_id"], case_run_id=case["identity"]["case_run_id"])
        snapshot = PopulationSnapshot.from_dict(json.loads(reader.read_verified(binding)))
        good = delivered_raw(snapshot, read_observations(ROOT, job["project_run_id"], 240))
        normalized = front((good-low)/scale)
        exports = ROOT / "results/ablation" / job["session"] / job["group"] / "exports"
        audits = {}
        for label in ("production", "stability", "balanced"):
            audit_path = exports / f"plan_{label}_src-SUPPLY.audit.json"
            csv_path = audit_path.with_suffix("").with_suffix(".csv")
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            if not audit["feasible"] or audit["objectives"][0] != -audit["production"]["total"]:
                raise ValueError("exported plan audit is infeasible or inconsistent")
            audits[label] = {"csv": str(csv_path), "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                "audit": str(audit_path), "objectives": audit["objectives"],
                "total_output": audit["production"]["total"], "daily_cv": audit["production"]["daily_cv"]}
        rows.append({"policy": job["policy"], "seed": job["seed"], "archive_count": len(good),
            "delivered_raw_hv": float(hv.do(normalized)), "delivered_raw_igd": float(igd.do(normalized)),
            "archive_best_output": float(-good[:,0].min()), "exports": audits,
            "archive_binding": binding.as_dict()})
    target = folder / "delivered_comparison.json"
    if target.exists():
        raise FileExistsError("preserve prior delivered comparison")
    _write(target, {"results": rows, "reporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "published Pareto archive, not algorithm-owned final population; raw feedback joined by exact token and checked by numeric digest",
        "evaluation_policy": "no new Problem calls in this report; CSV audits reuse existing post-search export reports, excluded from search budget"})
    print(json.dumps({"report": str(target), "results": [
        {k:v for k,v in r.items() if k not in {"archive_binding", "exports"}} for r in rows]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
