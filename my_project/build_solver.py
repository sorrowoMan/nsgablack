# -*- coding: utf-8 -*-
"""Project entrypoint: assembly only."""

from __future__ import annotations

import argparse

from nsgablack.core.solver import BlackBoxSolverNSGAII

from bias.example_bias import build_bias_module
from pipeline.example_pipeline import build_pipeline
from plugins.example_plugin import GenerationHeartbeatPlugin
from problem.example_problem import ExampleProblem


def build_solver(argv: list[str] | None = None) -> BlackBoxSolverNSGAII:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dimension", type=int, default=8)
    parser.add_argument("--pop-size", type=int, default=80)
    parser.add_argument("--generations", type=int, default=60)
    parser.add_argument("--enable-bias", action="store_true")
    parser.add_argument("--disable-heartbeat-plugin", action="store_true")
    parser.add_argument("--heartbeat-interval", type=int, default=10)
    args, _ = parser.parse_known_args(argv if argv is not None else [])

    problem = ExampleProblem(dimension=int(args.dimension))
    pipeline = build_pipeline()
    bias_module = build_bias_module(enable_bias=bool(args.enable_bias))

    solver = BlackBoxSolverNSGAII(problem, bias_module=bias_module)
    solver.pop_size = int(args.pop_size)
    solver.max_generations = int(args.generations)
    solver.mutation_rate = 0.2
    solver.crossover_rate = 0.8
    solver.enable_progress_log = True
    solver.report_interval = max(1, solver.max_generations // 10)
    solver.set_representation_pipeline(pipeline)
    if not bool(args.disable_heartbeat_plugin):
        solver.add_plugin(
            GenerationHeartbeatPlugin(
                interval=max(1, int(args.heartbeat_interval)),
                verbose=True,
            )
        )
    return solver


def main() -> None:
    solver = build_solver()
    result = solver.run(return_dict=True)
    pareto = result.get("pareto_solutions") or {}
    objs = pareto.get("objectives")
    if objs is not None and len(objs) > 0:
        best_f1 = min(float(row[0]) for row in objs)
        print(f"[example] best_objective_0={best_f1:.6f}")
    else:
        print("[example] run finished but no pareto objectives were returned")


if __name__ == "__main__":
    main()
