# -*- coding: utf-8 -*-
"""Formal solver assembly for the mlblack symbolic consensus scaffold."""

from __future__ import annotations

import argparse
import random
from datetime import datetime
from pathlib import Path

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.plugins.domain_backends.mlblack_symbolic_consensus_backend import MlblackSymbolicConsensusBackend

from case_scaffold.bias.symbolic_outer_bias import build_symbolic_outer_bias_module
from case_scaffold.orchestration.adapters import build_outer_adapter
from pipeline.main import build_pipeline
from case_scaffold.plugins.runtime import attach_observability, attach_runtime_plugins, build_backend_config
from case_scaffold.problem.outer_problem import MlblackSymbolicConsensusOuterProblem
from case_scaffold.reporting.result_projection import MlblackConsensusOuterSolver


def _resolve_run_paths(args: argparse.Namespace) -> tuple[str, Path, Path, str]:
    run_id = str(args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    run_root = Path(args.run_dir).expanduser().resolve() / run_id
    inner_root = run_root / "inner_mlblack"
    db_path = (
        str(Path(args.db_path).expanduser().resolve())
        if str(args.db_path).strip()
        else str(run_root / "mlblack_experiment_tracker.sqlite3")
    )
    return run_id, run_root, inner_root, db_path


def build_solver_from_args(args: argparse.Namespace) -> ComposableSolver:
    random.seed(int(args.seed))
    np.random.seed(int(args.seed))

    run_id, run_root, inner_root, db_path = _resolve_run_paths(args)
    backend_config = build_backend_config(args, run_root=run_root, inner_root=inner_root, db_path=db_path)
    backend = MlblackSymbolicConsensusBackend(config=backend_config)
    problem = MlblackSymbolicConsensusOuterProblem(
        benchmark_key=str(args.benchmark_key),
        backend_config=backend_config,
    )
    pipeline = build_pipeline(problem, args)
    adapter = build_outer_adapter(args)
    bias_module = None if bool(args.no_bias) else build_symbolic_outer_bias_module(problem)
    solver = MlblackConsensusOuterSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
        bias_module=bias_module,
    )
    solver.set_bias_enabled(bias_module is not None)
    solver.set_max_steps(int(args.generations))
    solver.set_solver_hyperparams(pop_size=max(1, int(args.pop_size)))
    attach_runtime_plugins(
        solver,
        backend=backend,
        backend_config=backend_config,
        args=args,
        db_path=db_path,
    )
    attach_observability(
        solver,
        args=args,
        run_root=run_root,
        run_id=run_id,
    )
    return solver
