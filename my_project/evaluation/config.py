# -*- coding: utf-8 -*-
"""L4 evaluation runtime configuration (provider registry only)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Any, Callable, Dict, Sequence

import numpy as np

from nsgablack.plugins import (
    BroydenSolverProviderPlugin,
    CoptBackend,
    EvaluationModelConfig,
    EvaluationModelProviderPlugin,
    GpuEvaluationTemplateConfig,
    GpuEvaluationTemplateProviderPlugin,
    MonteCarloEvaluationConfig,
    MonteCarloEvaluationProviderPlugin,
    MultiFidelityEvaluationConfig,
    MultiFidelityEvaluationProviderPlugin,
    NewtonSolverProviderPlugin,
    NumericalSolverConfig,
    SurrogateEvaluationConfig,
    SurrogateEvaluationProviderPlugin,
)


@dataclass(frozen=True)
class EvaluationSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationRegistry:
    registry: tuple[EvaluationSpec, ...] = ()


def get_evaluation_registry() -> EvaluationRegistry:
    return EvaluationRegistry(
        registry=(
            EvaluationSpec(key="surrogate", params={}),
            EvaluationSpec(key="multi_fidelity", params={}),
            EvaluationSpec(key="monte_carlo", params={}),
            EvaluationSpec(key="newton_solver", params={}),
            EvaluationSpec(key="broyden_solver", params={}),
            EvaluationSpec(key="gpu_eval_template", params={}),
            EvaluationSpec(key="evaluation_model", params={}),
            EvaluationSpec(key="copt_eval_model", params={"copt_template": "qp"}),
        )
    )


ProviderBuilder = Callable[[Dict[str, Any]], object]


def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
    if not params:
        return config_cls(), {}
    cfg_fields = {f.name for f in fields(config_cls)}
    cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
    other = {k: v for k, v in params.items() if k not in cfg_fields}
    return config_cls(**cfg_kwargs), other


def _provider_from_plugin(plugin: object) -> object:
    creator = getattr(plugin, "create_provider", None)
    if callable(creator):
        return creator()
    raise TypeError("evaluation spec expects a provider plugin with create_provider().")


def _build_with_config(plugin_cls, config_cls, params: Dict[str, Any], *, config_param: str = "config") -> object:
    if "config" in params and isinstance(params["config"], config_cls):
        cfg = params["config"]
        other = {k: v for k, v in params.items() if k != "config"}
        return _provider_from_plugin(plugin_cls(**{config_param: cfg}, **other))
    cfg, other = _split_config_kwargs(config_cls, params)
    return _provider_from_plugin(plugin_cls(**{config_param: cfg}, **other))


def _build_copt_eval_model(params: Dict[str, Any]) -> object:
    cfg, other = _split_config_kwargs(EvaluationModelConfig, params)
    copt_template = str(other.pop("copt_template", "qp"))

    def _backend_factory(problem, eval_ctx):
        _ = problem
        _ = eval_ctx
        backend = CoptBackend()

        def _solve_fn(request, cp):
            candidate = request.candidate
            n = int(len(candidate))
            eye_q = np.eye(n, dtype=float)
            spec = {
                "c": np.asarray(candidate, dtype=float),
                "Q": eye_q,
                "lb": np.zeros(n, dtype=float),
                "ub": np.ones(n, dtype=float),
                "objective_sense": "min",
            }
            req2 = type(request)(
                candidate=request.candidate,
                eval_context=request.eval_context,
                inner_problem=request.inner_problem,
                inner_solver=request.inner_solver,
                payload={
                    "copt_template": copt_template,
                    "copt_template_params": spec,
                },
            )
            return backend.solve(req2)

        backend.solve_fn = _solve_fn
        return backend

    plugin = EvaluationModelProviderPlugin(config=cfg, backend_factory=_backend_factory, **other)
    return plugin.create_provider()


_EVAL_PROVIDER_BUILDERS: Dict[str, ProviderBuilder] = {
    "surrogate": lambda p: _build_with_config(SurrogateEvaluationProviderPlugin, SurrogateEvaluationConfig, p),
    "multi_fidelity": lambda p: _build_with_config(
        MultiFidelityEvaluationProviderPlugin, MultiFidelityEvaluationConfig, p
    ),
    "monte_carlo": lambda p: _build_with_config(MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig, p),
    "newton_solver": lambda p: _build_with_config(NewtonSolverProviderPlugin, NumericalSolverConfig, p),
    "broyden_solver": lambda p: _build_with_config(BroydenSolverProviderPlugin, NumericalSolverConfig, p),
    "gpu_eval_template": lambda p: _build_with_config(GpuEvaluationTemplateProviderPlugin, GpuEvaluationTemplateConfig, p),
    "evaluation_model": lambda p: _build_with_config(EvaluationModelProviderPlugin, EvaluationModelConfig, p),
    "copt_eval_model": _build_copt_eval_model,
}


def register_evaluation_provider_builder(key: str, builder: ProviderBuilder) -> None:
    _EVAL_PROVIDER_BUILDERS[str(key).strip().lower()] = builder


def _find_spec(registry: EvaluationRegistry, key: str) -> EvaluationSpec:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    raise ValueError(f"Evaluation provider key not registered: {key}")


def _build_provider_from_spec(spec: EvaluationSpec) -> object:
    key = str(spec.key).strip().lower()
    builder = _EVAL_PROVIDER_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown evaluation provider key: {spec.key}")
    params = dict(spec.params or {})
    return builder(params)


def build_evaluation_providers(registry: EvaluationRegistry, keys: Sequence[str]) -> list[object]:
    providers: list[object] = []
    for key in keys:
        spec = _find_spec(registry, key)
        providers.append(_build_provider_from_spec(spec))
    return providers


def register_evaluation_runtime(solver, registry: EvaluationRegistry, keys: Sequence[str]) -> None:
    register = getattr(solver, "register_evaluation_provider", None)
    if not callable(register):
        return
    for provider in build_evaluation_providers(registry, keys):
        register(provider)
