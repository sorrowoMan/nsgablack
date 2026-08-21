from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence


def _ensure_nsgablack_importable(start: Path) -> None:
    for parent in start.resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "__init__.py").is_file():
            package_parent = parent.parent
            if str(package_parent) not in sys.path:
                sys.path.insert(0, str(package_parent))
            return


if __package__ in {None, ""}:
    _ensure_nsgablack_importable(Path(__file__))
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from build_solver import EtfLaneOuterSearchConfig, build_etf_lane_outer_search_solver
    from reporting import write_search_report
else:
    from .build_solver import EtfLaneOuterSearchConfig, build_etf_lane_outer_search_solver
    from .reporting import write_search_report


def _parse_int_list(text: str) -> tuple[int, ...]:
    out: list[int] = []
    for item in str(text or "").replace(";", ",").split(","):
        raw = str(item).strip()
        if not raw:
            continue
        out.append(int(raw))
    return tuple(out) if out else (42,)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run nsgablack outer search on mlblack ETF multi-strategy lane configuration.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--suite-id", type=str, default="")
    parser.add_argument("--dataset-url", type=str, default=EtfLaneOuterSearchConfig.dataset_url)
    parser.add_argument("--dataset-label", type=str, default=EtfLaneOuterSearchConfig.dataset_label)
    parser.add_argument("--seed", type=int, default=EtfLaneOuterSearchConfig.seed)
    parser.add_argument("--pop-size", type=int, default=EtfLaneOuterSearchConfig.pop_size)
    parser.add_argument("--offspring-size", type=int, default=EtfLaneOuterSearchConfig.offspring_size)
    parser.add_argument("--generations", type=int, default=EtfLaneOuterSearchConfig.generations)
    parser.add_argument("--mutation-sigma", type=float, default=EtfLaneOuterSearchConfig.mutation_sigma)
    parser.add_argument("--output-dir", type=str, default=EtfLaneOuterSearchConfig.output_dir)
    parser.add_argument("--baseline-models", type=str, default=EtfLaneOuterSearchConfig.baseline_models)
    parser.add_argument("--seeds", type=str, default="42,52")
    parser.add_argument("--wf-min-train-size", type=int, default=EtfLaneOuterSearchConfig.wf_min_train_size)
    parser.add_argument("--wf-test-size", type=int, default=EtfLaneOuterSearchConfig.wf_test_size)
    parser.add_argument("--wf-step-size", type=int, default=EtfLaneOuterSearchConfig.wf_step_size)
    parser.add_argument("--wf-mode", type=str, default=EtfLaneOuterSearchConfig.wf_mode)
    parser.add_argument("--wf-train-window-size", type=int, default=EtfLaneOuterSearchConfig.wf_train_window_size)
    parser.add_argument("--wf-max-folds", type=int, default=EtfLaneOuterSearchConfig.wf_max_folds)
    parser.add_argument("--wf-max-train-panel-rows", type=int, default=EtfLaneOuterSearchConfig.wf_max_train_panel_rows)
    parser.add_argument("--wf-max-test-panel-rows", type=int, default=EtfLaneOuterSearchConfig.wf_max_test_panel_rows)
    parser.add_argument(
        "--objective-weight-neg-net-sharpe",
        type=float,
        default=EtfLaneOuterSearchConfig.objective_weight_neg_net_sharpe,
    )
    parser.add_argument(
        "--objective-weight-max-drawdown-abs",
        type=float,
        default=EtfLaneOuterSearchConfig.objective_weight_max_drawdown_abs,
    )
    parser.add_argument(
        "--objective-weight-turnover-proxy",
        type=float,
        default=EtfLaneOuterSearchConfig.objective_weight_turnover_proxy,
    )
    parser.add_argument(
        "--objective-weight-neg-rank-ic-mean",
        type=float,
        default=EtfLaneOuterSearchConfig.objective_weight_neg_rank_ic_mean,
    )
    parser.add_argument(
        "--objective-weight-rank-ic-std",
        type=float,
        default=EtfLaneOuterSearchConfig.objective_weight_rank_ic_std,
    )
    parser.add_argument("--check", action="store_true")
    return parser


def _config_from_args(args: argparse.Namespace) -> EtfLaneOuterSearchConfig:
    return EtfLaneOuterSearchConfig(
        dataset_url=str(args.dataset_url),
        dataset_label=str(args.dataset_label),
        output_dir=str(args.output_dir),
        seed=int(args.seed),
        pop_size=int(args.pop_size),
        offspring_size=int(args.offspring_size),
        generations=int(args.generations),
        mutation_sigma=float(args.mutation_sigma),
        baseline_models=str(args.baseline_models),
        seeds=_parse_int_list(str(args.seeds)),
        wf_min_train_size=int(args.wf_min_train_size),
        wf_test_size=int(args.wf_test_size),
        wf_step_size=int(args.wf_step_size),
        wf_mode=str(args.wf_mode),
        wf_train_window_size=int(args.wf_train_window_size),
        wf_max_folds=int(args.wf_max_folds),
        wf_max_train_panel_rows=int(args.wf_max_train_panel_rows),
        wf_max_test_panel_rows=int(args.wf_max_test_panel_rows),
        objective_weight_neg_net_sharpe=float(args.objective_weight_neg_net_sharpe),
        objective_weight_max_drawdown_abs=float(args.objective_weight_max_drawdown_abs),
        objective_weight_turnover_proxy=float(args.objective_weight_turnover_proxy),
        objective_weight_neg_rank_ic_mean=float(args.objective_weight_neg_rank_ic_mean),
        objective_weight_rank_ic_std=float(args.objective_weight_rank_ic_std),
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    suite_id = str(args.suite_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    cfg = _config_from_args(args)
    solver = build_etf_lane_outer_search_solver(cfg, suite_id=suite_id)
    if bool(args.check):
        print(
            "[check] etf_lane_outer_search scaffold ok | "
            f"dimension={solver.problem.dimension} objectives={solver.problem.objectives}"
        )
        return
    result = solver.run()
    problem = solver.problem
    output_dir = Path(getattr(solver, "etf_outer_output_dir")).expanduser().resolve()
    summary = {
        "suite_id": suite_id,
        "protocol": "nsgablack_outer_etf_lane_search_v1",
        "config": cfg.__dict__,
        "solver_result": result,
        "best_result": getattr(problem, "best_result", None),
        "evaluation_count": len(getattr(problem, "evaluation_records", ())),
    }
    artifacts = write_search_report(
        output_dir=output_dir,
        summary=summary,
        records=tuple(getattr(problem, "evaluation_records", ())),
    )
    best = getattr(problem, "best_result", None) or {}
    print(f"[etf-outer] suite_id={suite_id}")
    print(f"[etf-outer] output_dir={output_dir}")
    print(f"[etf-outer] table={artifacts.get('table_md')}")
    print(f"[etf-outer] evaluation_count={summary.get('evaluation_count')}")
    print(f"[etf-outer] best_score={best.get('score')}")
    print(f"[etf-outer] best_objectives={best.get('objectives')}")
    print(f"[etf-outer] best_bundle={best.get('lane_bundle')}")
    print(f"[etf-outer] best_aggregate={best.get('aggregate')}")


if __name__ == "__main__":
    main()
