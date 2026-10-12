"""Case-local bindings to shared framework implementation."""
from nsgablack.project.case_support.bias_domain_config import BiasConfig, create_bindings

def _build_local_bias_module(*args, **kwargs):
    from .example_bias import build_bias_module
    return build_bias_module(*args, **kwargs)


_bindings = create_bindings(build_bias_module=_build_local_bias_module)
BiasConfig = _bindings.BiasConfig
BiasSpec = _bindings.BiasSpec
BiasRegistry = _bindings.BiasRegistry
get_bias_registry = _bindings.get_bias_registry
BiasBuilder = _bindings.BiasBuilder
register_bias_builder = _bindings.register_bias_builder
build_bias = _bindings.build_bias
