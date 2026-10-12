"""Case-local bindings to shared framework implementation."""
from .example_adapter import ExampleAdapter
from nsgablack.project.case_support.adapter_config import create_bindings

_bindings = create_bindings(ExampleAdapter=ExampleAdapter)
AdapterSpec = _bindings.AdapterSpec
OrchestrationDefaults = _bindings.OrchestrationDefaults
AdapterRegistry = _bindings.AdapterRegistry
get_adapter_registry = _bindings.get_adapter_registry
AdapterBuilder = _bindings.AdapterBuilder
register_adapter_builder = _bindings.register_adapter_builder
build_adapter_instance = _bindings.build_adapter_instance
require_adapter = _bindings.require_adapter
ValueRef = _bindings.ValueRef
Cond = _bindings.Cond
val = _bindings.val
all_of = _bindings.all_of
any_of = _bindings.any_of
not_ = _bindings.not_
ctx = _bindings.ctx
truthy = _bindings.truthy
exists = _bindings.exists
eq = _bindings.eq
ne = _bindings.ne
gt = _bindings.gt
ge = _bindings.ge
lt = _bindings.lt
le = _bindings.le
in_ = _bindings.in_
not_in = _bindings.not_in
between = _bindings.between
custom = _bindings.custom
group = _bindings.group
multi = _bindings.multi
phase = _bindings.phase
serial = _bindings.serial
event_case = _bindings.event_case
event = _bindings.event
ExampleAdapterConfig = _bindings.ExampleAdapterConfig
build_example_adapter = _bindings.build_example_adapter
