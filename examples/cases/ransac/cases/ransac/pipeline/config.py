"""Case-local bindings to shared framework implementation."""
from nsgablack.project.case_support.pipeline_config import create_bindings

_bindings = create_bindings()
PipelineConfig = _bindings.PipelineConfig
PipelineSpec = _bindings.PipelineSpec
PipelineRegistry = _bindings.PipelineRegistry
get_pipeline_registry = _bindings.get_pipeline_registry
PipelineBuilder = _bindings.PipelineBuilder
register_pipeline_builder = _bindings.register_pipeline_builder
build_pipeline = _bindings.build_pipeline
