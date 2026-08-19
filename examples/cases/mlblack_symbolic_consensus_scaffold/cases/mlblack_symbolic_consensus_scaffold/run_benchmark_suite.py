# -*- coding: utf-8 -*-
"""Run the five known-relation benchmarks through the nsgablack L2/L3 orchestrator.

This is the formal suite runner for the standard
``mlblack_symbolic_consensus_scaffold``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from build_solver import build_solver  # noqa: E402


KNOWN_BENCHMARKS: tuple[str, ...] = (
    "ohm_like",
    "ideal_gas_like",
    "arrhenius_gate_like",
    "periodic_gate_like",
    "redundant_proxy_control",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(raw) for key, raw in dict(value).items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return str(value)


def _find_latest_reference_suite_csv(mlblack_root: Path) -> Path | None:
    candidates = list(
        (mlblack_root / "examples" / "out" / "known_relation_symbolic_benchmark_suite").glob("**/benchmark_suite_table.csv")
    )
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _load_reference_table(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = _text(row.get("scenario"))
            if key:
                rows[key] = dict(row)
    return rows


def _format_metric(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError, OverflowError):
        return _text(value) or "-"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [dict(row) for row in rows]
    if not items:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in items:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def _write_markdown(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [dict(row) for row in rows]
    if not items:
        path.write_text("# Orchestrator Benchmark Table\n\n_No rows._\n", encoding="utf-8")
        return
    columns = [
        "scenario",
        "status",
        "orchestrator_best_rmse_test_rmse",
        "orchestrator_best_rmse_exact_term_recovery_score",
        "orchestrator_best_rmse_phase",
        "orchestrator_best_exact_test_rmse",
        "orchestrator_best_exact_term_recovery_score",
        "orchestrator_best_exact_phase",
        "orchestrator_best_balanced_test_rmse",
        "orchestrator_best_balanced_exact_term_recovery_score",
        "orchestrator_best_balanced_score",
        "orchestrator_best_balanced_phase",
        "orchestrator_consensus_cycles",
        "orchestrator_total_inner_runs",
        "orchestrator_outer_evaluation_count",
        "reference_baseline_test_rmse",
        "reference_orthogonal_test_rmse",
        "delta_vs_reference_orthogonal_rmse",
        "summary_path",
    ]
    lines = [
        "# nsgablack Orchestrator Benchmark Table",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in items:
        values = []
        for key in columns:
            values.append(str(row.get(key, "")).replace("\n", " ").strip())
        lines.append("| " + " | ".join(values) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the five known-relation benchmarks with the nsgablack L2/L3 orchestrator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mlblack-root", type=str, default=r"C:\Users\hp\Desktop\mlblack")
    parser.add_argument("--benchmarks", nargs="*", default=list(KNOWN_BENCHMARKS))
    parser.add_argument("--suite-id", type=str, default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument(
        "--run-dir",
        type=str,
        default=str(_THIS_DIR / "runs" / "benchmark_suite"),
        help="Suite root. Each benchmark uses <run-dir>/<suite-id>/<benchmark>/ as its scaffold run root.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="",
        help="Shared runtime surface DB for the whole suite. Defaults to <run-dir>/<suite-id>/runtime_surface.sqlite3.",
    )
    parser.add_argument("--reference-suite-csv", type=str, default="")
    parser.add_argument("--n-total", type=int, default=120)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--noise-std", type=float, default=0.025)
    parser.add_argument("--consensus-cycles", type=int, default=2)
    parser.add_argument("--unlocked-runs-per-cycle", type=int, default=2)
    parser.add_argument("--locked-runs-per-cycle", type=int, default=1)
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--pop-size", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--vns-k-max", type=int, default=4)
    parser.add_argument("--vns-base-sigma", type=float, default=0.18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--namespace", type=str, default="nsgablack_mlblack_symbolic_consensus")
    parser.add_argument("--tag-prefix", type=str, default="nsgablack_suite")
    parser.add_argument("--inner-time-budget-ms", type=float, default=180000.0)
    parser.add_argument("--max-inner-calls", type=int, default=200)
    parser.add_argument("--no-logs", action="store_true", default=True)
    return parser


def _reference_delta(orchestrator_rmse: Any, reference_rmse: Any) -> float | None:
    try:
        return float(orchestrator_rmse) - float(reference_rmse)
    except (TypeError, ValueError, OverflowError):
        return None


def _run_one_benchmark(
    *,
    args: argparse.Namespace,
    benchmark_key: str,
    suite_root: Path,
) -> dict[str, Any]:
    run_id = str(benchmark_key)
    benchmark_root = suite_root / str(benchmark_key)
    benchmark_root.mkdir(parents=True, exist_ok=True)
    db_path = str(Path(args.db_path).expanduser().resolve()) if _text(args.db_path) else str(
        (suite_root / "runtime_surface.sqlite3").resolve()
    )
    argv = [
        "--mlblack-root",
        str(args.mlblack_root),
        "--benchmark-key",
        str(benchmark_key),
        "--n-total",
        str(int(args.n_total)),
        "--train-ratio",
        str(float(args.train_ratio)),
        "--noise-std",
        str(float(args.noise_std)),
        "--consensus-cycles",
        str(int(args.consensus_cycles)),
        "--unlocked-runs-per-cycle",
        str(int(args.unlocked_runs_per_cycle)),
        "--locked-runs-per-cycle",
        str(int(args.locked_runs_per_cycle)),
        "--generations",
        str(int(args.generations)),
        "--pop-size",
        str(int(args.pop_size)),
        "--batch-size",
        str(int(args.batch_size)),
        "--vns-k-max",
        str(int(args.vns_k_max)),
        "--vns-base-sigma",
        str(float(args.vns_base_sigma)),
        "--seed",
        str(int(args.seed)),
        "--run-id",
        str(run_id),
        "--run-dir",
        str(suite_root),
        "--db-path",
        str(db_path),
        "--namespace",
        str(args.namespace),
        "--tag-prefix",
        str(args.tag_prefix),
        "--inner-time-budget-ms",
        str(float(args.inner_time_budget_ms)),
        "--max-inner-calls",
        str(int(args.max_inner_calls)),
    ]
    if bool(args.no_logs):
        argv.append("--no-logs")

    started = time.perf_counter()
    solver = build_solver(argv)
    result = dict(solver.run())
    elapsed = time.perf_counter() - started
    best_plan = None
    best_x = getattr(solver, "best_x", None)
    if best_x is not None and hasattr(solver.problem, "_decode_plan"):
        try:
            best_plan = solver.problem._decode_plan(best_x)
        except Exception:
            best_plan = None
    return {
        "scenario": str(benchmark_key),
        "status": _text(result.get("status")) or "unknown",
        "orchestrator_legacy_best_test_rmse": result.get("best_test_rmse"),
        "orchestrator_legacy_best_test_r2": result.get("best_test_r2"),
        "orchestrator_legacy_best_exact_term_recovery_score": result.get("best_exact_term_recovery_score"),
        "orchestrator_legacy_best_phase_equivalent_term_recovery_score": result.get(
            "best_phase_equivalent_term_recovery_score"
        ),
        "orchestrator_legacy_best_family_level_term_recovery_score": result.get(
            "best_family_level_term_recovery_score"
        ),
        "orchestrator_legacy_best_phase": result.get("best_phase"),
        "orchestrator_legacy_best_cycle_index": result.get("best_cycle_index"),
        "orchestrator_legacy_best_cycle_key": result.get("best_cycle_key"),
        "orchestrator_best_rmse_test_rmse": result.get("best_rmse_test_rmse"),
        "orchestrator_best_rmse_exact_term_recovery_score": result.get(
            "best_rmse_exact_term_recovery_score"
        ),
        "orchestrator_best_rmse_phase": result.get("best_rmse_phase"),
        "orchestrator_best_exact_test_rmse": result.get("best_exact_test_rmse"),
        "orchestrator_best_exact_term_recovery_score": result.get(
            "best_exact_term_recovery_score"
        ),
        "orchestrator_best_exact_phase": result.get("best_exact_phase"),
        "orchestrator_best_balanced_test_rmse": result.get("best_balanced_test_rmse"),
        "orchestrator_best_balanced_exact_term_recovery_score": result.get(
            "best_balanced_exact_term_recovery_score"
        ),
        "orchestrator_best_balanced_score": result.get("best_balanced_score"),
        "orchestrator_best_balanced_phase": result.get("best_balanced_phase"),
        "orchestrator_consensus_cycles": result.get("consensus_cycles"),
        "orchestrator_unlocked_runs_per_cycle": result.get("unlocked_runs_per_cycle"),
        "orchestrator_locked_runs_per_cycle": result.get("locked_runs_per_cycle"),
        "orchestrator_core_basis_count": result.get("core_basis_count"),
        "orchestrator_global_core_basis_count": result.get("global_core_basis_count"),
        "orchestrator_locked_seed_terms": result.get("locked_seed_terms"),
        "orchestrator_global_locked_seed_terms": result.get("global_locked_seed_terms"),
        "orchestrator_total_cycle_rows": result.get("total_cycle_rows"),
        "orchestrator_total_stage_rows": result.get("total_stage_rows"),
        "orchestrator_total_inner_runs": result.get("total_inner_runs"),
        "orchestrator_outer_generation": int(getattr(solver, "generation", 0)),
        "orchestrator_outer_evaluation_count": int(getattr(solver, "evaluation_count", 0)),
        "orchestrator_wall_time_s": float(elapsed),
        "best_plan_json": json.dumps(_jsonable(best_plan), ensure_ascii=False, sort_keys=True),
        "best_run_id": _text(result.get("best_run_id")),
        "best_artifact_id": _text(result.get("best_artifact_id")),
        "summary_path": _text(result.get("summary_path")),
        "orchestration_summary_path": _text(result.get("orchestration_summary_path")),
        "cycle_reports_path": _text(result.get("cycle_reports_path")),
        "stage_reports_path": _text(result.get("stage_reports_path")),
        "core_basis_evolution_path": _text(result.get("core_basis_evolution_path")),
        "comparison_path": _text(result.get("comparison_path")),
        "core_selection_path": _text(result.get("core_selection_path")),
        "runtime_surface_db": str(db_path),
        "run_root": str((suite_root / benchmark_key).resolve()),
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv if argv is not None else None)
    benchmarks = [str(item).strip() for item in list(args.benchmarks) if str(item).strip()]
    if not benchmarks:
        raise SystemExit("No benchmarks specified.")
    invalid = [item for item in benchmarks if item not in KNOWN_BENCHMARKS]
    if invalid:
        raise SystemExit(f"Unknown benchmarks: {', '.join(invalid)}")

    suite_root = Path(args.run_dir).expanduser().resolve() / str(args.suite_id)
    suite_root.mkdir(parents=True, exist_ok=True)

    reference_csv = (
        Path(args.reference_suite_csv).expanduser().resolve()
        if _text(args.reference_suite_csv)
        else _find_latest_reference_suite_csv(Path(args.mlblack_root).expanduser().resolve())
    )
    reference_rows = _load_reference_table(reference_csv)

    suite_rows: list[dict[str, Any]] = []
    started_suite = time.perf_counter()
    for benchmark_key in benchmarks:
        print(f"[suite] running {benchmark_key} ...", flush=True)
        row = _run_one_benchmark(args=args, benchmark_key=benchmark_key, suite_root=suite_root)
        reference = dict(reference_rows.get(str(benchmark_key), {}))
        row["reference_baseline_test_rmse"] = reference.get("baseline_test_rmse")
        row["reference_orthogonal_test_rmse"] = reference.get("orthogonal_test_rmse")
        row["reference_baseline_exact_term_recovery_score"] = reference.get(
            "baseline_exact_term_recovery_score"
        )
        row["reference_orthogonal_exact_term_recovery_score"] = reference.get(
            "orthogonal_exact_term_recovery_score"
        )
        row["reference_baseline_family_level_term_recovery_score"] = reference.get(
            "baseline_family_level_term_recovery_score"
        )
        row["reference_orthogonal_family_level_term_recovery_score"] = reference.get(
            "orthogonal_family_level_term_recovery_score"
        )
        row["delta_vs_reference_orthogonal_rmse"] = _reference_delta(
            row.get("orchestrator_best_balanced_test_rmse"),
            reference.get("orthogonal_test_rmse"),
        )
        suite_rows.append(row)
        print(
            "[suite] "
            f"{benchmark_key}: "
            f"rmse_board={_format_metric(row.get('orchestrator_best_rmse_test_rmse'))} "
            f"exact_board={_format_metric(row.get('orchestrator_best_exact_term_recovery_score'))} "
            f"balanced_rmse={_format_metric(row.get('orchestrator_best_balanced_test_rmse'))} "
            f"balanced_phase={_text(row.get('orchestrator_best_balanced_phase')) or '-'} "
            f"outer_eval={row.get('orchestrator_outer_evaluation_count')}",
            flush=True,
        )

    suite_elapsed = time.perf_counter() - started_suite
    summary = {
        "protocol": "nsgablack_orchestrator_benchmark_suite_v1",
        "suite_id": str(args.suite_id),
        "benchmarks": list(benchmarks),
        "budget": {
            "n_total": int(args.n_total),
            "train_ratio": float(args.train_ratio),
            "noise_std": float(args.noise_std),
            "consensus_cycles": int(args.consensus_cycles),
            "unlocked_runs_per_cycle": int(args.unlocked_runs_per_cycle),
            "locked_runs_per_cycle": int(args.locked_runs_per_cycle),
            "generations": int(args.generations),
            "pop_size": int(args.pop_size),
            "batch_size": int(args.batch_size),
            "vns_k_max": int(args.vns_k_max),
            "vns_base_sigma": float(args.vns_base_sigma),
            "seed": int(args.seed),
        },
        "reference_suite_csv": None if reference_csv is None else str(reference_csv),
        "runtime_surface_db": str(Path(args.db_path).expanduser().resolve())
        if _text(args.db_path)
        else str((suite_root / "runtime_surface.sqlite3").resolve()),
        "wall_time_s": float(suite_elapsed),
        "rows": list(suite_rows),
    }

    summary_json_path = suite_root / "orchestrator_benchmark_suite_summary.json"
    table_csv_path = suite_root / "orchestrator_benchmark_suite_table.csv"
    table_md_path = suite_root / "orchestrator_benchmark_suite_table.md"
    _write_json(summary_json_path, summary)
    _write_csv(table_csv_path, suite_rows)
    _write_markdown(table_md_path, suite_rows)

    print(f"[suite] summary_json={summary_json_path}")
    print(f"[suite] table_csv={table_csv_path}")
    print(f"[suite] table_md={table_md_path}")


if __name__ == "__main__":
    main()
