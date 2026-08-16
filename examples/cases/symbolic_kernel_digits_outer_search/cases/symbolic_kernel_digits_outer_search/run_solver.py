from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    _THIS_DIR = Path(__file__).resolve().parent
    if str(_THIS_DIR) not in sys.path:
        sys.path.insert(0, str(_THIS_DIR))
    from _bootstrap import ensure_nsgablack_importable  # noqa: E402
    from build_solver import (  # noqa: E402
        SymbolicKernelDigitsOuterSearchConfig,
        build_symbolic_kernel_digits_outer_search_solver,
    )
    from case_scaffold.reporting import write_search_report  # noqa: E402
else:
    from ._bootstrap import ensure_nsgablack_importable  # noqa: E402
    from .build_solver import (  # noqa: E402
        SymbolicKernelDigitsOuterSearchConfig,
        build_symbolic_kernel_digits_outer_search_solver,
    )
    from .case_scaffold.reporting import write_search_report  # noqa: E402

ensure_nsgablack_importable(Path(__file__))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run nsgablack outer search over symbolic-kernel digits classification.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--suite-id", type=str, default="")
    parser.add_argument("--output-dir", type=str, default=SymbolicKernelDigitsOuterSearchConfig.output_dir)
    parser.add_argument("--seed", type=int, default=SymbolicKernelDigitsOuterSearchConfig.seed)
    parser.add_argument("--pop-size", type=int, default=SymbolicKernelDigitsOuterSearchConfig.pop_size)
    parser.add_argument("--offspring-size", type=int, default=SymbolicKernelDigitsOuterSearchConfig.offspring_size)
    parser.add_argument("--generations", type=int, default=SymbolicKernelDigitsOuterSearchConfig.generations)
    parser.add_argument("--inner-dataset-key", type=str, default=SymbolicKernelDigitsOuterSearchConfig.inner_dataset_key)
    parser.add_argument("--inner-max-rows", type=int, default=SymbolicKernelDigitsOuterSearchConfig.inner_max_rows)
    parser.add_argument("--inner-trainer-key", type=str, default=SymbolicKernelDigitsOuterSearchConfig.inner_trainer_key)
    parser.add_argument("--inner-trainer-l2", type=float, default=SymbolicKernelDigitsOuterSearchConfig.inner_trainer_l2)
    parser.add_argument("--inner-mlp-epochs", type=int, default=SymbolicKernelDigitsOuterSearchConfig.inner_mlp_epochs)
    parser.add_argument("--inner-mlp-batch-size", type=int, default=SymbolicKernelDigitsOuterSearchConfig.inner_mlp_batch_size)
    parser.add_argument("--inner-mlp-lr", type=float, default=SymbolicKernelDigitsOuterSearchConfig.inner_mlp_lr)
    parser.add_argument("--inner-mlp-weight-decay", type=float, default=SymbolicKernelDigitsOuterSearchConfig.inner_mlp_weight_decay)
    parser.add_argument("--inner-backend", type=str, default=SymbolicKernelDigitsOuterSearchConfig.inner_compute_backend)
    parser.add_argument("--inner-device", type=str, default=SymbolicKernelDigitsOuterSearchConfig.inner_device)
    parser.add_argument("--outer-accuracy-weight", type=float, default=SymbolicKernelDigitsOuterSearchConfig.outer_accuracy_weight)
    parser.add_argument("--outer-gap-weight", type=float, default=SymbolicKernelDigitsOuterSearchConfig.outer_gap_weight)
    parser.add_argument("--outer-complexity-weight", type=float, default=SymbolicKernelDigitsOuterSearchConfig.outer_complexity_weight)
    parser.add_argument("--outer-prior-weight", type=float, default=SymbolicKernelDigitsOuterSearchConfig.outer_prior_weight)
    parser.add_argument("--refinement-mode", type=str, default=SymbolicKernelDigitsOuterSearchConfig.refinement_mode)
    parser.add_argument("--refinement-steps", type=int, default=SymbolicKernelDigitsOuterSearchConfig.refinement_steps)
    parser.add_argument("--refinement-trust-region-batch-size", type=int, default=SymbolicKernelDigitsOuterSearchConfig.refinement_trust_region_batch_size)
    parser.add_argument("--check", action="store_true")
    return parser


