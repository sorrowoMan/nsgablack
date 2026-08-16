# -*- coding: utf-8 -*-
# Assembly helpers for build_solver (build/apply/attach).

from __future__ import annotations

from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.utils.wiring import attach_checkpoint_resume, attach_observability_profile

from bias.domain.config import build_bias
from evaluation.config import register_evaluation_runtime
from pipeline.main import build_pipeline
from plugins.config import (
    attach_governance_plugins,
    attach_ops_plugins,
    get_checkpoint_spec,
    get_observability_spec,
)
from problem.config import build_problem
from runtime.config import apply_runtime_profile
from solver.config import apply_solver_profile as apply_solver_profile_cfg


def build_modeling(cfg, *, problem_key: str, pipeline_key: str, bias_key: str):
    problem = build_problem(cfg.problems, problem_key)
    pipeline = build_pipeline(cfg.pipelines, pipeline_key)
    bias_module = build_bias(cfg.biases, bias_key)
    return problem, pipeline, bias_module


def apply_solver_profile(solver: EvolutionSolver, cfg, key: str) -> None:
    apply_solver_profile_cfg(solver, cfg.solver_profiles, key)


def attach_search(solver: EvolutionSolver, adapter: object | None = None) -> None:
    if adapter is not None:
        solver.set_adapter(adapter)


def attach_runtime(solver: EvolutionSolver, cfg, profile_key: str = "local_cpu", backend_keys=()) -> None:
    apply_runtime_profile(solver, cfg.runtime, profile_key, backend_keys)


def attach_evaluation(solver: EvolutionSolver, cfg, keys) -> None:
    register_evaluation_runtime(solver, cfg.evaluation, keys)


def attach_observability(solver: EvolutionSolver, cfg, run_id: str, key: str) -> None:
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


def attach_governance(solver: EvolutionSolver, cfg, keys) -> None:
    attach_governance_plugins(solver, cfg.governance_plugins, keys)


def attach_ops(solver: EvolutionSolver, cfg, keys) -> None:
    attach_ops_plugins(solver, cfg.ops_plugins, keys)


def attach_checkpoint(solver: EvolutionSolver, cfg, key: str) -> None:
    ckpt_spec = get_checkpoint_spec(cfg.checkpoint, key)
    ckpt_cfg = ckpt_spec.params
    attach_checkpoint_resume(
        solver,
        checkpoint_dir=str(ckpt_cfg.get("checkpoint_dir", "runs/checkpoints")),
        auto_resume=bool(ckpt_cfg.get("auto_resume", True)),
        strict=bool(ckpt_cfg.get("strict", True)),
        trust_checkpoint=bool(ckpt_cfg.get("trust_checkpoint", False)),
    )
