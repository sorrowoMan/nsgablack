# -*- coding: utf-8 -*-
"""CLI entrypoint for running the project scaffold."""

from __future__ import annotations

import argparse

from build_solver import build_solver


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and run the standard project scaffold.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build and validate assembly only; do not execute solver.run().",
    )
    parser.add_argument("--run-id", default=None, help="Optional run id. Auto-generated when omitted.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    solver = build_solver(run_id=args.run_id)
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
    result = solver.run(return_dict=True)
    pareto_payload = result.get("pareto_solutions", None)
    if isinstance(pareto_payload, dict):
        objs = pareto_payload.get("objectives")
    else:
        objs = result.get("pareto_objectives", None)
    if objs is not None and len(objs) > 0:
        best_f1 = min(float(row[0]) for row in objs)
        print(f"[example] best_objective_0={best_f1:.6f}")
    else:
        print("[example] run finished but no pareto objectives were returned")


if __name__ == "__main__":
    main()
