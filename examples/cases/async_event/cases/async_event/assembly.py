"""Case-local bindings to shared framework implementation."""
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
from nsgablack.project.case_support.assembly import create_bindings

_bindings = create_bindings(build_bias=build_bias, register_evaluation_runtime=register_evaluation_runtime, build_pipeline=build_pipeline, attach_governance_plugins=attach_governance_plugins, attach_ops_plugins=attach_ops_plugins, get_checkpoint_spec=get_checkpoint_spec, get_observability_spec=get_observability_spec, build_problem=build_problem, apply_runtime_profile=apply_runtime_profile, apply_solver_profile_cfg=apply_solver_profile_cfg)
build_modeling = _bindings.build_modeling
apply_solver_profile = _bindings.apply_solver_profile
attach_search = _bindings.attach_search
attach_runtime = _bindings.attach_runtime
attach_evaluation = _bindings.attach_evaluation
attach_observability = _bindings.attach_observability
attach_governance = _bindings.attach_governance
attach_ops = _bindings.attach_ops
attach_checkpoint = _bindings.attach_checkpoint
