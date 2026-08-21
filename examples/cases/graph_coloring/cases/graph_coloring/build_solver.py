"""Graph Coloring: nsgablack DE vs Welsh-Powell greedy."""
from __future__ import annotations
import numpy as np
from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.coloring_problem import GraphColoringProblem

def build_solver(edges=None, n_nodes=None, max_colors=15, *, pop_size=30, max_steps=200, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    max_colors = int(config.pop("max_colors", max_colors))
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    if config:
        raise ValueError("unsupported graph_coloring config overrides: " + str(sorted(config)))
    edges = overrides.pop("edges", edges)
    n_nodes = overrides.pop("n_nodes", n_nodes)
    if edges is None:
        edges = [(0, 1), (1, 2), (2, 0)]
    if n_nodes is None:
        n_nodes = 3
    prob = GraphColoringProblem(edges, n_nodes, max_colors)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[0]*n_nodes, high=[max_colors-0.001]*n_nodes),
        mutator=ContextGaussianMutation(base_sigma=1.5, low=[0]*n_nodes, high=[max_colors-0.001]*n_nodes),
        repair=ClipRepair(low=[0]*n_nodes, high=[max_colors-0.001]*n_nodes))
    bias = BiasModule()
    def adj_penalty(x, constraints, context):
        colors = np.asarray(x, dtype=int) % max_colors
        c = sum(1 for u, v in prob.edges if colors[u] == colors[v])
        return {"penalty": float(c * 500)}
    bias.add(CallableBias(name="adjacency", func=adj_penalty, weight=1.0, mode="penalty"))
    solver = ComposableSolver(problem=prob, adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
                              representation_pipeline=pipeline, bias_module=bias)
    solver.set_max_steps(max_steps)
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
