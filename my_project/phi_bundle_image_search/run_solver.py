from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from my_project.phi_bundle_image_search.build_solver import (
    PhiBundleImageSearchConfig,
    build_phi_bundle_image_search_solver,
)
from my_project.phi_bundle_image_search.reporting import write_search_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run nsgablack outer search over mlblack image PhiBundle representation programs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--suite-id", type=str, default="")
    parser.add_argument("--dataset", type=str, default="digits")
    parser.add_argument("--train-ratio", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-rows", type=int, default=700)
    parser.add_argument("--pop-size", type=int, default=8)
    parser.add_argument("--offspring-size", type=int, default=8)
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--mutation-sigma", type=float, default=0.18)
    parser.add_argument("--output-dir", type=str, default="runs/phi_bundle_image_search")
    parser.add_argument("--check", action="store_true")
    return parser


def _config_from_args(args: argparse.Namespace) -> PhiBundleImageSearchConfig:
    return PhiBundleImageSearchConfig(
        dataset_key=str(args.dataset),
        train_ratio=float(args.train_ratio),
        seed=int(args.seed),
        max_rows=int(args.max_rows),
        pop_size=int(args.pop_size),
        offspring_size=int(args.offspring_size),
        generations=int(args.generations),
        mutation_sigma=float(args.mutation_sigma),
        output_dir=str(args.output_dir),
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    suite_id = str(args.suite_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    cfg = _config_from_args(args)
    solver = build_phi_bundle_image_search_solver(cfg, suite_id=suite_id)
    if bool(args.check):
        print(
            "phi_bundle_image_search scaffold ok | "
            f"dimension={solver.problem.dimension} | objectives={solver.problem.objectives}"
        )
        return
    result = solver.run(return_dict=True)
    problem = solver.problem
    output_dir = Path(getattr(solver, "phi_bundle_output_dir")).expanduser().resolve()
    summary = {
        "suite_id": suite_id,
        "protocol": "nsgablack_outer_phi_bundle_search_with_typed_lane_genome_v3",
        "config": cfg.__dict__,
        "solver_result": result,
        "best_by_score": getattr(problem, "best_result", None),
        "best_by_accuracy": getattr(problem, "best_accuracy_result", None),
        "evaluation_count": len(getattr(problem, "evaluation_records", ())),
    }
    artifacts = write_search_report(
        output_dir=output_dir,
        summary=summary,
        records=tuple(getattr(problem, "evaluation_records", ())),
    )
    print(f"[phi-outer] suite_id={suite_id}")
    print(f"[phi-outer] output_dir={output_dir}")
    print(f"[phi-outer] table={artifacts['table_md']}")
    best_score = getattr(problem, "best_result", None) or {}
    best_accuracy = getattr(problem, "best_accuracy_result", None) or {}
    print(f"[phi-outer] best_by_score={best_score.get('score')} metrics={best_score.get('metrics')}")
    print(f"[phi-outer] best_by_accuracy={best_accuracy.get('metrics')} score={best_accuracy.get('score')}")
    print(f"[phi-outer] best_accuracy_bundle={best_accuracy.get('bundle')}")


if __name__ == "__main__":
    main()
