"""Graph coloring: minimize colors while respecting adjacency constraints."""
import numpy as np
from nsgablack.core.base import BlackBoxProblem


class GraphColoringProblem(BlackBoxProblem):
    def __init__(self, edges: list, n_nodes: int, max_colors: int = 15):
        self.edges = [(int(u), int(v)) for u, v in edges]
        self.n_nodes = int(n_nodes)
        self.max_colors = int(max_colors)
        super().__init__(dimension=n_nodes, objectives=["minimize"],
                         bounds=[(0.0, float(max_colors) - 0.001)] * n_nodes, name="graph_coloring")

    def evaluate(self, candidate):
        colors = np.asarray(candidate, dtype=int) % self.max_colors
        conflicts = sum(1 for u, v in self.edges if colors[u] == colors[v])
        n_colors = len(set(colors))
        return float(conflicts * 1000 + n_colors)
