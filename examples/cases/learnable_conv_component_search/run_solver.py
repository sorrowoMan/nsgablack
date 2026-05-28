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
        LearnableConvComponentSearchConfig,
        build_learnable_conv_component_search_solver,
    )
    from case_scaffold.reporting import write_search_report  # noqa: E402
else:
    from ._bootstrap import ensure_nsgablack_importable  # noqa: E402
    from .build_solver import (  # noqa: E402
        LearnableConvComponentSearchConfig,
        build_learnable_conv_component_search_solver,
    )
    from .case_scaffold.reporting import write_search_report  # noqa: E402

ensure_nsgablack_importable(Path(__file__))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run nsgablack outer search over mlblack learnable convolution component overrides.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--suite-id", type=str, default="")
    parser.add_argument("--output-dir", type=str, default=LearnableConvComponentSearchConfig.output_dir)
    parser.add_argument("--seed", type=int, default=LearnableConvComponentSearchConfig.seed)
    parser.add_argument("--pop-size", type=int, default=LearnableConvComponentSearchConfig.pop_size)
    parser.add_argument("--offspring-size", type=int, default=LearnableConvComponentSearchConfig.offspring_size)
    parser.add_argument("--generations", type=int, default=LearnableConvComponentSearchConfig.generations)
    parser.add_argument("--mutation-sigma", type=float, default=LearnableConvComponentSearchConfig.mutation_sigma)
    parser.add_argument("--inner-train-ratio", type=float, default=LearnableConvComponentSearchConfig.inner_train_ratio)
    parser.add_argument("--inner-n-samples", type=int, default=LearnableConvComponentSearchConfig.inner_n_samples)
    parser.add_argument("--inner-input-dim", type=int, default=LearnableConvComponentSearchConfig.inner_input_dim)
    parser.add_argument("--inner-image-height", type=int, default=LearnableConvComponentSearchConfig.inner_image_height)
    parser.add_argument("--inner-image-width", type=int, default=LearnableConvComponentSearchConfig.inner_image_width)
    parser.add_argument("--inner-noise-scale", type=float, default=LearnableConvComponentSearchConfig.inner_noise_scale)
    parser.add_argument("--inner-trainer-key", type=str, default=LearnableConvComponentSearchConfig.inner_trainer_key)
    parser.add_argument("--inner-trainer-l2", type=float, default=LearnableConvComponentSearchConfig.inner_trainer_l2)
    parser.add_argument("--inner-backend", type=str, default=LearnableConvComponentSearchConfig.inner_compute_backend)
    parser.add_argument("--inner-device", type=str, default=LearnableConvComponentSearchConfig.inner_device)
    parser.add_argument("--inner-execution-backend", type=str, default=LearnableConvComponentSearchConfig.inner_execution_backend)
    parser.add_argument("--inner-threads", type=int, default=LearnableConvComponentSearchConfig.inner_threads)
    parser.add_argument(
        "--kernel-alignment-prior-weight",
        type=float,
        default=LearnableConvComponentSearchConfig.kernel_alignment_prior_weight,
    )
    parser.add_argument("--refinement-mode", type=str, default=LearnableConvComponentSearchConfig.refinement_mode)
    parser.add_argument("--refinement-steps", type=int, default=LearnableConvComponentSearchConfig.refinement_steps)
    parser.add_argument(
        "--refinement-gradient-max-directions",
        type=int,
        default=LearnableConvComponentSearchConfig.refinement_gradient_max_directions,
    )
    parser.add_argument(
        "--refinement-trust-region-batch-size",
        type=int,
        default=LearnableConvComponentSearchConfig.refinement_trust_region_batch_size,
    )
    parser.add_argument("--check", action="store_true")
    return parser


def _config_from_args(args: argparse.Namespace) -> LearnableConvComponentSearchConfig:
    return LearnableConvComponentSearchConfig(
        output_dir=str(args.output_dir),
        seed=int(args.seed),
        pop_size=int(args.pop_size),
        offspring_size=int(args.offspring_size),
        generations=int(args.generations),
        mutation_sigma=float(args.mutation_sigma),
        inner_train_ratio=float(args.inner_train_ratio),
        inner_n_samples=int(args.inner_n_samples),
        inner_input_dim=int(args.inner_input_dim),
        inner_image_height=int(args.inner_image_height),
        inner_image_width=int(args.inner_image_width),
        inner_noise_scale=float(args.inner_noise_scale),
        inner_trainer_key=str(args.inner_trainer_key),
        inner_trainer_l2=float(args.inner_trainer_l2),
        inner_compute_backend=str(args.inner_backend),
        inner_device=str(args.inner_device),
        inner_execution_backend=str(args.inner_execution_backend),
        inner_threads=int(args.inner_threads),
        kernel_alignment_prior_weight=float(args.kernel_alignment_prior_weight),
        refinement_mode=str(args.refinement_mode),
        refinement_steps=int(args.refinement_steps),
        refinement_gradient_max_directions=int(args.refinement_gradient_max_directions),
        refinement_trust_region_batch_size=int(args.refinement_trust_region_batch_size),
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    suite_id = str(args.suite_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    cfg = _config_from_args(args)
    solver = build_learnable_conv_component_search_solver(cfg, suite_id=suite_id)
    if bool(args.check):
        print(
            "learnable_conv_component_search scaffold ok | "
            f"dimension={solver.problem.dimension} objectives={solver.problem.objectives}"
        )
        return
    result = solver.run(return_dict=True)
    problem = solver.problem
    output_dir = Path(getattr(solver, "learnable_conv_output_dir")).expanduser().resolve()
    structure_cache = dict(getattr(problem, "get_cache_summary")())
    summary = {
        "suite_id": suite_id,
        "protocol": f"nsgablack_outer_symbolic_kernel_object_inner_{cfg.refinement_mode}_v4",
        "config": cfg.__dict__,
        "solver_result": result,
        "best_result": getattr(problem, "best_result", None),
        "evaluation_count": int(structure_cache.get("requested_evaluation_count", 0) or 0),
        "unique_structure_count": int(structure_cache.get("unique_structure_count", 0) or 0),
        "structure_cache": structure_cache,
    }
    artifacts = write_search_report(
        output_dir=output_dir,
        summary=summary,
        records=tuple(getattr(problem, "evaluation_records", ())),
    )
    best = getattr(problem, "best_result", None) or {}
    print(f"[conv-outer] suite_id={suite_id}")
    print(f"[conv-outer] output_dir={output_dir}")
    print(f"[conv-outer] search_mode=outer_symbolic_kernel_object_inner_{cfg.refinement_mode}")
    print(f"[conv-outer] evaluation_count={summary.get('evaluation_count')}")
    print(f"[conv-outer] unique_structure_count={summary.get('unique_structure_count')}")
    print(f"[conv-outer] structure_cache={summary.get('structure_cache')}")
    print(f"[conv-outer] best_score={best.get('score')}")
    print(f"[conv-outer] best_legacy_score={best.get('legacy_score')}")
    print(f"[conv-outer] best_refinement={best.get('refinement')}")
    print(f"[conv-outer] best_bundle={best.get('bundle')}")
    print(f"[conv-outer] best_metrics={best.get('metrics')}")
    print(f"[conv-outer] best_kernel_alignment={best.get('kernel_alignment')}")
    print(f"[conv-outer] report={artifacts.get('report_md')}")


if __name__ == "__main__":
    main()
