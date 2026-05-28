# -*- coding: utf-8 -*-
# CLI entrypoint for running the project scaffold.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))

from build_solver import _print_result, build_solver


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and run the classification threshold calibration case.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build and validate assembly only; do not execute solver.run().",
    )
    parser.add_argument("--run-id", default=None, help="Optional run id. Auto-generated when omitted.")
    parser.add_argument("--strategy", default="default", help="Search strategy key (default).")
    parser.add_argument(
        "--quickstart",
        action="store_true",
        help="Use quickstart observability profile.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    solver = build_solver(run_id=args.run_id, strategy=args.strategy, quickstart=bool(args.quickstart))
    if bool(args.check):
        plugin_count = len(getattr(getattr(solver, "plugin_manager", None), "plugins", []) or [])
        providers = getattr(getattr(solver, "evaluation_mediator", None), "list_providers", None)
        provider_count = len(tuple(providers())) if callable(providers) else 0
        pipeline = getattr(solver, "representation_pipeline", None)
        mutator_name = type(getattr(pipeline, "mutator", None)).__name__
        print(
            "[check] assembly ok | "
            f"problem={type(getattr(solver, 'problem', None)).__name__} | "
            f"pipeline={type(getattr(solver, 'representation_pipeline', None)).__name__} | "
            f"mutator={mutator_name} | "
            f"adapter={type(getattr(solver, 'adapter', None)).__name__} | "
            f"providers={provider_count} | "
            f"plugins={plugin_count}"
        )
        return
    _print_result(solver, solver.run(return_dict=True))


if __name__ == "__main__":
    main()
