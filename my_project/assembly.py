# -*- coding: utf-8 -*-
"""Assembly helpers for build_solver (register + orchestration)."""

from __future__ import annotations

from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.utils.wiring import attach_checkpoint_resume, attach_observability_profile

from acceleration.config import apply_acceleration_backends
from bias.domain.config import build_bias
from evaluation.config import register_evaluation_runtime
from pipeline.config import build_pipeline
from plugins.config import (
    build_flow_plugins,
    build_ops_plugins,
    get_checkpoint_spec,
    get_observability_spec,
)
from problem.config import build_problem
from solver.config import apply_solver_profile


def reg_modeling(cfg, *, problem_key: str, pipeline_key: str, bias_key: str):
    problem = build_problem(cfg.problems, problem_key)
    pipeline = build_pipeline(cfg.pipelines, pipeline_key)
    bias_module = build_bias(cfg.biases, bias_key)
    return problem, pipeline, bias_module


def reg_solver_core(solver: EvolutionSolver, cfg, key: str) -> None:
    apply_solver_profile(solver, cfg.solver_profiles, key)


def reg_search(solver: EvolutionSolver, adapter: object | None = None) -> None:
    if adapter is not None:
        solver.set_adapter(adapter)


def reg_acceleration(solver: EvolutionSolver, cfg, keys) -> None:
    apply_acceleration_backends(solver, cfg.acceleration, keys)


def reg_evaluation(solver: EvolutionSolver, cfg, keys) -> None:
    register_evaluation_runtime(solver, cfg.evaluation, keys)


def reg_observability(solver: EvolutionSolver, cfg, run_id: str, key: str) -> None:
    obs_spec = get_observability_spec(cfg.observability, key)
    obs_cfg = obs_spec.params
    attach_observability_profile(
        solver,
        profile=str(obs_cfg.get("profile", "default")),
        output_dir=str(obs_cfg.get("run_dir", "runs")),
        run_id=run_id,
        enable_profiler=obs_cfg.get("enable_profiler", None),
        enable_decision_trace=obs_cfg.get("enable_decision_trace", None),
    )


def reg_flow(solver: EvolutionSolver, cfg, keys) -> None:
    for plugin in build_flow_plugins(cfg.flow_plugins, keys):
        solver.add_plugin(plugin)


def reg_ops(solver: EvolutionSolver, cfg, keys) -> None:
    for plugin in build_ops_plugins(cfg.ops_plugins, keys):
        solver.add_plugin(plugin)


def reg_checkpoint(solver: EvolutionSolver, cfg, key: str) -> None:
    ckpt_spec = get_checkpoint_spec(cfg.checkpoint, key)
    ckpt_cfg = ckpt_spec.params
    attach_checkpoint_resume(
        solver,
        checkpoint_dir=str(ckpt_cfg.get("checkpoint_dir", "runs/checkpoints")),
        auto_resume=bool(ckpt_cfg.get("auto_resume", True)),
        strict=bool(ckpt_cfg.get("strict", True)),
        trust_checkpoint=bool(ckpt_cfg.get("trust_checkpoint", False)),
    )
