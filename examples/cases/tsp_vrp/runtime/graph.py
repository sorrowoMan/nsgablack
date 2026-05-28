# -*- coding: utf-8 -*-
# Static execution-plan graph for resource planning.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Dict, Mapping, Sequence


@dataclass(frozen=True)
class ExecutionGraphNode:
    node_id: str
    label: str
    kind: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    children: tuple["ExecutionGraphNode", ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.node_id),
            "label": str(self.label),
            "kind": str(self.kind),
            "metadata": dict(self.metadata or {}),
            "children": [child.as_dict() for child in self.children],
        }


@dataclass(frozen=True)
class ExecutionGraph:
    root: ExecutionGraphNode

    def as_dict(self) -> Dict[str, Any]:
        return self.root.as_dict()


def build_execution_plan_graph(solver, *, run_id: str = "planned") -> ExecutionGraph:
    problem = getattr(solver, "problem", None)
    pipeline = getattr(solver, "representation_pipeline", None)
    adapter = getattr(solver, "adapter", None)
    plugin_manager = getattr(solver, "plugin_manager", None)
    plugins = _list_plugins(plugin_manager)
    runtime_summary = dict(getattr(solver, "l0_runtime_summary", {}) or {})

    return ExecutionGraph(
        root=ExecutionGraphNode(
            node_id=f"run:{run_id}",
            label=str(run_id),
            kind="run",
            metadata={"graph_type": "static_execution_plan"},
            children=(
                ExecutionGraphNode(
                    node_id="modeling",
                    label="modeling",
                    kind="stage",
                    children=(_object_node("problem", problem), _pipeline_node(pipeline)),
                ),
                ExecutionGraphNode(
                    node_id="search",
                    label="search",
                    kind="stage",
                    children=(_object_node("adapter", adapter),),
                ),
                _runtime_node(runtime_summary),
                ExecutionGraphNode(
                    node_id="plugins",
                    label="plugins",
                    kind="stage",
                    metadata={"count": len(plugins)},
                    children=tuple(_object_node(f"plugin:{i}", plugin) for i, plugin in enumerate(plugins)),
                ),
            ),
        )
    )


def _object_node(node_id: str, obj: object | None) -> ExecutionGraphNode:
    if obj is None:
        return ExecutionGraphNode(node_id=node_id, label="none", kind="empty")
    return ExecutionGraphNode(
        node_id=node_id,
        label=type(obj).__name__,
        kind="component",
        metadata={"module": type(obj).__module__, "name": str(getattr(obj, "name", ""))},
    )


def _pipeline_node(pipeline: object | None) -> ExecutionGraphNode:
    if pipeline is None:
        return ExecutionGraphNode(node_id="pipeline", label="none", kind="empty")
    children = tuple(_object_node(f"pipeline:{attr}", getattr(pipeline, attr, None)) for attr in ("initializer", "mutator", "repair", "encoder"))
    return ExecutionGraphNode(
        node_id="pipeline",
        label=type(pipeline).__name__,
        kind="component",
        metadata={"module": type(pipeline).__module__},
        children=children,
    )


def _runtime_node(summary: Mapping[str, Any]) -> ExecutionGraphNode:
    profile = dict(summary.get("profile", {}) or {})
    return ExecutionGraphNode(
        node_id="runtime",
        label=str(profile.get("key", "unconfigured")),
        kind="l0_runtime",
        metadata={
            "summary": str(profile.get("summary", "")),
            "executor_backend": str(profile.get("executor_backend", "")),
            "resource_backend": str(profile.get("resource_backend", "")),
            "queue_backend": str(profile.get("queue_backend", "")),
            "result_backend": str(profile.get("result_backend", "")),
            "artifact_backend": str(profile.get("artifact_backend", "")),
            "data_transport_backend": str(profile.get("data_transport_backend", "")),
            "lease_store": str(profile.get("lease_store", "")),
            "registered_executor_backends": list(summary.get("registered_executor_backends", []) or []),
            "effective_default_backend": summary.get("effective_default_backend"),
        },
        children=(
            ExecutionGraphNode(
                node_id="runtime:task_requirement",
                label="task_requirement",
                kind="resource_requirement",
                metadata=dict(profile.get("task_requirement", {}) or {}),
            ),
        ),
    )