def _config_from_args(args: argparse.Namespace) -> SymbolicKernelDigitsOuterSearchConfig:
    return SymbolicKernelDigitsOuterSearchConfig(
        output_dir=str(args.output_dir),
        seed=int(args.seed),
        pop_size=int(args.pop_size),
        offspring_size=int(args.offspring_size),
        generations=int(args.generations),
        inner_dataset_key=str(args.inner_dataset_key),
        inner_max_rows=int(args.inner_max_rows),
        inner_trainer_key=str(args.inner_trainer_key),
        inner_trainer_l2=float(args.inner_trainer_l2),
        inner_mlp_epochs=int(args.inner_mlp_epochs),
        inner_mlp_batch_size=int(args.inner_mlp_batch_size),
        inner_mlp_lr=float(args.inner_mlp_lr),
        inner_mlp_weight_decay=float(args.inner_mlp_weight_decay),
        inner_compute_backend=str(args.inner_backend),
        inner_device=str(args.inner_device),
        outer_accuracy_weight=float(args.outer_accuracy_weight),
        outer_gap_weight=float(args.outer_gap_weight),
        outer_complexity_weight=float(args.outer_complexity_weight),
        outer_prior_weight=float(args.outer_prior_weight),
        refinement_mode=str(args.refinement_mode),
        refinement_steps=int(args.refinement_steps),
        refinement_trust_region_batch_size=int(args.refinement_trust_region_batch_size),
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    suite_id = str(args.suite_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    cfg = _config_from_args(args)
    solver = build_symbolic_kernel_digits_outer_search_solver(cfg, suite_id=suite_id)
    if bool(args.check):
        print(
            "symbolic_kernel_digits_outer_search scaffold ok | "
            f"dimension={solver.problem.dimension} objectives={solver.problem.objectives}"
        )
        return
    result = solver.run(return_dict=True)
    problem = solver.problem
    output_dir = Path(getattr(solver, "symbolic_kernel_digits_output_dir")).expanduser().resolve()
    structure_cache = dict(getattr(problem, "get_cache_summary")())
    records = tuple(getattr(problem, "evaluation_records", ()))
    best_score_result = min(records, key=lambda record: float(dict(record).get("score", float("inf")))) if records else None
    best_accuracy_result = (
        max(
            records,
            key=lambda record: float(dict(dict(record).get("metrics", {}) or {}).get("test_accuracy", float("-inf"))),
        )
        if records
        else None
    )
    best_macro_f1_result = (
        max(
            records,
            key=lambda record: float(dict(dict(record).get("metrics", {}) or {}).get("test_macro_f1", float("-inf"))),
        )
        if records
        else None
    )
    summary = {
        "suite_id": suite_id,
        "protocol": f"nsgablack_outer_symbolic_kernel_digits_inner_{cfg.refinement_mode}_v1",
        "config": cfg.__dict__,
        "solver_result": result,
        "best_result": best_score_result,
        "best_score_result": best_score_result,
        "best_accuracy_result": best_accuracy_result,
        "best_macro_f1_result": best_macro_f1_result,
        "evaluation_count": int(structure_cache.get("requested_evaluation_count", 0) or 0),
        "unique_structure_count": int(structure_cache.get("unique_structure_count", 0) or 0),
        "structure_cache": structure_cache,
    }
    artifacts = write_search_report(
        output_dir=output_dir,
        summary=summary,
        records=records,
    )
    best = dict(best_score_result or {})
    best_accuracy = dict(best_accuracy_result or {})
    print(f"[digits-outer] suite_id={suite_id}")
    print(f"[digits-outer] output_dir={output_dir}")
    print(f"[digits-outer] inner_dataset_key={cfg.inner_dataset_key}")
    print(f"[digits-outer] search_mode=outer_symbolic_kernel_digits_inner_{cfg.refinement_mode}")
    print(f"[digits-outer] evaluation_count={summary.get('evaluation_count')}")
    print(f"[digits-outer] unique_structure_count={summary.get('unique_structure_count')}")
    print(f"[digits-outer] structure_cache={summary.get('structure_cache')}")
    print(f"[digits-outer] best_score={best.get('score')}")
    print(f"[digits-outer] best_bundle={best.get('bundle')}")
    print(f"[digits-outer] best_metrics={best.get('metrics')}")
    print(f"[digits-outer] best_prior_summary={best.get('prior_summary')}")
    print(f"[digits-outer] best_accuracy={dict(best_accuracy.get('metrics', {}) or {}).get('test_accuracy')}")
    print(f"[digits-outer] best_accuracy_bundle={best_accuracy.get('bundle')}")
    print(f"[digits-outer] best_accuracy_metrics={best_accuracy.get('metrics')}")
    print(f"[digits-outer] report={artifacts.get('report_md')}")


if __name__ == "__main__":
    main()
