"""Canonical child assembly; scenario semantics live in runtime/task_contract.py."""
from collections.abc import Mapping
from blackbase.resources import coerce_resource_context
from .runtime.task_contract import PORTABLE_TASK_SCHEMA, prepare_task
from .solver.case import ProductionInnerCase, PortableProductionInnerCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("production_inner accepts its versioned task through component_overrides")
    overrides = dict(component_overrides or {})
    task = overrides.pop("task", None)
    if overrides:
        raise ValueError(f"unsupported production_inner overrides: {sorted(overrides)}")
    if isinstance(task, Mapping) and task.get("schema") == PORTABLE_TASK_SCHEMA:
        return PortableProductionInnerCase(task, resource_context=resource_context)
    metadata = dict(coerce_resource_context(resource_context).metadata)
    local_parent_lease = dict(metadata.get("child_grant", {}) or {}).get("parent_lease_id")
    if metadata.get("external_target") and not local_parent_lease:
        raise ValueError("external production Case requires portable Artifact inputs, not local task paths")
    prepared = prepare_task(task)
    solver, problem = prepared.build_solver(resource_context=resource_context)
    return ProductionInnerCase(solver, problem, prepared)
