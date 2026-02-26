from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from statistics import NormalDist

import numpy as np


def _load_data(
    *,
    case_dir: Path,
    bom_path: str | None,
    supply_path: str | None,
    machines: int,
    materials: int,
    days: int,
):
    prod_case_dir = (case_dir.parent / "production_scheduling").resolve()
    if str(prod_case_dir) not in sys.path:
        sys.path.insert(0, str(prod_case_dir))
    from refactor_data import load_production_data  # type: ignore

    data = load_production_data(
        base_dir=prod_case_dir,
        bom_path=Path(bom_path) if bom_path else None,
        supply_path=Path(supply_path) if supply_path else None,
        machines=int(machines),
        materials=int(materials),
        days=int(days),
        fallback=False,
    )
    return data


def _analyze_material_safety(
    *,
    bom_matrix: np.ndarray,
    supply_matrix: np.ndarray,
    machine_weights: np.ndarray,
    max_active_machines_per_day: int,
    max_production_per_machine: float,
    prob_confidence: float,
    prob_margin: float,
    weighted_margin: float,
    relational_robust_coef: float,
) -> dict[str, Any]:
    bom = np.asarray(bom_matrix, dtype=bool)
    supply = np.asarray(supply_matrix, dtype=float)
    materials, days = int(supply.shape[0]), int(supply.shape[1])

    cumulative_supply = np.cumsum(supply, axis=1)
    need_counts = np.sum(bom, axis=0).astype(int)
    daily_upper = (
        np.minimum(need_counts, int(max_active_machines_per_day)).astype(float)
        * float(max_production_per_machine)
    )
    cumulative_upper = np.outer(daily_upper, np.arange(1, days + 1, dtype=float))

    eps = 1e-9
    ratios = cumulative_supply / (cumulative_upper + eps)
    min_ratio = np.min(ratios, axis=1)
    bottleneck_day = np.argmin(ratios, axis=1).astype(int)

    strict_mask = cumulative_supply >= (cumulative_upper - 1e-9)
    strict_never_short = np.all(strict_mask, axis=1)

    # Probabilistic safety upper bound:
    # E[consumption] + z * std(consumption), with machine-level Bernoulli activity.
    # This approximates "weighted chance of not producing each machine".
    w = np.asarray(machine_weights, dtype=float).reshape(-1)
    if w.size != bom.shape[0]:
        w = np.ones(bom.shape[0], dtype=float)
    w = np.where(np.isfinite(w), w, 0.0)
    w = np.maximum(w, 0.0)
    if float(np.max(w)) > 0.0:
        p = w / float(np.max(w))
    else:
        p = np.zeros_like(w, dtype=float)
    p = np.clip(p, 0.0, 1.0)
    s = float(np.sum(p))
    if s > float(max_active_machines_per_day) > 0.0:
        p = p * (float(max_active_machines_per_day) / s)
    p = np.clip(p, 0.0, 1.0)

    u_jm = np.where(bom, float(max_production_per_machine), 0.0)  # (machines, materials)
    # Weighted upper bound (deterministic): machine j contributes a_j * cap.
    weighted_day_upper = np.sum(p[:, None] * u_jm, axis=0)
    weighted_day_upper = np.maximum(0.0, weighted_day_upper) * float(max(weighted_margin, 1e-9))
    cumulative_weighted_upper = np.outer(weighted_day_upper, np.arange(1, days + 1, dtype=float))
    weighted_mask = cumulative_supply >= (cumulative_weighted_upper - 1e-9)
    weighted_safe = np.all(weighted_mask, axis=1)

    mu_day = np.sum(p[:, None] * u_jm, axis=0)  # (materials,)
    var_day = np.sum((p * (1.0 - p))[:, None] * (u_jm ** 2), axis=0)  # (materials,)
    sigma_day = np.sqrt(np.maximum(var_day, 0.0))
    conf = float(np.clip(prob_confidence, 0.5001, 0.999999))
    z = float(NormalDist().inv_cdf(conf))
    day_prob_upper = np.maximum(0.0, mu_day + z * sigma_day) * float(max(prob_margin, 1e-9))
    cumulative_prob_upper = np.outer(day_prob_upper, np.arange(1, days + 1, dtype=float))
    prob_mask = cumulative_supply >= (cumulative_prob_upper - 1e-9)
    probabilistic_safe = np.all(prob_mask, axis=1)

    # Relational expected upper bound (cumulative-by-day):
    # For target material a at day t, for each machine j that needs a:
    #   bottleneck_j(t) = min((t+1)*cap, min_{m in req(j)\{a}} S_m(t))
    #   expected_use_a(t) += p_j * bottleneck_j(t)
    # Then multiply robust coefficient.
    # This is stricter than total-supply-only relational bound.
    machine_day_cap = float(max_production_per_machine)
    day_idx = np.arange(1, days + 1, dtype=float)
    machine_cum_cap = machine_day_cap * day_idx  # (days,)
    relational_cum_upper = np.zeros((materials, days), dtype=float)
    rel_coef = float(max(relational_robust_coef, 0.0))
    for a in range(materials):
        js = np.where(bom[:, a])[0]
        if js.size == 0:
            relational_cum_upper[a, :] = 0.0
            continue
        exp_use_t = np.zeros(days, dtype=float)
        for j in js:
            req = np.where(bom[j])[0]
            others = req[req != a]
            if others.size == 0:
                bottleneck_t = machine_cum_cap.copy()
            else:
                bottleneck_by_other = np.min(cumulative_supply[others, :], axis=0)
                bottleneck_t = np.minimum(machine_cum_cap, bottleneck_by_other)
            bottleneck_t = np.clip(bottleneck_t, 0.0, None)
            exp_use_t += float(p[j]) * bottleneck_t
        relational_cum_upper[a, :] = rel_coef * exp_use_t
    relational_safe_mask = cumulative_supply >= (relational_cum_upper - 1e-9)
    relational_safe = np.all(relational_safe_mask, axis=1)
    relational_ratio = np.min(cumulative_supply / (relational_cum_upper + 1e-9), axis=1)
    relational_day_upper = np.diff(
        np.concatenate([np.zeros((materials, 1), dtype=float), relational_cum_upper], axis=1),
        axis=1,
    )

    return {
        "strict_never_short": strict_never_short,
        "min_ratio": min_ratio,
        "bottleneck_day": bottleneck_day,
        "need_counts": need_counts,
        "daily_upper": daily_upper,
        "weighted_safe": weighted_safe,
        "weighted_day_upper": weighted_day_upper,
        "weighted_margin": float(weighted_margin),
        "probabilistic_safe": probabilistic_safe,
        "probability_day_upper": day_prob_upper,
        "probability_confidence": conf,
        "probability_margin": float(prob_margin),
        "relational_safe": relational_safe,
        "relational_expected_upper": np.sum(relational_day_upper, axis=1),
        "relational_cumulative_upper": relational_cum_upper,
        "relational_day_upper": relational_day_upper,
        "relational_ratio": relational_ratio,
        "relational_robust_coef": float(rel_coef),
        "machine_activation_prob": p,
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Compute material blacklist that can never be short under worst-case upper bound."
    )
    p.add_argument("--bom", type=str, default=None)
    p.add_argument("--supply", type=str, default=None)
    p.add_argument("--machines", type=int, default=22)
    p.add_argument("--materials", type=int, default=157)
    p.add_argument("--days", type=int, default=31)
    p.add_argument("--max-active-machines", type=int, default=8)
    p.add_argument("--max-production-per-machine", type=float, default=3000.0)
    p.add_argument(
        "--practical-margin",
        type=float,
        default=1.10,
        help="Practical-safe threshold on min cumulative ratio (e.g. 1.10 = 10%% extra margin).",
    )
    p.add_argument(
        "--mode",
        type=str,
        default="strict",
        choices=["strict", "practical", "weighted", "probabilistic", "relational"],
        help="strict: provably never-short; practical: min_ratio >= practical_margin; weighted: weight-based upper bound; probabilistic: weighted confidence bound; relational: relation-aware expected upper bound.",
    )
    p.add_argument(
        "--weighted-margin",
        type=float,
        default=1.00,
        help="Extra safety multiplier on weighted day upper bound (>=1.0 recommended).",
    )
    p.add_argument(
        "--prob-confidence",
        type=float,
        default=0.95,
        help="Confidence level for probabilistic mode (e.g. 0.95/0.99).",
    )
    p.add_argument(
        "--prob-margin",
        type=float,
        default=1.00,
        help="Extra safety multiplier on probabilistic day upper bound (>=1.0 recommended).",
    )
    p.add_argument(
        "--relational-robust-coef",
        type=float,
        default=1.00,
        help="Robust coefficient for relational expected upper bound (>=1.0 conservative, <1.0 aggressive).",
    )
    p.add_argument(
        "--out-blacklist",
        type=str,
        default="material_blacklist_autogen.txt",
        help="Output text file with 1-based material ids, one per line.",
    )
    p.add_argument(
        "--out-report",
        type=str,
        default="material_blacklist_report.json",
        help="Output JSON report with per-material diagnostics.",
    )
    args = p.parse_args(argv)

    case_dir = Path(__file__).resolve().parent
    data = _load_data(
        case_dir=case_dir,
        bom_path=args.bom,
        supply_path=args.supply,
        machines=int(args.machines),
        materials=int(args.materials),
        days=int(args.days),
    )

    stats = _analyze_material_safety(
        bom_matrix=np.asarray(data.bom_matrix, dtype=bool),
        supply_matrix=np.asarray(data.supply_matrix, dtype=float),
        machine_weights=np.asarray(data.machine_weights, dtype=float),
        max_active_machines_per_day=int(args.max_active_machines),
        max_production_per_machine=float(args.max_production_per_machine),
        prob_confidence=float(args.prob_confidence),
        prob_margin=float(args.prob_margin),
        weighted_margin=float(args.weighted_margin),
        relational_robust_coef=float(args.relational_robust_coef),
    )

    strict = np.asarray(stats["strict_never_short"], dtype=bool)
    min_ratio = np.asarray(stats["min_ratio"], dtype=float)
    bottleneck_day = np.asarray(stats["bottleneck_day"], dtype=int)
    need_counts = np.asarray(stats["need_counts"], dtype=int)
    daily_upper = np.asarray(stats["daily_upper"], dtype=float)
    weighted_safe = np.asarray(stats["weighted_safe"], dtype=bool)
    weighted_day_upper = np.asarray(stats["weighted_day_upper"], dtype=float)
    probabilistic_safe = np.asarray(stats["probabilistic_safe"], dtype=bool)
    prob_day_upper = np.asarray(stats["probability_day_upper"], dtype=float)
    relational_safe = np.asarray(stats["relational_safe"], dtype=bool)
    relational_expected_upper = np.asarray(stats["relational_expected_upper"], dtype=float)
    relational_ratio = np.asarray(stats["relational_ratio"], dtype=float)

    practical = min_ratio >= float(args.practical_margin)
    if args.mode == "strict":
        selected = strict
    elif args.mode == "weighted":
        selected = weighted_safe
    elif args.mode == "probabilistic":
        selected = probabilistic_safe
    elif args.mode == "relational":
        selected = relational_safe
    else:
        selected = practical

    ids_1based = (np.where(selected)[0] + 1).astype(int).tolist()
    blacklist_path = (case_dir / args.out_blacklist).resolve()
    report_path = (case_dir / args.out_report).resolve()

    with open(blacklist_path, "w", encoding="utf-8") as f:
        for mid in ids_1based:
            f.write(f"{mid}\n")

    records = []
    for i in range(len(min_ratio)):
        records.append(
            {
                "material_id": int(i + 1),
                "strict_never_short": bool(strict[i]),
                "practical_safe": bool(practical[i]),
                "min_ratio": float(min_ratio[i]),
                "bottleneck_day": int(bottleneck_day[i]),
                "need_machine_count": int(need_counts[i]),
                "daily_upper_bound": float(daily_upper[i]),
                "weighted_safe": bool(weighted_safe[i]),
                "weighted_day_upper_bound": float(weighted_day_upper[i]),
                "probabilistic_safe": bool(probabilistic_safe[i]),
                "probability_day_upper_bound": float(prob_day_upper[i]),
                "relational_safe": bool(relational_safe[i]),
                "relational_expected_upper": float(relational_expected_upper[i]),
                "relational_ratio": float(relational_ratio[i]),
            }
        )

    payload = {
        "mode": str(args.mode),
        "practical_margin": float(args.practical_margin),
        "machines": int(args.machines),
        "materials": int(args.materials),
        "days": int(args.days),
        "max_active_machines": int(args.max_active_machines),
        "max_production_per_machine": float(args.max_production_per_machine),
        "selected_count": int(len(ids_1based)),
        "selected_material_ids": ids_1based,
        "strict_count": int(np.sum(strict)),
        "practical_count": int(np.sum(practical)),
        "weighted_count": int(np.sum(weighted_safe)),
        "weighted_margin": float(stats["weighted_margin"]),
        "probabilistic_count": int(np.sum(probabilistic_safe)),
        "probability_confidence": float(stats["probability_confidence"]),
        "probability_margin": float(stats["probability_margin"]),
        "relational_count": int(np.sum(relational_safe)),
        "relational_robust_coef": float(stats["relational_robust_coef"]),
        "records": records,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[ok] mode={args.mode} selected={len(ids_1based)} / {len(min_ratio)}")
    print(
        f"[ok] strict={int(np.sum(strict))}, practical@{args.practical_margin:.2f}={int(np.sum(practical))}, "
        f"weighted@margin={float(args.weighted_margin):.3f}={int(np.sum(weighted_safe))}, "
        f"probabilistic@conf={float(args.prob_confidence):.3f} margin={float(args.prob_margin):.3f}={int(np.sum(probabilistic_safe))}, "
        f"relational@coef={float(args.relational_robust_coef):.3f}={int(np.sum(relational_safe))}"
    )
    print(f"[ok] blacklist={blacklist_path}")
    print(f"[ok] report={report_path}")
    if ids_1based:
        show = ", ".join(map(str, ids_1based[:20]))
        print(f"[ok] sample_ids={show}{' ...' if len(ids_1based) > 20 else ''}")


if __name__ == "__main__":
    main()
