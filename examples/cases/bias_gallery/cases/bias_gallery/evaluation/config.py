"""Case-local bindings to shared framework implementation."""
from nsgablack.project.case_support.evaluation_config import create_bindings

_bindings = create_bindings()
EvaluationSpec = _bindings.EvaluationSpec
EvaluationRegistry = _bindings.EvaluationRegistry
get_evaluation_registry = _bindings.get_evaluation_registry
ProviderBuilder = _bindings.ProviderBuilder
register_evaluation_provider_builder = _bindings.register_evaluation_provider_builder
build_evaluation_providers = _bindings.build_evaluation_providers
register_evaluation_runtime = _bindings.register_evaluation_runtime
