# -*- coding: utf-8 -*-
"""Project-level configuration aggregator (registries only)."""

from __future__ import annotations

from dataclasses import dataclass

from problem.config import ProblemRegistry
from pipeline.config import PipelineRegistry
from bias.domain.config import BiasRegistry
from adapter.config import AdapterRegistry
from solver.config import SolverProfileRegistry, StoreProfileRegistry
from acceleration.config import AccelerationRegistry
from evaluation.config import EvaluationRegistry
from plugins.config import FlowPluginRegistry, OpsPluginRegistry, ObservabilityRegistry, CheckpointRegistry

__all__ = ["ProjectConfig", "get_project_config"]


@dataclass(frozen=True)
class ProjectConfig:
    problems: ProblemRegistry
    pipelines: PipelineRegistry
    biases: BiasRegistry
    adapters: AdapterRegistry
    solver_profiles: SolverProfileRegistry
    store_profiles: StoreProfileRegistry
    acceleration: AccelerationRegistry
    evaluation: EvaluationRegistry
    flow_plugins: FlowPluginRegistry
    ops_plugins: OpsPluginRegistry
    observability: ObservabilityRegistry
    checkpoint: CheckpointRegistry


def get_project_config() -> ProjectConfig:
    from acceleration.config import get_acceleration_registry
    from adapter.config import get_adapter_registry
    from bias.domain.config import get_bias_registry
    from evaluation.config import get_evaluation_registry
    from pipeline.config import get_pipeline_registry
    from plugins.config import (
        get_checkpoint_registry,
        get_flow_plugin_registry,
        get_observability_registry,
        get_ops_plugin_registry,
    )
    from problem.config import get_problem_registry
    from solver.config import get_solver_profile_registry
    from solver.config import get_store_profile_registry

    return ProjectConfig(
        problems=get_problem_registry(),
        pipelines=get_pipeline_registry(),
        biases=get_bias_registry(),
        adapters=get_adapter_registry(),
        solver_profiles=get_solver_profile_registry(),
        store_profiles=get_store_profile_registry(),
        acceleration=get_acceleration_registry(),
        evaluation=get_evaluation_registry(),
        flow_plugins=get_flow_plugin_registry(),
        ops_plugins=get_ops_plugin_registry(),
        observability=get_observability_registry(),
        checkpoint=get_checkpoint_registry(),
    )
