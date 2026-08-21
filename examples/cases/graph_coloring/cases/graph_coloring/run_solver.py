# -*- coding: utf-8 -*-
"""Graph-coloring benchmark CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver  # noqa: E402
else:
    from .build_solver import build_solver

from nsgablack.project.scaffold import print_solver_check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Graph-coloring benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    n_nodes, n_edges = 15, 30
    edges = set()
    while len(edges) < n_edges:
        u, v = int(rng.integers(0, n_nodes)), int(rng.integers(0, n_nodes))
        if u != v:
            edges.add((min(u, v), max(u, v)))
    edges_list = list(edges)
    adjacency = {i: set() for i in range(n_nodes)}
    for u, v in edges_list:
        adjacency[u].add(v)
        adjacency[v].add(u)
    greedy_colors = {}
    for node in sorted(range(n_nodes), key=lambda i: -len(adjacency[i])):
        used = {greedy_colors[n] for n in adjacency[node] if n in greedy_colors}
        color = 0
        while color in used:
            color += 1
        greedy_colors[node] = color
    greedy_count = max(greedy_colors.values()) + 1

    solver = build_solver(edges_list, n_nodes)
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0
    started = time.perf_counter()
    solver.run()
    elapsed = time.perf_counter() - started
    colors = (
        np.asarray(solver.best_x, dtype=int) % 15
        if solver.best_x is not None
        else np.zeros(n_nodes, dtype=int)
    )
    conflicts = sum(1 for u, v in edges_list if colors[u] == colors[v])
    print(f"Welsh-Powell: {greedy_count} colors, 0 conflicts")
    print(f"nsgablack DE: {len(set(colors))} colors, {conflicts} conflicts, time={elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