def _list_plugins(plugin_manager: object | None) -> Sequence[object]:
    if plugin_manager is None:
        return ()
    list_plugins = getattr(plugin_manager, "list_plugins", None)
    if callable(list_plugins):
        try:
            return tuple(list_plugins(enabled_only=False))
        except TypeError:
            return tuple(list_plugins())
    return tuple(getattr(plugin_manager, "plugins", ()) or ())


def build_execution_lifecycle_graph(solver, *, run_id: str = "planned") -> ExecutionGraph:
    problem = getattr(solver, "problem", None)
    pipeline = getattr(solver, "representation_pipeline", None)
    adapter = getattr(solver, "adapter", None)
    plugins = _list_plugins(getattr(solver, "plugin_manager", None))
    runtime_summary = dict(getattr(solver, "l0_runtime_summary", {}) or {})

    lifecycle = ExecutionGraphNode(
        node_id=f"lifecycle:{run_id}",
        label=str(run_id),
        kind="lifecycle_run",
        metadata={"graph_type": "lifecycle_execution_plan"},
        children=(
            ExecutionGraphNode(
                node_id="lifecycle:init",
                label="on_solver_init",
                kind="lifecycle_stage",
                children=(
                    _object_node("problem", problem),
                    _pipeline_node(pipeline),
                    _runtime_node(runtime_summary),
                ),
            ),
            ExecutionGraphNode(
                node_id="lifecycle:population_init",
                label="on_population_init",
                kind="lifecycle_stage",
                children=(
                    _object_node("adapter", adapter),
                    _plugins_hook_node("on_population_init", plugins),
                ),
            ),
            ExecutionGraphNode(
                node_id="lifecycle:generation_loop",
                label="generation_loop",
                kind="lifecycle_stage",
                children=(
                    ExecutionGraphNode(
                        node_id="lifecycle:generation_start",
                        label="on_generation_start",
                        kind="lifecycle_hook",
                        children=(_plugins_hook_node("on_generation_start", plugins),),
                    ),
                    ExecutionGraphNode(
                        node_id="lifecycle:propose",
                        label="adapter.propose",
                        kind="evaluation_chain",
                    ),
                    ExecutionGraphNode(
                        node_id="lifecycle:representation",
                        label="representation",
                        kind="evaluation_chain",
                        children=tuple(
                            _object_node(f"pipeline:{attr}", getattr(pipeline, attr, None))
                            for attr in ("repair", "encoder")
                        ),
                    ),
                    ExecutionGraphNode(
                        node_id="lifecycle:evaluate",
                        label="evaluate_population / evaluate_individual",
                        kind="evaluation_chain",
                    ),
                    ExecutionGraphNode(
                        node_id="lifecycle:update",
                        label="adapter.update",
                        kind="evaluation_chain",
                    ),
                    ExecutionGraphNode(
                        node_id="lifecycle:generation_end",
                        label="on_generation_end",
                        kind="lifecycle_hook",
                        children=(_plugins_hook_node("on_generation_end", plugins),),
                    ),
                ),
            ),
            ExecutionGraphNode(
                node_id="lifecycle:finish",
                label="on_solver_finish",
                kind="lifecycle_stage",
                children=(_plugins_hook_node("on_solver_finish", plugins),),
            ),
        ),
    )
    return ExecutionGraph(root=lifecycle)


def _plugins_hook_node(hook_name: str, plugins: Sequence[object]) -> ExecutionGraphNode:
    children = tuple(
        ExecutionGraphNode(
            node_id=f"hook:{hook_name}:{i}",
            label=type(plugin).__name__,
            kind="plugin",
            metadata={"hook": str(hook_name), "name": str(getattr(plugin, "name", ""))},
        )
        for i, plugin in enumerate(plugins)
    )
    return ExecutionGraphNode(
        node_id=f"hook:{hook_name}",
        label=str(hook_name),
        kind="plugin_hook",
        metadata={"count": len(children)},
        children=children,
    )
