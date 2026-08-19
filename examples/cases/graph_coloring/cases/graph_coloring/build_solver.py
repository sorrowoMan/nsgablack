"""Graph Coloring: nsgablack DE vs Welsh-Powell greedy."""
from __future__ import annotations
import sys, time, argparse
from pathlib import Path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path: sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable; ensure_nsgablack_importable(Path(__file__))
import numpy as np
from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.project.scaffold import print_solver_check
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.coloring_problem import GraphColoringProblem

def build_solver(edges=None, n_nodes=None, max_colors=15, *, pop_size=30, max_steps=200, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    edges = overrides.get("edges", edges)
    n_nodes = overrides.get("n_nodes", n_nodes)
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
    solver.set_resource_context(resource_context)
    return solver

def main():
    p = argparse.ArgumentParser(); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    rng = np.random.default_rng(args.seed); n_nodes, n_edges = 15, 30
    edges = set()
    while len(edges) < n_edges:
        u, v = int(rng.integers(0, n_nodes)), int(rng.integers(0, n_nodes))
        if u != v: edges.add((min(u, v), max(u, v)))
    edges_list = list(edges)
    adj = {i: set() for i in range(n_nodes)}
    for u, v in edges_list: adj[u].add(v); adj[v].add(u)
    degrees = sorted(range(n_nodes), key=lambda i: -len(adj[i]))
    greedy_colors = {}
    for node in degrees:
        used = {greedy_colors[n] for n in adj[node] if n in greedy_colors}
        c = 0
        while c in used: c += 1
        greedy_colors[node] = c
    greedy_k = max(greedy_colors.values()) + 1
    solver = build_solver(edges_list, n_nodes); solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return
    t0 = time.perf_counter(); solver.run(); nsga_t = time.perf_counter()-t0
    nsga_colors = np.asarray(solver.best_x, dtype=int) % 15 if solver.best_x is not None else np.zeros(n_nodes, dtype=int)
    nsga_k = len(set(nsga_colors))
    nsga_conflicts = sum(1 for u, v in edges_list if nsga_colors[u] == nsga_colors[v])
    print(f"Welsh-Powell: {greedy_k} colors, 0 conflicts")
    print(f"nsgablack DE: {nsga_k} colors, {nsga_conflicts} conflicts, time={nsga_t:.2f}s")

if __name__ == "__main__": main()
